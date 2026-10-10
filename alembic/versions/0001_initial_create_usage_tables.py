"""create usage events and collector state tables

Revision ID: 0001_initial
Revises:
Create Date: 2026-10-11

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op
from database.types import UtcDateTime

revision: str = "0001_initial"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "usage_events",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("platform", sa.String(), nullable=False),
        sa.Column("provider_id", sa.String(), nullable=False),
        sa.Column("model_id", sa.String(), nullable=False),
        sa.Column("session_id", sa.String(), nullable=False),
        sa.Column("message_id", sa.String(), nullable=False),
        sa.Column("source_event_id", sa.String(), nullable=False),
        sa.Column("timestamp", UtcDateTime(), nullable=False),
        sa.Column("input_tokens", sa.Integer(), nullable=True),
        sa.Column("output_tokens", sa.Integer(), nullable=True),
        sa.Column("total_tokens", sa.Integer(), nullable=True),
        sa.Column("reasoning_tokens", sa.Integer(), nullable=True),
        sa.Column("cache_read_tokens", sa.Integer(), nullable=True),
        sa.Column("cache_write_tokens", sa.Integer(), nullable=True),
        sa.Column("consumption_tokens", sa.Integer(), nullable=True),
        sa.Column("usage_status", sa.String(), nullable=False),
        sa.Column("cache_overlap", sa.String(), nullable=False),
        sa.Column("reasoning_overlap", sa.String(), nullable=False),
        sa.Column("raw_usage", sa.Text(), nullable=False),
        sa.Column("created_at", UtcDateTime(), nullable=False),
        sa.Column("updated_at", UtcDateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "platform", "source_event_id", name="uq_usage_events_platform_source_event"
        ),
        sa.CheckConstraint(
            "usage_status IN ('reported', 'estimated', 'unavailable')",
            name="ck_usage_events_usage_status",
        ),
        sa.CheckConstraint(
            "(input_tokens IS NULL OR input_tokens >= 0)"
            " AND (output_tokens IS NULL OR output_tokens >= 0)"
            " AND (total_tokens IS NULL OR total_tokens >= 0)",
            name="ck_usage_events_non_negative_tokens",
        ),
    )
    op.create_index("ix_usage_events_timestamp", "usage_events", ["timestamp"])
    op.create_index("ix_usage_events_provider_id", "usage_events", ["provider_id"])
    op.create_index("ix_usage_events_model_id", "usage_events", ["model_id"])
    op.create_index("ix_usage_events_session_id", "usage_events", ["session_id"])
    op.create_index("ix_usage_events_platform_timestamp", "usage_events", ["platform", "timestamp"])

    op.create_table(
        "collector_state",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("platform", sa.String(), nullable=False),
        sa.Column("source_path", sa.Text(), nullable=False),
        sa.Column("checkpoint", sa.Text(), nullable=True),
        sa.Column("last_scan_at", UtcDateTime(), nullable=True),
        sa.Column("status", sa.String(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("platform", name="uq_collector_state_platform"),
        sa.CheckConstraint(
            "status IN ('idle', 'scanning', 'error')",
            name="ck_collector_state_status",
        ),
    )
    op.create_index("ix_collector_state_last_scan_at", "collector_state", ["last_scan_at"])


def downgrade() -> None:
    op.drop_index("ix_collector_state_last_scan_at", table_name="collector_state")
    op.drop_table("collector_state")
    op.drop_index("ix_usage_events_platform_timestamp", table_name="usage_events")
    op.drop_index("ix_usage_events_session_id", table_name="usage_events")
    op.drop_index("ix_usage_events_model_id", table_name="usage_events")
    op.drop_index("ix_usage_events_provider_id", table_name="usage_events")
    op.drop_index("ix_usage_events_timestamp", table_name="usage_events")
    op.drop_table("usage_events")
