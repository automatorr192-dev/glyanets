"""Запись в боксы: свободное время, перенос, отмена, предоплата и гонка за один слот."""

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import insert
from sqlalchemy.exc import IntegrityError

import db
from conftest import POSTGRES
from schedule import MSK

NOW = datetime(2026, 10, 20, 8, 0, tzinfo=MSK)
DAY = NOW.date() + timedelta(days=1)
NINE = datetime(DAY.year, DAY.month, DAY.day, 9, 0, tzinfo=MSK)


async def wash(user=1, start=NINE, **kwargs):
    return await db.book(user, ["wash"], "sedan", start, "Kia K5", "+79990000000", **kwargs)


async def test_two_boxes_take_two_cars_at_once(database):
    first, second = await wash(1), await wash(2)

    assert {first.box, second.box} == {1, 2}
    with pytest.raises(db.Taken):
        await wash(3)


async def test_free_starts_count_boxes(database):
    await wash(1)
    slots = {s["time"]: s["free"] for s in await db.free_starts(DAY, ["wash"], "sedan", NOW)}
    assert slots["09:00"] is True

    await wash(2)
    slots = {s["time"]: s["free"] for s in await db.free_starts(DAY, ["wash"], "sedan", NOW)}
    assert slots["09:00"] is False
    assert slots["09:30"] is False
    assert slots["10:30"] is True


async def test_cancelled_time_is_free_again(database):
    first, _ = await wash(1), await wash(2)

    await db.cancel(first.id, 1)

    assert (await wash(3)).box == first.box


async def test_only_owner_cancels_and_sees(database):
    booking = await wash(1)

    assert await db.cancel(booking.id, 2) is None
    assert await db.get(booking.id, 2) is None
    assert [b.id for b in await db.mine(1)] == [booking.id]
    assert await db.mine(2) == []


async def test_reschedule_moves_and_keeps_others_safe(database):
    later = NINE + timedelta(hours=3)
    mine = await wash(1)
    await wash(2, start=later)

    moved = await db.reschedule(mine.id, 1, later)

    assert db.aware(moved.start_at) == later and moved.reminded_at is None
    assert {b.box for b in await db.mine(1) + await db.mine(2)} == {1, 2}


async def test_reschedule_into_a_full_slot_is_refused(database):
    later = NINE + timedelta(hours=3)
    mine = await wash(1)
    await wash(2, start=later)
    await wash(3, start=later)

    with pytest.raises(db.Taken):
        await db.reschedule(mine.id, 1, later)


async def test_prepayment_holds_the_slot_until_paid(database):
    booking = await db.book(
        1, ["polish", "ceramic"], "sedan", NINE, "Kia K5", "+79990000000", prepay_percent=20
    )
    assert booking.status == "awaiting_payment" and booking.prepay == 8300

    paid = await db.mark_paid(booking.id)
    assert paid.status == "confirmed" and paid.paid_at is not None
    assert await db.mark_paid(booking.id) is None


async def test_unpaid_hold_expires(database):
    booking = await wash(1, prepay_percent=20)

    assert await db.expire_holds(datetime.now(UTC) + timedelta(minutes=16)) == 1
    assert (await db.get(booking.id)).status == "cancelled"


async def test_reminder_is_due_two_hours_before(database):
    booking = await wash(1)
    start = db.aware(booking.start_at)

    assert await db.due_reminders(start - timedelta(hours=3)) == []
    assert [b.id for b in await db.due_reminders(start - timedelta(hours=1))] == [booking.id]

    await db.mark_reminded(booking.id)
    assert await db.due_reminders(start - timedelta(hours=1)) == []


@pytest.mark.skipif(not POSTGRES, reason="EXCLUDE-ограничение есть только в Postgres")
async def test_database_refuses_overlap_even_when_code_misses_it(database, monkeypatch):
    """Гонка: оба запроса увидели свободный бокс. Код ошибся — база должна не пустить."""

    async def blind(*args, **kwargs):
        return set()

    monkeypatch.setattr(db, "BOXES", 1)
    first = await wash(1)
    monkeypatch.setattr(db, "busy_boxes", blind)

    with pytest.raises(db.Taken):
        await wash(2)

    async with db.Session() as session:
        with pytest.raises(IntegrityError):
            await session.execute(
                insert(db.Booking).values(
                    user_id=3,
                    phone="+7",
                    car="X",
                    services="wash",
                    car_class="sedan",
                    start_at=first.start_at,
                    ready_at=first.ready_at,
                    box=1,
                    total=1,
                    status="confirmed",
                    source="app",
                )
            )
            await session.commit()
