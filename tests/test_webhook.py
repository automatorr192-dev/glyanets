"""Вебхук для бесплатного Render: Telegram будит спящий сервер, обработка идёт фоном.

lifespan не запускается — в Telegram и в базу тесты не ходят.
"""

import pytest
from fastapi.testclient import TestClient

import app as server

SECRET = "s3cret"


def update(update_id: int) -> dict:
    return {
        "update_id": update_id,
        "message": {
            "message_id": 1,
            "date": 1,
            "chat": {"id": 42, "type": "private"},
            "from": {"id": 42, "is_bot": False, "first_name": "Полина"},
            "text": "/start",
        },
    }


@pytest.fixture
def hooked(monkeypatch):
    fed = []

    async def feed(bot, received):
        fed.append(received.update_id)

    monkeypatch.setattr(server, "WEBHOOK_SECRET", SECRET)
    monkeypatch.setattr(server, "PUBLIC_URL", "https://glyanets.example")
    monkeypatch.setattr(server.tg.dp, "feed_update", feed)
    return TestClient(server.app), fed


def post(client, body, secret=SECRET):
    return client.post("/telegram", json=body, headers={"X-Telegram-Bot-Api-Secret-Token": secret})


def test_update_without_secret_is_refused(hooked):
    client, fed = hooked
    assert post(client, update(1), secret="guess").status_code == 403
    assert fed == []


def test_update_goes_to_the_bot_once(hooked):
    client, fed = hooked
    assert post(client, update(7)).json() == {"ok": True}
    assert post(client, update(7)).json() == {"ok": True}
    assert post(client, update(8)).status_code == 200
    assert fed == [7, 8]


def test_without_public_address_bot_stays_on_polling(monkeypatch):
    monkeypatch.setattr(server, "WEBHOOK_SECRET", SECRET)
    monkeypatch.setattr(server, "PUBLIC_URL", "")
    assert not server.hooked()
    assert post(TestClient(server.app), update(9)).status_code == 403
