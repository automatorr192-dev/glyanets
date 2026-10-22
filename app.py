"""Сервер Глянца: мини-апп, API записи и боты в одном процессе.

Цену, длительность и свободное время считает сервер по catalog.json — тем же правилам,
что видит клиент в мини-аппе. С телефона приходят только выбор услуг и время: сумму,
пришедшую с фронта, можно подделать, а сумму, посчитанную здесь, — нет.
"""

import asyncio
import hmac
import json
import logging
import os
from collections import deque
from contextlib import asynccontextmanager, suppress
from datetime import date

from dotenv import load_dotenv

load_dotenv()

from aiogram.types import Update  # noqa: E402
from alembic import command  # noqa: E402
from alembic.config import Config  # noqa: E402
from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request, status  # noqa: E402
from fastapi.staticfiles import StaticFiles  # noqa: E402
from pydantic import BaseModel, Field  # noqa: E402
from sqlalchemy import text  # noqa: E402

import bot as tg  # noqa: E402
import db  # noqa: E402
import maxbot  # noqa: E402
import payments  # noqa: E402
import schedule  # noqa: E402
import tgauth  # noqa: E402
from schedule import BadOrder  # noqa: E402

logging.basicConfig(level=logging.INFO)

HERE = os.path.dirname(os.path.abspath(__file__))
DIST = os.path.join(HERE, "dist")
# Заданы оба — бот на вебхуке: бесплатный Render усыпляет сервер без входящих запросов,
# и будит его сам Telegram, когда клиент пишет. Без них — long polling.
PUBLIC_URL = (os.environ.get("PUBLIC_URL") or os.environ.get("RENDER_EXTERNAL_URL", "")).rstrip("/")
WEBHOOK_SECRET = os.environ.get("WEBHOOK_SECRET", "")


def migrate() -> None:
    command.upgrade(Config(os.path.join(HERE, "alembic.ini")), "head")


async def _forever(job, name: str):
    while True:
        try:
            await job()
            return
        except asyncio.CancelledError:
            raise
        except Exception:
            logging.exception("%s упал, перезапуск через 5 с", name)
            await asyncio.sleep(5)


def hooked() -> bool:
    return bool(tg.BOT_TOKEN and WEBHOOK_SECRET and PUBLIC_URL)


async def _hook() -> None:
    try:
        await tg.introduce()
        # Без drop_pending_updates: сервер будит как раз то сообщение, что ждёт в очереди.
        await tg.bot().set_webhook(
            f"{PUBLIC_URL}/telegram",
            secret_token=WEBHOOK_SECRET,
            allowed_updates=tg.dp.resolve_used_update_types(),
        )
    except Exception:
        # Telegram недоступен на старте — мини-апп и API записи всё равно должны жить.
        logging.exception("вебхук не установлен")


@asynccontextmanager
async def lifespan(app: FastAPI):
    await asyncio.to_thread(migrate)
    jobs = [asyncio.create_task(tg.ticker(maxbot.remind if maxbot.enabled() else None))]
    if hooked():
        await _hook()
    elif tg.BOT_TOKEN:
        jobs.append(asyncio.create_task(_forever(tg.main, "Telegram-бот")))
    if maxbot.enabled():
        jobs.append(asyncio.create_task(_forever(maxbot.run, "MAX-бот")))
    yield
    for job in jobs:
        job.cancel()
        with suppress(asyncio.CancelledError):
            await job


app = FastAPI(title="Глянец", lifespan=lifespan)


async def client(x_init_data: str = Header("")) -> int:
    """Кто записывается — только из подписи Telegram, а не из тела запроса."""
    try:
        user = tgauth.check(x_init_data, tg.BOT_TOKEN)
    except tgauth.BadInitData as e:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Откройте запись из Telegram") from e
    return int(user["id"])


def shape(booking: db.Booking, invoice: str | None = None) -> dict:
    return {
        "id": str(booking.id),
        "services": booking.service_ids,
        "cls": booking.car_class,
        "car": booking.car,
        "plate": booking.plate or "",
        "start": db.aware(booking.start_at).isoformat(),
        "ready": db.aware(booking.ready_at).isoformat(),
        "total": booking.total,
        "phone": booking.phone,
        "cancelled": booking.status == "cancelled",
        "status": booking.status,
        "prepay": booking.prepay,
        "invoice": invoice,
    }


class BookingIn(BaseModel):
    services: list[str] = Field(min_length=1, max_length=5)
    cls: str
    day: str
    time: str
    car: str = Field(min_length=2, max_length=100)
    plate: str = Field("", max_length=20)
    name: str = Field("", max_length=100)
    phone: str = Field(min_length=10, max_length=20)


class MoveIn(BaseModel):
    day: str
    time: str


@app.get("/health")
async def health():
    async with db.Session() as session:
        await session.execute(text("select 1"))
    return {"status": "ok"}


@app.get("/api/config")
async def config():
    return {"prepay_percent": tg.PREPAY_PERCENT}


@app.get("/api/slots")
async def slots(day: date, cls: str, services: str = Query(min_length=1)):
    try:
        return {"slots": await db.free_starts(day, services.split(","), cls)}
    except BadOrder as e:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(e)) from e


@app.get("/api/bookings")
async def my_bookings(user: int = Depends(client)):
    return [shape(b) for b in await db.mine(user)]


@app.post("/api/bookings", status_code=status.HTTP_201_CREATED)
async def create_booking(data: BookingIn, user: int = Depends(client)):
    try:
        hours = schedule.quote(data.services, data.cls)["hours"]
        start = schedule.parse_start(data.day, data.time, hours)
        booking = await db.book(
            user,
            data.services,
            data.cls,
            start,
            data.car,
            data.phone,
            name=data.name,
            plate=data.plate,
            prepay_percent=tg.PREPAY_PERCENT,
        )
    except BadOrder as e:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(e)) from e
    except db.Taken as e:
        raise HTTPException(status.HTTP_409_CONFLICT, "Это время только что заняли") from e
    if booking.status == "awaiting_payment":
        try:
            return shape(booking, await tg.pay_link(booking))
        except payments.PaymentError as e:
            # Без ссылки на оплату бронь бессмысленна: освобождаем время сразу, а не через 15 минут.
            await db.cancel(booking.id)
            logging.warning("оплата не создана: %s", e)
            raise HTTPException(
                status.HTTP_502_BAD_GATEWAY, "Не получилось открыть оплату, попробуйте ещё раз"
            ) from e
    await tg.on_event("booked", booking)
    return shape(booking)


@app.post("/api/payments/rollypay")
async def rollypay_callback(request: Request):
    """Уведомление RollyPay об оплате. Отвечаем 2xx на всё подписанное: иначе RollyPay будет
    повторять уведомление час. Подтверждаем запись только после сверки подписи и суммы."""
    body = await request.body()
    try:
        payments.verify(
            body, request.headers.get("X-Timestamp"), request.headers.get("X-Signature")
        )
    except payments.BadSignature as e:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Подпись не сходится") from e
    event = json.loads(body)
    booking_id = payments.booking_of(event)
    # Тестовая оплата подтверждает запись, только пока касса сама в тестовом режиме.
    if event.get("event_type") != "payment.paid" or booking_id is None:
        return {"ok": True}
    if bool(event.get("test")) != payments.TEST:
        return {"ok": True}
    booking = await db.get(booking_id)
    if booking is None or float(event.get("amount") or 0) != booking.prepay:
        logging.warning("оплата не сходится с записью: %s", event.get("order_id"))
        return {"ok": True}
    paid = await db.mark_paid(booking_id)
    if paid is None:
        if booking.status == "cancelled":
            await tg.on_event(
                "handoff",
                f"Оплата по брони №{booking_id} пришла после того, как бронь истекла: "
                f"свяжитесь с клиентом {booking.phone}",
            )
        return {"ok": True}
    await tg.on_event("paid", paid)
    text = f"{tg.PAID}\n{tg.describe(paid)}"
    if paid.user_id > 0:
        await tg.tell(paid.user_id, text)
    else:
        await maxbot.tell(paid.user_id, text)
    return {"ok": True}


@app.patch("/api/bookings/{booking_id}")
async def move_booking(booking_id: int, data: MoveIn, user: int = Depends(client)):
    current = await db.get(booking_id, user)
    if current is None or current.status == "cancelled":
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Запись не найдена")
    try:
        hours = schedule.quote(current.service_ids, current.car_class)["hours"]
        start = schedule.parse_start(data.day, data.time, hours)
        booking = await db.reschedule(booking_id, user, start)
    except BadOrder as e:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(e)) from e
    except db.Taken as e:
        raise HTTPException(status.HTTP_409_CONFLICT, "Это время только что заняли") from e
    await tg.on_event("moved", booking)
    return shape(booking)


@app.delete("/api/bookings/{booking_id}")
async def cancel_booking(booking_id: int, user: int = Depends(client)):
    booking = await db.cancel(booking_id, user)
    if booking is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Запись не найдена")
    await tg.on_event("cancelled", booking)
    return shape(booking)


_handling: set[asyncio.Task] = set()
_seen: deque[int] = deque(maxlen=1000)


@app.post("/telegram")
async def telegram_update(request: Request):
    secret = request.headers.get("X-Telegram-Bot-Api-Secret-Token", "")
    if not hooked() or not hmac.compare_digest(secret, WEBHOOK_SECRET):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Forbidden")
    update = Update.model_validate(await request.json(), context={"bot": tg.bot()})
    # Пока бесплатный Render просыпается, Telegram может прислать то же обновление ещё раз.
    if update.update_id in _seen:
        return {"ok": True}
    _seen.append(update.update_id)
    # ИИ-администратор думает дольше, чем Telegram ждёт ответа на вебхук: отвечаем сразу,
    # обрабатываем фоном. Ссылку на задачу держим, иначе её соберёт сборщик мусора.
    task = asyncio.create_task(tg.dp.feed_update(tg.bot(), update))
    _handling.add(task)
    task.add_done_callback(_handling.discard)
    return {"ok": True}


class NoCacheStatic(StaticFiles):
    """WebView Telegram кэширует мини-апп намертво: no-cache заставляет сверять ETag."""

    def file_response(self, *args, **kwargs):
        response = super().file_response(*args, **kwargs)
        response.headers["Cache-Control"] = "no-cache"
        return response


# Только собранный dist/: в корне лежат .env и код — наружу их отдавать нельзя.
if os.path.isdir(DIST):
    app.mount("/", NoCacheStatic(directory=DIST, html=True), name="webapp")
