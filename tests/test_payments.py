"""Предоплата через RollyPay: создание платежа, подпись уведомления, подтверждение записи.
Сеть подменена httpx.MockTransport, Telegram — записью вызовов."""

import hashlib
import hmac
import json
import time
from datetime import datetime, timedelta

import httpx
import pytest
from fastapi.testclient import TestClient

import app as server
import bot as tg
import db
import maxbot
import payments
from schedule import MSK

SECRET = "whsec_test"


@pytest.fixture(autouse=True)
def cashbox(monkeypatch):
    monkeypatch.setattr(payments, "API_KEY", "rpk_test")
    monkeypatch.setattr(payments, "SECRET", SECRET)
    monkeypatch.setattr(payments, "TEST", True)


def signed(event: dict, secret: str = SECRET, at: int | None = None) -> tuple[bytes, dict]:
    body = json.dumps(event).encode()
    stamp = str(at or int(time.time()))
    signature = hmac.new(secret.encode(), f"{stamp}.".encode() + body, hashlib.sha256).hexdigest()
    return body, {
        "X-Timestamp": stamp,
        "X-Signature": signature,
        "Content-Type": "application/json",
    }


async def hold(user=1):
    start = (datetime.now(MSK) + timedelta(days=1)).replace(
        hour=10, minute=0, second=0, microsecond=0
    )
    return await db.book(
        user, ["polish"], "sedan", start, "Kia K5", "+79990000000", prepay_percent=20
    )


def paid_event(booking, **extra) -> dict:
    return {
        "event_type": "payment.paid",
        "payment_id": "pay_1",
        "order_id": payments.order_id(booking.id),
        "status": "paid",
        "amount": f"{booking.prepay}.00",
        "currency": "RUB",
        "test": True,
    } | extra


@pytest.fixture
def told(monkeypatch):
    got = []

    async def tell(user_id, text):
        got.append((user_id, text))

    async def event(kind, subject):
        got.append((kind, getattr(subject, "id", subject)))

    monkeypatch.setattr(tg, "tell", tell)
    monkeypatch.setattr(maxbot, "tell", tell)
    monkeypatch.setattr(tg, "on_event", event)
    return got


async def test_payment_is_created_with_key_nonce_and_test_flag(monkeypatch):
    seen = []

    def handler(request: httpx.Request):
        seen.append(request)
        return httpx.Response(
            200, json={"payment_id": "pay_1", "pay_url": "https://rollypay.io/p/1"}
        )

    monkeypatch.setattr(payments, "TRANSPORT", httpx.MockTransport(handler))

    url = await payments.create(42, 3600, "Предоплата", "https://t.me/glyanets_bot")

    assert url == "https://rollypay.io/p/1"
    request = seen[0]
    body = json.loads(request.content)
    assert request.url.path == "/api/v1/payments"
    assert request.headers["X-API-Key"] == "rpk_test" and len(request.headers["X-Nonce"]) == 36
    assert body["amount"] == "3600.00" and body["order_id"] == "booking-42" and body["test"] is True


async def test_refused_payment_is_an_error(monkeypatch):
    monkeypatch.setattr(
        payments, "TRANSPORT", httpx.MockTransport(lambda r: httpx.Response(401, json={}))
    )

    with pytest.raises(payments.PaymentError):
        await payments.create(42, 3600, "Предоплата")


def test_signature_checks():
    body, headers = signed({"a": 1})
    payments.verify(body, headers["X-Timestamp"], headers["X-Signature"])

    for bad_body, stamp, signature in (
        (body + b" ", headers["X-Timestamp"], headers["X-Signature"]),
        (body, headers["X-Timestamp"], "0" * 64),
        (body, None, headers["X-Signature"]),
    ):
        with pytest.raises(payments.BadSignature):
            payments.verify(bad_body, stamp, signature)

    old_body, old = signed({"a": 1}, at=int(time.time()) - 3600)
    with pytest.raises(payments.BadSignature):
        payments.verify(old_body, old["X-Timestamp"], old["X-Signature"])


async def test_paid_callback_confirms_and_tells_everyone(database, told):
    booking = await hold(1)
    body, headers = signed(paid_event(booking))

    response = TestClient(server.app).post("/api/payments/rollypay", content=body, headers=headers)

    assert response.status_code == 200
    assert (await db.get(booking.id)).status == "confirmed"
    assert ("paid", booking.id) in told
    assert any(user == 1 and "Предоплата получена" in str(text) for user, text in told)


async def test_repeated_callback_does_nothing_twice(database, told):
    booking = await hold(1)
    body, headers = signed(paid_event(booking))
    http = TestClient(server.app)

    http.post("/api/payments/rollypay", content=body, headers=headers)
    http.post("/api/payments/rollypay", content=body, headers=headers)

    assert told.count(("paid", booking.id)) == 1


async def test_forged_or_wrong_callbacks_do_not_confirm(database, told, monkeypatch):
    booking = await hold(1)
    http = TestClient(server.app)

    forged_body, forged = signed(paid_event(booking), secret="другой")
    assert (
        http.post("/api/payments/rollypay", content=forged_body, headers=forged).status_code == 401
    )

    cheap_body, cheap = signed(paid_event(booking, amount="1.00"))
    assert http.post("/api/payments/rollypay", content=cheap_body, headers=cheap).status_code == 200

    monkeypatch.setattr(payments, "TEST", False)
    test_body, test = signed(paid_event(booking))
    assert http.post("/api/payments/rollypay", content=test_body, headers=test).status_code == 200

    assert (await db.get(booking.id)).status == "awaiting_payment"
    assert told == []


async def test_payment_after_expired_hold_reaches_the_admin(database, told):
    booking = await hold(1)
    await db.cancel(booking.id)
    body, headers = signed(paid_event(booking))

    TestClient(server.app).post("/api/payments/rollypay", content=body, headers=headers)

    assert told and told[0][0] == "handoff" and "+79990000000" in told[0][1]


async def test_max_client_hears_about_payment_in_max(database, told):
    booking = await hold(maxbot.uid(55))
    body, headers = signed(paid_event(booking))

    TestClient(server.app).post("/api/payments/rollypay", content=body, headers=headers)

    assert any(user == -55 for user, _ in told)


async def test_payment_link_failure_frees_the_slot(database, monkeypatch):
    from test_api import ORDER, as_user

    async def broken(booking):
        raise payments.PaymentError("RollyPay ответил 500")

    monkeypatch.setattr(tg, "PREPAY_PERCENT", 20)
    monkeypatch.setattr(tg, "pay_link", broken)

    response = TestClient(server.app).post("/api/bookings", json=ORDER, headers=as_user(1))

    assert response.status_code == 502
    assert all(b.status == "cancelled" for b in await db.mine(1))
