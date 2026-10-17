"""Записи в боксы и переписка с ИИ-администратором

Revision ID: 0001
Revises:
Create Date: 2026-10-17
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _postgres() -> bool:
    return op.get_bind().dialect.name == "postgresql"


def upgrade() -> None:
    op.create_table(
        "bookings",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("user_id", sa.BigInteger, nullable=False),
        sa.Column("name", sa.String(100)),
        sa.Column("phone", sa.String(20), nullable=False),
        sa.Column("car", sa.String(100), nullable=False),
        sa.Column("plate", sa.String(20)),
        sa.Column("services", sa.String(100), nullable=False),
        sa.Column("car_class", sa.String(10), nullable=False),
        sa.Column("start_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ready_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("box", sa.SmallInteger, nullable=False),
        sa.Column("total", sa.Integer, nullable=False),
        sa.Column("prepay", sa.Integer, nullable=False, server_default="0"),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("source", sa.String(10), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("paid_at", sa.DateTime(timezone=True)),
        sa.Column("reminded_at", sa.DateTime(timezone=True)),
        sa.CheckConstraint(
            "status in ('awaiting_payment', 'confirmed', 'cancelled')", name="ck_bookings_status"
        ),
        sa.CheckConstraint("ready_at > start_at", name="ck_bookings_period"),
        sa.CheckConstraint("total >= 0 and prepay >= 0", name="ck_bookings_money"),
    )
    op.create_index("ix_bookings_user_id", "bookings", ["user_id"])
    op.create_index("ix_bookings_start_at", "bookings", ["start_at"])
    if _postgres():
        # Главная гарантия расписания: две живые записи одного бокса не пересекаются по
        # времени. btree_gist нужен, чтобы в одном индексе сравнивать и бокс (=), и
        # интервал (&&). Отменённые записи время не держат.
        op.execute("create extension if not exists btree_gist")
        op.execute(
            "alter table bookings add constraint ex_bookings_box_time exclude using gist "
            "(box with =, tstzrange(start_at, ready_at) with &&) where (status <> 'cancelled')"
        )

    op.create_table(
        "chat_messages",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("user_id", sa.BigInteger, nullable=False),
        sa.Column("role", sa.String(10), nullable=False),
        sa.Column("text", sa.Text, nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint("role in ('client', 'admin')", name="ck_chat_role"),
    )
    op.create_index("ix_chat_messages_user_id", "chat_messages", ["user_id"])


def downgrade() -> None:
    op.drop_table("chat_messages")
    op.drop_table("bookings")
