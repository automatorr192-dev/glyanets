"""Сервер Глянца: мини-апп, API записи и боты в одном процессе.

Цену, длительность и свободное время считает сервер по catalog.json — тем же правилам,
что видит клиент в мини-аппе. С телефона приходят только выбор услуг и время: сумму,
пришедшую с фронта, можно подделать, а сумму, посчитанную здесь, — нет.
"""

import asyncio
import logging
import os
from contextlib import asynccontextmanager, suppress
from datetime import date

from dotenv import load_dotenv

load_dotenv()

from alembic import command  # noqa: E402
from alembic.config import Config  # noqa: E402
from fastapi import Depends, FastAPI, Header, HTTPException, Query, status  # noqa: E402
from fastapi.staticfiles import StaticFiles  # noqa: E402
from pydantic import BaseModel, Field  # noqa: E402
from sqlalchemy import text  # noqa: E402

import bot as tg  # noqa: E402
import db  # noqa: E402
import maxbot  # noqa: E402
import schedule  # noqa: E402
import tgauth  # noqa: E402
from schedule import BadOrder  # noqa: E402

logging.basicConfig(level=logging.INFO)

HERE = os.path.dirname(os.path.abspath(__file__))
DIST = os.path.join(HERE, "dist")


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


@asynccontextmanager
async def lifespan(app: FastAPI):
    await asyncio.to_thread(migrate)
    jobs = [asyncio.create_task(tg.ticker(maxbot.remind if maxbot.enabled() else None))]
    if tg.BOT_TOKEN:
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
        return shape(booking, await tg.invoice_link(booking))
    await tg.on_event("booked", booking)
    return shape(booking)


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


class NoCacheStatic(StaticFiles):
    """WebView Telegram кэширует мини-апп намертво: no-cache заставляет сверять ETag."""

    def file_response(self, *args, **kwargs):
        response = super().file_response(*args, **kwargs)
        response.headers["Cache-Control"] = "no-cache"
        return response


# Только собранный dist/: в корне лежат .env и код — наружу их отдавать нельзя.
if os.path.isdir(DIST):
    app.mount("/", NoCacheStatic(directory=DIST, html=True), name="webapp")
