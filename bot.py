"""Бот Глянца: открывает мини-апп, напоминает о визите, принимает предоплату и отвечает
клиентам как администратор студии. Живёт в одном процессе с сервером записи (app.py).
"""

import asyncio
import html
import logging
import os

from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    MenuButtonWebApp,
    Message,
    WebAppInfo,
)
from dotenv import load_dotenv

import concierge
import db
import payments
import schedule
from schedule import MSK

load_dotenv()

BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
WEBAPP_URL = os.environ.get("WEBAPP_URL", "https://automatorr192-dev.github.io/glyanets/")
ADMIN_CHAT_ID = int(os.environ.get("ADMIN_CHAT_ID") or 0)
# Предоплата через RollyPay (payments.py). Нет ключей кассы — записи без предоплаты.
PREPAY_PERCENT = int(os.environ.get("PREPAY_PERCENT") or 20) if payments.enabled() else 0
PAID = "Предоплата получена, запись подтверждена."
CHECK_EVERY = 60

DESCRIPTION = (
    "Запись в детейлинг-студию «Глянец» за минуту: мойка, полировка, керамика, химчистка и "
    "бронеплёнка. Выберите услуги и время в приложении или просто напишите сюда — "
    "администратор ответит на вопросы о ценах и запишет."
)
SHORT_DESCRIPTION = "Запись на детейлинг и статус работ над вашей машиной в реальном времени."
WELCOME = (
    "Здравствуйте! Записаться можно кнопкой ниже — или напишите сюда: например, "
    "«сколько стоит керамика на кроссовер и есть ли время в субботу?»"
)

dp = Dispatcher()
_bot: Bot | None = None


def bot() -> Bot:
    global _bot
    if _bot is None:
        _bot = Bot(BOT_TOKEN)
    return _bot


def describe(booking) -> str:
    start = db.aware(booking.start_at).astimezone(MSK)
    ready = db.aware(booking.ready_at).astimezone(MSK)
    names = " + ".join(schedule.SERVICES[s]["name"] for s in booking.service_ids)
    total = f"{booking.total:,}".replace(",", " ")
    return (
        f"{names} · {booking.car}\n"
        f"{start:%d.%m %H:%M} → готово {ready:%d.%m} к {ready:%H:%M} · {total} ₽"
    )


async def notify_admin(text: str) -> None:
    if not ADMIN_CHAT_ID or not BOT_TOKEN:
        return
    try:
        await bot().send_message(ADMIN_CHAT_ID, text, parse_mode="HTML")
    except Exception:
        logging.exception("администратору не ушло")


async def on_event(kind: str, subject) -> None:
    """События записи — в чат администратора студии."""
    if kind == "handoff":
        await notify_admin(f"🙋 <b>Клиент просит администратора</b>\n{html.escape(str(subject))}")
        return
    title = {
        "booked": "🆕 Новая запись",
        "paid": "💳 Предоплата получена",
        "moved": "↪️ Запись перенесена",
        "cancelled": "✖️ Запись отменена",
    }[kind]
    who = html.escape(f"{subject.name or 'Клиент'} · {subject.phone}")
    await notify_admin(f"<b>{title} №{subject.id}</b>\n{who}\n{html.escape(describe(subject))}")


async def pay_link(booking) -> str | None:
    if not payments.enabled() or not booking.prepay:
        return None
    return await payments.create(
        booking.id, booking.prepay, f"Предоплата · Глянец · {describe(booking)}", WEBAPP_URL
    )


async def tell(user_id: int, text: str) -> None:
    try:
        await bot().send_message(user_id, text)
    except Exception:
        logging.exception("клиенту не ушло")


def reminder_keyboard(booking) -> InlineKeyboardMarkup:
    move = WebAppInfo(url=f"{WEBAPP_URL}?move={booking.id}")
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Перенести", web_app=move)],
            [InlineKeyboardButton(text="Отменить", callback_data=f"cancel:{booking.id}")],
        ]
    )


async def remind(booking) -> bool:
    start = db.aware(booking.start_at).astimezone(MSK)
    text = (
        f"Напоминаем: сегодня в {start:%H:%M} ждём вас в «Глянце».\n{describe(booking)}\n\n"
        "Ходынский бульвар, м. ЦСКА. Если планы поменялись — перенесите или отмените."
    )
    try:
        await bot().send_message(booking.user_id, text, reply_markup=reminder_keyboard(booking))
        return True
    except Exception:
        logging.exception("напоминание не ушло")
        return False


async def tick(remind_max=None) -> None:
    """Раз в минуту: напомнить о визите через 2 часа и вернуть неоплаченные брони."""
    await db.expire_holds()
    for booking in await db.due_reminders():
        if booking.user_id > 0:
            sent = BOT_TOKEN and await remind(booking)
        else:
            sent = remind_max and await remind_max(booking)
        if sent:
            await db.mark_reminded(booking.id)


async def ticker(remind_max=None) -> None:
    while True:
        try:
            await tick(remind_max)
        except Exception:
            logging.exception("напоминания упали")
        await asyncio.sleep(CHECK_EVERY)


def open_app() -> InlineKeyboardMarkup:
    button = InlineKeyboardButton(text="Записаться", web_app=WebAppInfo(url=WEBAPP_URL))
    return InlineKeyboardMarkup(inline_keyboard=[[button]])


@dp.message(CommandStart())
async def start(message: Message):
    await message.answer(WELCOME, reply_markup=open_app())


@dp.callback_query(F.data.startswith("cancel:"))
async def cancel_from_reminder(query: CallbackQuery):
    booking = await db.cancel(int(query.data.split(":")[1]), query.from_user.id)
    if booking is None:
        await query.answer("Запись не найдена")
        return
    await query.answer("Запись отменена")
    await query.message.edit_text("Запись отменена. Будем рады видеть вас в другой раз.")
    await on_event("cancelled", booking)


@dp.message(F.text)
async def chat(message: Message):
    await bot().send_chat_action(message.chat.id, "typing")
    try:
        answer = await concierge.reply(
            message.from_user.id,
            message.text,
            source="bot",
            on_event=on_event,
            pay_link=pay_link if payments.enabled() else None,
            prepay_percent=PREPAY_PERCENT,
        )
    except Exception:
        logging.exception("ИИ-администратор упал")
        answer = concierge.FALLBACK
    await message.answer(answer)


async def main():
    b = bot()
    await b.set_my_description(DESCRIPTION)
    await b.set_my_short_description(SHORT_DESCRIPTION)
    await b.set_chat_menu_button(
        menu_button=MenuButtonWebApp(text="Запись", web_app=WebAppInfo(url=WEBAPP_URL))
    )
    await dp.start_polling(b)


if __name__ == "__main__":
    asyncio.run(main())
