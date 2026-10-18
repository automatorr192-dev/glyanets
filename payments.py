"""Предоплата через RollyPay: ссылка на оплату (СБП, карта) и подписанное уведомление об оплате.

Ссылка открывается и из мини-аппа, и из чата Telegram или MAX — платёжки внутри мессенджера
не нужно. Запись подтверждает не возврат клиента со страницы оплаты (его можно подделать),
а уведомление RollyPay на /api/payments/rollypay: подпись HMAC-SHA256 от «время.тело» на
секрете кассы. Пока ROLLYPAY_TEST не выключен, платежи тестовые: деньги не списываются,
на странице оплаты — кнопки «оплачено» и «не оплачено».
"""

import hashlib
import hmac
import os
import time
import uuid

import httpx

API = os.environ.get("ROLLYPAY_API", "https://rollypay.io").rstrip("/")
API_KEY = os.environ.get("ROLLYPAY_API_KEY", "")
SECRET = os.environ.get("ROLLYPAY_SIGNING_SECRET", "")
TEST = os.environ.get("ROLLYPAY_TEST", "1") != "0"
# Уведомление старше пяти минут — повтор перехваченного запроса, а не свежая оплата.
MAX_SKEW = 300
TRANSPORT: httpx.AsyncBaseTransport | None = None


class PaymentError(Exception):
    pass


class BadSignature(Exception):
    pass


def enabled() -> bool:
    return bool(API_KEY and SECRET)


def order_id(booking_id: int) -> str:
    return f"booking-{booking_id}"


def booking_of(event: dict) -> int | None:
    raw = str(event.get("order_id") or "")
    return (
        int(raw.removeprefix("booking-"))
        if raw.startswith("booking-") and raw[8:].isdigit()
        else None
    )


async def create(booking_id: int, amount: int, description: str, return_url: str = "") -> str:
    body = {
        "amount": f"{amount}.00",
        "payment_currency": "RUB",
        "order_id": order_id(booking_id),
        "description": description[:255],
        "metadata": {"booking_id": booking_id},
        "test": TEST,
    }
    if return_url:
        body["redirect_url"] = return_url
    headers = {"X-API-Key": API_KEY, "X-Nonce": str(uuid.uuid4())}
    async with httpx.AsyncClient(base_url=API, transport=TRANSPORT, timeout=15) as http:
        response = await http.post("/api/v1/payments", json=body, headers=headers)
    if response.status_code != 200:
        raise PaymentError(f"RollyPay ответил {response.status_code}")
    return response.json()["pay_url"]


def verify(body: bytes, timestamp: str | None, signature: str | None, now: float | None = None):
    """Подпись считается от сырого тела: разобранный и заново собранный JSON подпись не сохранит."""
    if not SECRET:
        raise BadSignature("приём оплат не настроен")
    if not timestamp or not signature:
        raise BadSignature("нет подписи")
    try:
        sent_at = int(timestamp)
    except ValueError as e:
        raise BadSignature("время не число") from e
    if abs((now or time.time()) - sent_at) > MAX_SKEW:
        raise BadSignature("уведомление слишком старое")
    expected = hmac.new(SECRET.encode(), f"{timestamp}.".encode() + body, hashlib.sha256)
    if not hmac.compare_digest(expected.hexdigest(), signature):
        raise BadSignature("подпись не сходится")
