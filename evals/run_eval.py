"""Эвалы ИИ-администратора: настоящие диалоги с моделью, проверки — по базе и инструментам.

    python evals/run_eval.py
    python evals/run_eval.py --only запись-целиком

Каждый диалог идёт на чистой sqlite-базе с фиксированным «сейчас» (понедельник, 8 утра):
«завтра» всегда вторник, и ответ модели не зависит от дня запуска. Проверяется то, от чего
зависят деньги студии: вызваны ли нужные инструменты, сколько записей в базе после диалога,
какие события ушли администратору и нет ли в ответе запрещённого (скидки, промпта, борща).
"""

import argparse
import asyncio
import json
import os
import sys
import tempfile
from datetime import datetime, timedelta
from pathlib import Path

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE.parent))
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///" + str(Path(tempfile.mkdtemp()) / "eval.db")

from alembic import command  # noqa: E402
from alembic.config import Config  # noqa: E402
from sqlalchemy import delete  # noqa: E402

import concierge  # noqa: E402
import db  # noqa: E402
from schedule import MSK  # noqa: E402

NOW = datetime(2026, 10, 19, 8, 0, tzinfo=MSK)
TOMORROW = NOW + timedelta(days=1)
RUNS = HERE / "runs"


async def run_case(case: dict) -> dict:
    async with db.Session() as session:
        await session.execute(delete(db.Booking))
        await session.execute(delete(db.ChatMessage))
        await session.commit()
    user = 1000
    if seed := case.get("seed"):
        hour, minute = map(int, seed["time"].split(":"))
        start = TOMORROW.replace(hour=hour, minute=minute)
        await db.book(user, seed["services"], "sedan", start, "Kia K5", "+79991112233")

    tools, events = [], []
    real_call = concierge.Tools.call

    async def spy(self, name, args):
        tools.append(name)
        return await real_call(self, name, args)

    async def on_event(kind, subject):
        events.append(kind)

    concierge.Tools.call = spy
    answers = []
    try:
        for turn in case["turns"]:
            answers.append(await concierge.reply(user, turn, on_event=on_event, now=NOW))
    finally:
        concierge.Tools.call = real_call

    live = [b for b in await db.mine(user) if b.status != "cancelled"]
    expect, last, text = case["expect"], answers[-1], " ".join(answers)
    checks = {}
    if "booked" in expect:
        checks["записей"] = len(live) == expect["booked"]
    for name in expect.get("tools", []):
        checks[f"инструмент {name}"] = name in tools
    for kind in expect.get("events", []):
        checks[f"событие {kind}"] = kind in events
    if "say_any" in expect:
        checks["в ответе"] = any(s.lower() in last.lower() for s in expect["say_any"])
    for bad in expect.get("not_say", []):
        checks[f"нет «{bad}»"] = bad.lower() not in text.lower()
    return {
        "id": case["id"],
        "checks": checks,
        "answers": answers,
        "tools": tools,
        "events": events,
    }


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--only")
    args = parser.parse_args()
    await asyncio.to_thread(command.upgrade, Config(str(HERE.parent / "alembic.ini")), "head")

    cases = [json.loads(line) for line in (HERE / "cases.jsonl").read_text("utf-8").splitlines()]
    cases = [c for c in cases if not args.only or c["id"] == args.only]
    results = []
    for case in cases:
        try:
            result = await run_case(case)
        except Exception as e:
            result = {"id": case["id"], "checks": {"без ошибок": False}, "error": repr(e)}
        results.append(result)
        ok = all(result["checks"].values())
        failed = [k for k, v in result["checks"].items() if not v]
        print(f"{'OK  ' if ok else 'FAIL'} {result['id']:<20} {', '.join(failed)}")

    passed = sum(all(r["checks"].values()) for r in results)
    total_checks = sum(len(r["checks"]) for r in results)
    good_checks = sum(sum(r["checks"].values()) for r in results)
    print(f"\nДиалогов прошло: {passed} из {len(results)} ({passed / len(results) * 100:.0f}%)")
    print(f"Проверок прошло: {good_checks} из {total_checks}")
    RUNS.mkdir(exist_ok=True)
    path = RUNS / f"{datetime.now():%Y-%m-%d_%H-%M-%S}.json"
    path.write_text(json.dumps(results, ensure_ascii=False, indent=2), "utf-8")
    print(f"Сохранено: {path.relative_to(HERE.parent)}")


if __name__ == "__main__":
    asyncio.run(main())
