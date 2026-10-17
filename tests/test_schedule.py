"""Правила расписания — те же, что в мини-аппе: цены, скидка за комплекс, начала, готовность."""

from datetime import date, datetime, timedelta

import pytest

import schedule
from schedule import MSK, BadOrder


def test_bundle_discount_is_ten_percent_of_polish_and_ceramic():
    price = schedule.quote(["ceramic", "polish", "wash"], "suv")

    assert price["services"] == ["wash", "polish", "ceramic"]
    assert price["subtotal"] == 2900 + 22000 + 34000
    assert price["discount"] == 5600
    assert price["total"] == price["subtotal"] - 5600
    assert price["hours"] == 17.5


@pytest.mark.parametrize(
    ("ids", "car_class"),
    [([], "sedan"), (["wash", "wash"], "sedan"), (["teleport"], "sedan"), (["wash"], "bus")],
)
def test_bad_orders_are_refused(ids, car_class):
    with pytest.raises(BadOrder):
        schedule.quote(ids, car_class)


def test_short_jobs_start_every_half_hour_and_end_before_closing():
    times = [s.strftime("%H:%M") for s in schedule.starts(date(2026, 10, 20), 1.5)]

    assert times[0] == "09:00" and times[1] == "09:30"
    assert times[-1] == "19:00"


def test_long_jobs_start_only_in_the_morning():
    times = [s.strftime("%H:%M") for s in schedule.starts(date(2026, 10, 20), 8)]

    assert times == ["09:00", "10:00", "11:00"]


def test_work_continues_next_morning():
    start = datetime(2026, 10, 20, 11, 0, tzinfo=MSK)

    assert schedule.ready_at(start, 16) == datetime(2026, 10, 21, 15, 0, tzinfo=MSK)
    assert schedule.ready_at(start, 1.5) == datetime(2026, 10, 20, 12, 30, tzinfo=MSK)


def test_start_must_be_a_real_slot_in_the_future_and_within_two_weeks():
    now = datetime(2026, 10, 20, 12, 0, tzinfo=MSK)

    assert schedule.parse_start("2026-10-21", "09:30", 1.5, now).hour == 9
    assert schedule.parse_start("2026-10-20", "13:00", 1.5, now) - now == timedelta(hours=1)
    for day, at in (("2026-10-21", "09:15"), ("2026-10-20", "12:30"), ("2026-11-20", "10:00")):
        with pytest.raises(BadOrder):
            schedule.parse_start(day, at, 1.5, now)
    with pytest.raises(BadOrder):
        schedule.parse_start("2026-10-21", "15:00", 8, now)


@pytest.mark.parametrize(
    ("total", "percent", "prepay"),
    [(46000, 20, 9200), (2500, 20, 500), (300, 20, 300), (9000, 0, 0)],
)
def test_prepayment(total, percent, prepay):
    assert schedule.prepayment(total, percent) == prepay
