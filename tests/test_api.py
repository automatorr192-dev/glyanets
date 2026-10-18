"""API записи: кто записывается — только из подписи Telegram, цену и время считает сервер."""

import hashlib
import hmac
import json
import time
from datetime import datetime, timedelta
from urllib.parse import urlencode

import pytest
from fastapi.testclient import TestClient

import app as server
import bot as tg
import db
from schedule import MSK

TOMORROW = (datetime.now(MSK) + timedelta(days=1)).date().isoformat()


def init_data(user_id: int, token: str = "123:test") -> str:
    fields = {
        "auth_date": str(int(time.time())),
        "query_id": "AAH",
        "user": json.dumps({"id": user_id, "first_name": "Полина"}),
    }
    check = "\n".join(f"{k}={fields[k]}" for k in sorted(fields))
    secret = hmac.new(b"WebAppData", token.encode(), hashlib.sha256).digest()
    fields["hash"] = hmac.new(secret, check.encode(), hashlib.sha256).hexdigest()
    return urlencode(fields)


def as_user(user_id: int) -> dict:
    return {"X-Init-Data": init_data(user_id)}


ORDER = {
    "services": ["polish", "ceramic"],
    "cls": "suv",
    "day": TOMORROW,
    "time": "10:00",
    "car": "Kia Sportage",
    "phone": "+7 999 000-00-00",
    "total": 1,
}


@pytest.fixture
def api(database, monkeypatch):
    events = []

    async def record(kind, subject):
        events.append((kind, subject.id))

    monkeypatch.setattr(tg, "on_event", record)
    http = TestClient(server.app)
    http.events = events
    return http


def test_without_telegram_signature_nobody_books(api):
    assert api.post("/api/bookings", json=ORDER).status_code == 401
    forged = {"X-Init-Data": init_data(1, token="999:other")}
    assert api.post("/api/bookings", json=ORDER, headers=forged).status_code == 401


def test_server_sets_the_price_not_the_phone(api):
    response = api.post("/api/bookings", json=ORDER, headers=as_user(1))

    assert response.status_code == 201
    booking = response.json()
    assert booking["total"] == 22000 + 34000 - 5600
    assert booking["status"] == "confirmed"
    assert datetime.fromisoformat(booking["ready"]) > datetime.fromisoformat(booking["start"])
    assert api.events == [("booked", int(booking["id"]))]


def test_impossible_time_is_refused(api):
    late = {**ORDER, "time": "15:00"}

    assert api.post("/api/bookings", json=late, headers=as_user(1)).status_code == 422


def test_full_slot_is_a_conflict(api):
    for user in (1, 2):
        assert api.post("/api/bookings", json=ORDER, headers=as_user(user)).status_code == 201

    assert api.post("/api/bookings", json=ORDER, headers=as_user(3)).status_code == 409
    slots = api.get(
        "/api/slots", params={"day": TOMORROW, "cls": "suv", "services": "polish,ceramic"}
    ).json()["slots"]
    assert {s["time"]: s["free"] for s in slots}["10:00"] is False


def test_people_see_and_touch_only_their_bookings(api):
    booking = api.post("/api/bookings", json=ORDER, headers=as_user(1)).json()

    assert api.get("/api/bookings", headers=as_user(2)).json() == []
    assert api.delete(f"/api/bookings/{booking['id']}", headers=as_user(2)).status_code == 404
    move = {"day": TOMORROW, "time": "11:00"}
    assert (
        api.patch(f"/api/bookings/{booking['id']}", json=move, headers=as_user(2)).status_code
        == 404
    )
    assert [b["id"] for b in api.get("/api/bookings", headers=as_user(1)).json()] == [booking["id"]]


def test_move_and_cancel(api):
    booking = api.post("/api/bookings", json=ORDER, headers=as_user(1)).json()

    moved = api.patch(
        f"/api/bookings/{booking['id']}",
        json={"day": TOMORROW, "time": "11:00"},
        headers=as_user(1),
    ).json()
    assert datetime.fromisoformat(moved["start"]).astimezone(MSK).hour == 11

    cancelled = api.delete(f"/api/bookings/{booking['id']}", headers=as_user(1)).json()
    assert cancelled["cancelled"] is True
    assert [kind for kind, _ in api.events] == ["booked", "moved", "cancelled"]


def test_prepayment_returns_an_invoice_and_waits(api, monkeypatch):
    async def link(booking):
        return f"https://rollypay.io/pay/{booking.id}"

    monkeypatch.setattr(tg, "PREPAY_PERCENT", 20)
    monkeypatch.setattr(tg, "pay_link", link)

    booking = api.post("/api/bookings", json=ORDER, headers=as_user(1)).json()

    assert booking["status"] == "awaiting_payment"
    assert booking["prepay"] == 10100
    assert booking["invoice"] == f"https://rollypay.io/pay/{booking['id']}"
    assert api.events == []
    assert api.get("/api/config").json() == {"prepay_percent": 20}


def test_slots_need_known_services(api):
    response = api.get("/api/slots", params={"day": TOMORROW, "cls": "suv", "services": "magic"})

    assert response.status_code == 422


async def test_health_checks_the_database(api):
    assert api.get("/health").json() == {"status": "ok"}
    assert await db.mine(1) == []
