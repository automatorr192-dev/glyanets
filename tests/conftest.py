import os

os.environ["BOT_TOKEN"] = "123:test"
os.environ.setdefault("OPENROUTER_API_KEY", "test")

import asyncio  # noqa: E402

import pytest  # noqa: E402
from alembic import command  # noqa: E402
from alembic.config import Config  # noqa: E402

import db  # noqa: E402

# Задан — тесты идут на Postgres (так в CI): EXCLUDE-ограничение на пересечение записей
# есть только там. Иначе — sqlite-файл.
POSTGRES = os.environ.get("TEST_DATABASE_URL", "").replace(
    "postgresql://", "postgresql+asyncpg://", 1
)


@pytest.fixture
async def database(tmp_path, monkeypatch):
    url = POSTGRES or f"sqlite+aiosqlite:///{tmp_path / 'test.db'}"
    monkeypatch.setenv("DATABASE_URL", url)

    from sqlalchemy import text
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
    from sqlalchemy.pool import NullPool

    engine = create_async_engine(url, future=True, poolclass=NullPool if POSTGRES else None)
    if POSTGRES:
        async with engine.begin() as connection:
            await connection.execute(text("drop schema public cascade"))
            await connection.execute(text("create schema public"))
    monkeypatch.setattr(db, "engine", engine)
    monkeypatch.setattr(db, "Session", async_sessionmaker(engine, expire_on_commit=False))

    config = Config(os.path.join(os.path.dirname(__file__), "..", "alembic.ini"))
    await asyncio.to_thread(command.upgrade, config, "head")
    yield
    await engine.dispose()
