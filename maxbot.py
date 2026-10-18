"""Глянец в MAX: тот же ИИ-администратор, та же база записей, напоминания и отмена кнопкой.

Мини-аппа и платежей Telegram в MAX нет, поэтому здесь запись идёт через чат, без предоплаты.
Пользователи MAX хранятся с отрицательным id: с телеграмными не пересекаются.
"""

import asyncio
import logging
import os
import ssl

import certifi
import httpx

import bot as tg
import concierge
import db
import payments

API = "https://platform-api2.max.ru"
TOKEN = os.environ.get("MAX_BOT_TOKEN", "").strip()
CA = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "certs", "russian_trusted_root_ca.pem"
)
TRANSPORT: httpx.AsyncBaseTransport | None = None
WELCOME = (
    "Здравствуйте! Это детейлинг-студия «Глянец». Напишите, что нужно — например, «сколько "
    "стоит керамика на кроссовер и есть ли время в субботу?» — посчитаю и запишу."
)


def enabled() -> bool:
    return bool(TOKEN)


def uid(user_id: int) -> int:
    return -abs(int(user_id))


def _trust() -> ssl.SSLContext:
    # API MAX работает на сертификате Минцифры: без этого корня httpx не соединится.
    context = ssl.create_default_context(cafile=certifi.where())
    context.load_verify_locations(CA)
    return context


def client() -> httpx.AsyncClient:
    return httpx.AsyncClient(
        base_url=API,
        headers={"Authorization": TOKEN},
        verify=_trust() if TRANSPORT is None else True,
        transport=TRANSPORT,
        timeout=45,
    )


def cancel_button(booking_id: int) -> list[list[dict]]:
    return [[{"type": "callback", "text": "Отменить запись", "payload": f"cancel:{booking_id}"}]]


async def send(http, text: str, *, chat_id=None, user_id=None, buttons=None) -> bool:
    body: dict = {"text": text[:4000]}
    if buttons:
        body["attachments"] = [{"type": "inline_keyboard", "payload": {"buttons": buttons}}]
    params = {"chat_id": chat_id} if chat_id is not None else {"user_id": user_id}
    response = await http.post("/messages", params=params, json=body)
    if response.status_code != 200:
        logging.warning("MAX не принял сообщение: %s", response.status_code)
    return response.status_code == 200


async def handle(http, update: dict) -> None:
    kind = update.get("update_type")
    if kind == "bot_started":
        await send(http, WELCOME, chat_id=update["chat_id"])
    elif kind == "message_created":
        message = update.get("message") or {}
        text = ((message.get("body") or {}).get("text") or "").strip()
        sender = message.get("sender") or {}
        chat_id = (message.get("recipient") or {}).get("chat_id")
        if not text or text.startswith("/start") or "user_id" not in sender:
            return
        try:
            answer = await concierge.reply(
                uid(sender["user_id"]),
                text,
                source="max",
                on_event=tg.on_event,
                pay_link=tg.pay_link if payments.enabled() else None,
                prepay_percent=tg.PREPAY_PERCENT,
            )
        except Exception:
            logging.exception("MAX: ИИ-администратор упал")
            answer = concierge.FALLBACK
        await send(http, answer, chat_id=chat_id)
    elif kind == "message_callback":
        pressed = update.get("callback") or {}
        payload = pressed.get("payload") or ""
        user = pressed.get("user") or {}
        if not payload.startswith("cancel:") or "user_id" not in user:
            return
        booking = await db.cancel(int(payload.split(":")[1]), uid(user["user_id"]))
        note = "Запись отменена." if booking else "Запись не найдена."
        await http.post(
            "/answers",
            params={"callback_id": pressed.get("callback_id")},
            json={"notification": note},
        )
        if booking:
            await tg.on_event("cancelled", booking)


async def tell(user_id: int, text: str) -> None:
    async with client() as http:
        await send(http, text, user_id=abs(user_id))


async def remind(booking) -> bool:
    start = db.aware(booking.start_at).astimezone(tg.MSK)
    text = (
        f"Напоминаем: сегодня в {start:%H:%M} ждём вас в «Глянце».\n{tg.describe(booking)}\n\n"
        "Ходынский бульвар, м. ЦСКА. Планы поменялись — отмените запись кнопкой ниже."
    )
    async with client() as http:
        return await send(
            http, text, user_id=abs(booking.user_id), buttons=cancel_button(booking.id)
        )


async def run() -> None:
    marker = None
    async with client() as http:
        while True:
            try:
                params: dict = {
                    "timeout": 30,
                    "types": "bot_started,message_created,message_callback",
                }
                if marker is not None:
                    params["marker"] = marker
                response = await http.get("/updates", params=params)
                response.raise_for_status()
                data = response.json()
                marker = data.get("marker", marker)
                for update in data.get("updates", []):
                    try:
                        await handle(http, update)
                    except Exception:
                        logging.exception("MAX: ошибка в обработке апдейта")
            except asyncio.CancelledError:
                raise
            except Exception:
                logging.exception("MAX: опрос упал, повтор через 5 секунд")
                await asyncio.sleep(5)
