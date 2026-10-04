"""Бот-лаунчер мини-аппа «Глянец»: /start с кнопкой и кнопка меню, больше ничего."""

import asyncio
import os

from aiogram import Bot, Dispatcher
from aiogram.filters import CommandStart
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, MenuButtonWebApp, Message, WebAppInfo
from dotenv import load_dotenv

load_dotenv()

WEBAPP_URL = os.environ.get("WEBAPP_URL", "https://automatorr192-dev.github.io/glyanets/")
DESCRIPTION = (
    "Запись в детейлинг-студию «Глянец» за минуту: мойка, полировка, керамика, химчистка и "
    "бронеплёнка. Выберите услуги и время, а пока машина у нас, следите за этапами работ."
)
SHORT_DESCRIPTION = "Запись на детейлинг и статус работ над вашей машиной в реальном времени."
WELCOME = "Здравствуйте! Здесь можно записаться на детейлинг и следить, как идёт работа над машиной."

dp = Dispatcher()


@dp.message(CommandStart())
async def start(message: Message):
    button = InlineKeyboardButton(text="Записаться", web_app=WebAppInfo(url=WEBAPP_URL))
    await message.answer(WELCOME, reply_markup=InlineKeyboardMarkup(inline_keyboard=[[button]]))


async def main():
    bot = Bot(os.environ["BOT_TOKEN"])
    await bot.set_my_description(DESCRIPTION)
    await bot.set_my_short_description(SHORT_DESCRIPTION)
    await bot.set_chat_menu_button(menu_button=MenuButtonWebApp(text="Запись", web_app=WebAppInfo(url=WEBAPP_URL)))
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
