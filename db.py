"""Записи в боксы студии.

Два клиента могут нажать «Записаться» на одно время в одну и ту же секунду. Проверка
«свободно ли» в коде этого не ловит: оба запроса успеют увидеть свободный бокс до того,
как кто-то из них запишет. Поэтому последнее слово за базой: на Postgres ограничение
EXCLUDE не даёт двум живым записям одного бокса пересечься по времени. Код выбирает бокс,
база гарантирует; проиграл гонку — пробуем следующий бокс.
"""

import os
from datetime import UTC, datetime, timedelta

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    Integer,
    SmallInteger,
    String,
    Text,
    func,
    select,
)
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

import schedule

DATA_DIR = os.environ.get("DATA_DIR") or ("/data" if os.path.isdir("/data") else "data")
BOXES = int(os.environ.get("BOXES") or 2)
# Сколько держим время за клиентом, который ещё не внёс предоплату.
HOLD = timedelta(minutes=int(os.environ.get("HOLD_MINUTES") or 15))
STATUSES = ("awaiting_payment", "confirmed", "cancelled")


def database_url() -> str:
    url = os.environ.get("DATABASE_URL")
    if url:
        return url.replace("postgresql://", "postgresql+asyncpg://", 1)
    os.makedirs(DATA_DIR, exist_ok=True)
    return f"sqlite+aiosqlite:///{os.path.join(DATA_DIR, 'glyanets.db')}"


engine = create_async_engine(database_url(), future=True)
Session = async_sessionmaker(engine, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


class Taken(Exception):
    """Время заняли: свободного бокса на этот отрезок нет."""


class Booking(Base):
    __tablename__ = "bookings"
    __table_args__ = (
        CheckConstraint(
            "status in ('awaiting_payment', 'confirmed', 'cancelled')", name="ck_bookings_status"
        ),
        CheckConstraint("ready_at > start_at", name="ck_bookings_period"),
        CheckConstraint("total >= 0 and prepay >= 0", name="ck_bookings_money"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    # Telegram — id пользователя, MAX — тот же id со знаком минус: пространства не пересекаются.
    user_id: Mapped[int] = mapped_column(BigInteger, index=True)
    name: Mapped[str | None] = mapped_column(String(100))
    phone: Mapped[str] = mapped_column(String(20))
    car: Mapped[str] = mapped_column(String(100))
    plate: Mapped[str | None] = mapped_column(String(20))
    services: Mapped[str] = mapped_column(String(100))
    car_class: Mapped[str] = mapped_column(String(10))
    start_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    ready_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    box: Mapped[int] = mapped_column(SmallInteger)
    total: Mapped[int] = mapped_column(Integer)
    prepay: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    status: Mapped[str] = mapped_column(String(20), default="confirmed")
    source: Mapped[str] = mapped_column(String(10), default="app")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    reminded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    @property
    def service_ids(self) -> list[str]:
        return self.services.split(",")


class ChatMessage(Base):
    """Переписка с ИИ-администратором: модели нужен разговор целиком, а не последняя реплика."""

    __tablename__ = "chat_messages"
    __table_args__ = (CheckConstraint("role in ('client', 'admin')", name="ck_chat_role"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(BigInteger, index=True)
    role: Mapped[str] = mapped_column(String(10))
    text: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


def aware(moment: datetime) -> datetime:
    return moment if moment.tzinfo else moment.replace(tzinfo=UTC)


def utc(moment: datetime) -> datetime:
    """В базу — только UTC: sqlite отбрасывает пояс и сравнивает время как строки."""
    return moment.astimezone(UTC)


def _live():
    return Booking.status != "cancelled"


async def busy_boxes(session, start: datetime, end: datetime, skip: int | None = None) -> set[int]:
    query = select(Booking.box).where(
        _live(), Booking.start_at < utc(end), Booking.ready_at > utc(start)
    )
    if skip is not None:
        query = query.where(Booking.id != skip)
    return set((await session.execute(query)).scalars())


async def free_starts(day, services: list[str], car_class: str, now: datetime | None = None):
    """Время начала на день: свободно, если к этому отрезку найдётся хоть один бокс."""
    now = now or datetime.now(schedule.MSK)
    hours = schedule.quote(services, car_class)["hours"]
    options = schedule.starts(day, hours)
    if not options:
        return []
    horizon = schedule.ready_at(options[-1], hours)
    async with Session() as session:
        rows = (
            await session.execute(
                select(Booking.box, Booking.start_at, Booking.ready_at).where(
                    _live(), Booking.start_at < utc(horizon), Booking.ready_at > utc(options[0])
                )
            )
        ).all()
    out = []
    for start in options:
        end = schedule.ready_at(start, hours)
        taken = {box for box, a, b in rows if aware(a) < end and aware(b) > start}
        out.append(
            {
                "time": start.strftime("%H:%M"),
                "free": start >= now + schedule.LEAD and len(taken) < BOXES,
            }
        )
    return out


async def _place(make, start: datetime, end: datetime, skip: int | None = None) -> Booking:
    """Найти бокс и записать. make(session, box) кладёт или правит запись в сессии."""
    tried: set[int] = set()
    while True:
        async with Session() as session:
            busy = await busy_boxes(session, start, end, skip) | tried
            free = [box for box in range(1, BOXES + 1) if box not in busy]
            if not free:
                raise Taken
            booking = await make(session, free[0])
            try:
                await session.commit()
            except IntegrityError:
                # Бокс увели между проверкой и записью: база не пустила, берём следующий.
                tried.add(free[0])
                continue
            await session.refresh(booking)
            return booking


async def book(
    user_id: int,
    services: list[str],
    car_class: str,
    start: datetime,
    car: str,
    phone: str,
    name: str | None = None,
    plate: str | None = None,
    source: str = "app",
    prepay_percent: int = 0,
) -> Booking:
    price = schedule.quote(services, car_class)
    end = schedule.ready_at(start, price["hours"])
    prepay = schedule.prepayment(price["total"], prepay_percent)

    async def make(session, box):
        booking = Booking(
            user_id=user_id,
            name=(name or "").strip()[:100] or None,
            phone=phone.strip()[:20],
            car=car.strip()[:100],
            plate=(plate or "").strip().upper()[:20] or None,
            services=",".join(price["services"]),
            car_class=car_class,
            start_at=utc(start),
            ready_at=utc(end),
            box=box,
            total=price["total"],
            prepay=prepay,
            status="awaiting_payment" if prepay else "confirmed",
            source=source,
        )
        session.add(booking)
        return booking

    return await _place(make, start, end)


async def reschedule(booking_id: int, user_id: int, start: datetime) -> Booking | None:
    current = await get(booking_id, user_id)
    if current is None or current.status == "cancelled":
        return None
    end = schedule.ready_at(start, schedule.quote(current.service_ids, current.car_class)["hours"])

    async def make(session, box):
        booking = await session.get(Booking, booking_id)
        booking.start_at, booking.ready_at, booking.box = utc(start), utc(end), box
        booking.reminded_at = None
        return booking

    return await _place(make, start, end, skip=booking_id)


async def get(booking_id: int, user_id: int | None = None) -> Booking | None:
    async with Session() as session:
        booking = await session.get(Booking, booking_id)
    if booking is None or (user_id is not None and booking.user_id != user_id):
        return None
    return booking


async def mine(user_id: int, days: int = 60) -> list[Booking]:
    since = datetime.now(UTC) - timedelta(days=days)
    async with Session() as session:
        rows = await session.execute(
            select(Booking)
            .where(Booking.user_id == user_id, Booking.start_at >= since)
            .order_by(Booking.start_at)
        )
        return list(rows.scalars())


async def cancel(booking_id: int, user_id: int | None = None) -> Booking | None:
    async with Session() as session:
        booking = await session.get(Booking, booking_id)
        if booking is None or (user_id is not None and booking.user_id != user_id):
            return None
        booking.status = "cancelled"
        await session.commit()
        await session.refresh(booking)
    return booking


async def mark_paid(booking_id: int) -> Booking | None:
    async with Session() as session:
        booking = await session.get(Booking, booking_id)
        if booking is None or booking.status != "awaiting_payment":
            return None
        booking.status, booking.paid_at = "confirmed", datetime.now(UTC)
        await session.commit()
        await session.refresh(booking)
    return booking


async def expire_holds(now: datetime | None = None) -> int:
    """Не оплатил за время брони — время возвращается в расписание."""
    deadline = (now or datetime.now(UTC)) - HOLD
    async with Session() as session:
        rows = await session.execute(
            select(Booking).where(
                Booking.status == "awaiting_payment", Booking.created_at < deadline
            )
        )
        stale = list(rows.scalars())
        for booking in stale:
            booking.status = "cancelled"
        await session.commit()
    return len(stale)


async def due_reminders(now: datetime | None = None, ahead: timedelta = timedelta(hours=2)):
    now = now or datetime.now(UTC)
    async with Session() as session:
        rows = await session.execute(
            select(Booking).where(
                Booking.status == "confirmed",
                Booking.reminded_at.is_(None),
                Booking.start_at > now,
                Booking.start_at <= now + ahead,
            )
        )
        return list(rows.scalars())


async def mark_reminded(booking_id: int) -> None:
    async with Session() as session:
        booking = await session.get(Booking, booking_id)
        booking.reminded_at = datetime.now(UTC)
        await session.commit()


async def add_message(user_id: int, role: str, text: str) -> None:
    async with Session() as session:
        session.add(ChatMessage(user_id=user_id, role=role, text=text[:4000]))
        await session.commit()


async def messages(user_id: int, limit: int = 20) -> list[ChatMessage]:
    async with Session() as session:
        rows = await session.execute(
            select(ChatMessage)
            .where(ChatMessage.user_id == user_id)
            .order_by(ChatMessage.id.desc())
            .limit(limit)
        )
        return list(reversed(rows.scalars().all()))
