"""Боты: напоминание за 2 часа, отмена кнопкой, предоплата, MAX. Сеть не трогаем:
Telegram подменён записью вызовов, MAX — httpx.MockTransport."""

import json
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace as NS

import httpx
import pytest

import bot as tg
import concierge
import db
import maxbot
from schedule import MSK

START = datetime.now(MSK).replace(minute=0, second=0, microsecond=0) + timedelta(days=1)


async def booking(user=1, **kwargs):
    start = START.replace(hour=10)
    return await db.book(user, ["wash"], "sedan", start, "Kia K5", "+79990000000", **kwargs)


class Answer:
    def __init__(self):
        self.calls = []

    async def __call__(self, *args, **kwargs):
        self.calls.append((args, kwargs))


@pytest.fixture
def admin(monkeypatch):
    got = []

    async def notify(text):
        got.append(text)

    monkeypatch.setattr(tg, "notify_admin", notify)
    return got


async def test_reminders_go_to_the_right_messenger_once(database, monkeypatch):
    telegram, maximum = await booking(1), await booking(maxbot.uid(55))
    sent = []

    async def remind_tg(b):
        sent.append(("tg", b.id))
        return True

    async def remind_max(b):
        sent.append(("max", b.id))
        return True

    real = db.due_reminders

    async def due():
        return await real(db.aware(telegram.start_at) - timedelta(hours=1))

    monkeypatch.setattr(tg, "remind", remind_tg)
    monkeypatch.setattr(db, "due_reminders", due)

    await tg.tick(remind_max)
    await tg.tick(remind_max)

    assert sorted(sent) == sorted([("tg", telegram.id), ("max", maximum.id)])


async def test_reminder_buttons_move_and_cancel(database):
    keyboard = tg.reminder_keyboard(await booking())

    move, cancel = keyboard.inline_keyboard[0][0], keyboard.inline_keyboard[1][0]
    assert move.web_app.url.endswith("?move=1")
    assert cancel.callback_data == "cancel:1"


async def test_cancel_button_cancels_only_own_booking(database, admin):
    mine = await booking(1)
    answer, edit = Answer(), Answer()
    query = NS(
        data=f"cancel:{mine.id}", from_user=NS(id=2), answer=answer, message=NS(edit_text=edit)
    )

    await tg.cancel_from_reminder(query)
    assert (await db.get(mine.id)).status == "confirmed"

    query.from_user = NS(id=1)
    await tg.cancel_from_reminder(query)
    assert (await db.get(mine.id)).status == "cancelled"
    assert edit.calls and "отменена" in admin[-1]


async def test_checkout_only_for_a_live_hold_of_the_payer(database):
    hold = await booking(1, prepay_percent=20)
    answer = Answer()

    await tg.pre_checkout(
        NS(invoice_payload=f"booking:{hold.id}", from_user=NS(id=2), answer=answer)
    )
    await tg.pre_checkout(
        NS(invoice_payload=f"booking:{hold.id}", from_user=NS(id=1), answer=answer)
    )

    assert [kwargs["ok"] for _, kwargs in answer.calls] == [False, True]


async def test_payment_confirms_the_booking(database, admin):
    hold = await booking(1, prepay_percent=20)
    reply = Answer()
    message = NS(successful_payment=NS(invoice_payload=f"booking:{hold.id}"), answer=reply)

    await tg.paid(message)

    assert (await db.get(hold.id)).status == "confirmed"
    assert "Предоплата получена" in reply.calls[0][0][0]
    assert "Предоплата получена" in admin[-1]


async def test_expired_hold_frees_the_time(database, monkeypatch):
    hold = await booking(1, prepay_percent=20)
    real = db.expire_holds

    async def later():
        return await real(datetime.now(UTC) + timedelta(minutes=20))

    monkeypatch.setattr(db, "expire_holds", later)
    await tg.tick()

    assert (await db.get(hold.id)).status == "cancelled"


async def test_admin_message_says_what_and_when(database, admin):
    await tg.on_event("booked", await booking())

    assert "Новая запись" in admin[0] and "Детейлинг-мойка" in admin[0] and "2 500 ₽" in admin[0]


@pytest.fixture
def max_api():
    requests = []

    def handler(request: httpx.Request):
        requests.append(request)
        return httpx.Response(200, json={})

    http = httpx.AsyncClient(base_url=maxbot.API, transport=httpx.MockTransport(handler))
    http.requests = requests
    return http


async def test_max_chat_goes_to_the_same_concierge(database, monkeypatch, max_api):
    seen = []

    async def fake_reply(user_id, text, **kwargs):
        seen.append((user_id, text, kwargs["source"]))
        return "Керамика на кроссовер — 34 000 ₽."

    monkeypatch.setattr(concierge, "reply", fake_reply)
    update = {
        "update_type": "message_created",
        "message": {
            "body": {"text": "Сколько керамика?"},
            "sender": {"user_id": 55},
            "recipient": {"chat_id": 900},
        },
    }

    await maxbot.handle(max_api, update)

    assert seen == [(-55, "Сколько керамика?", "max")]
    sent = max_api.requests[0]
    assert sent.url.params["chat_id"] == "900"
    assert json.loads(sent.content)["text"] == "Керамика на кроссовер — 34 000 ₽."


async def test_max_cancel_button(database, admin, max_api):
    mine = await booking(maxbot.uid(55))
    update = {
        "update_type": "message_callback",
        "callback": {"payload": f"cancel:{mine.id}", "user": {"user_id": 55}, "callback_id": "cb"},
    }

    await maxbot.handle(max_api, update)

    assert (await db.get(mine.id)).status == "cancelled"
    assert json.loads(max_api.requests[0].content)["notification"] == "Запись отменена."
