"""Цены, время начала и готовность — те же правила, что в мини-аппе (src/lib/data.ts), из того
же catalog.json. Сервер считает сам: цене и времени, пришедшим с телефона, верить нельзя.
Всё время — московское: студия одна, и «9 утра» у клиента в Новосибирске — тоже 9 по Москве.
"""

import json
import math
import os
from datetime import date, datetime, time, timedelta, timezone

MSK = timezone(timedelta(hours=3), "MSK")
HERE = os.path.dirname(os.path.abspath(__file__))

with open(os.path.join(HERE, "catalog.json"), encoding="utf-8") as file:
    CATALOG = json.load(file)

SERVICES = {service["id"]: service for service in CATALOG["services"]}
CLASSES = {item["id"]: item["name"] for item in CATALOG["classes"]}
ORDER = CATALOG["order"]
OPEN, CLOSE = CATALOG["open_hour"], CATALOG["close_hour"]
BUNDLE = ("polish", "ceramic")
DAYS_AHEAD = 14
LEAD = timedelta(hours=1)


class BadOrder(ValueError):
    pass


def quote(ids: list[str], car_class: str) -> dict:
    if car_class not in CLASSES:
        raise BadOrder(f"неизвестный класс машины: {car_class}")
    if not ids or len(set(ids)) != len(ids) or any(i not in SERVICES for i in ids):
        raise BadOrder("услуги не выбраны или указаны неверно")
    ordered = sorted(ids, key=ORDER.index)
    items = [
        {"id": i, "name": SERVICES[i]["name"], "price": SERVICES[i]["price"][car_class]}
        for i in ordered
    ]
    subtotal = sum(item["price"] for item in items)
    discount = 0
    if all(i in ids for i in BUNDLE):
        bundle = sum(SERVICES[i]["price"][car_class] for i in BUNDLE)
        discount = round(bundle * CATALOG["bundle_off"] / 100) * 100
    return {
        "services": ordered,
        "items": items,
        "subtotal": subtotal,
        "discount": discount,
        "total": subtotal - discount,
        "hours": sum(SERVICES[i]["hours"] for i in ids),
    }


def starts(day: date, hours: float) -> list[datetime]:
    """Возможные начала. Долгие работы — только утром и по часу, короткие — каждые полчаса
    так, чтобы закончить до закрытия."""
    long_job = hours >= 6
    last = 11 if long_job else CLOSE - math.ceil(hours)
    step = 60 if long_job else 30
    out = []
    minute = OPEN * 60
    while minute <= last * 60:
        out.append(datetime.combine(day, time(minute // 60, minute % 60), MSK))
        minute += step
    return out


def ready_at(start: datetime, hours: float) -> datetime:
    """Работы идут только в часы студии: что не успели сегодня, доделают завтра с утра."""
    end = start.astimezone(MSK)
    left = timedelta(hours=hours)
    while left > timedelta(0):
        closing = end.replace(hour=CLOSE, minute=0, second=0, microsecond=0)
        room = max(closing - end, timedelta(0))
        if left <= room:
            return end + left
        left -= room
        end = (end + timedelta(days=1)).replace(hour=OPEN, minute=0, second=0, microsecond=0)
    return end


def parse_start(day: str, at: str, hours: float, now: datetime | None = None) -> datetime:
    """Начало визита из «2026-10-20» и «09:30» — только если такое время вообще бывает."""
    now = now or datetime.now(MSK)
    try:
        when = date.fromisoformat(day)
        start = datetime.combine(when, time.fromisoformat(at), MSK)
    except ValueError as e:
        raise BadOrder("дата или время в неверном формате") from e
    if start not in starts(when, hours):
        raise BadOrder("в это время такую работу не начинают")
    if start < now + LEAD:
        raise BadOrder("это время уже прошло")
    if when > now.astimezone(MSK).date() + timedelta(days=DAYS_AHEAD - 1):
        raise BadOrder(f"записываем не дальше чем на {DAYS_AHEAD} дней вперёд")
    return start


def prepayment(total: int, percent: int) -> int:
    """Доля суммы до сотни рублей, но не меньше 500 ₽: копеечная предоплата не держит клиента."""
    if percent <= 0:
        return 0
    return min(total, max(500, round(total * percent / 100 / 100) * 100))
