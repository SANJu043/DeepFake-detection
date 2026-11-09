"""initial schema

Revision ID: 20261026_0001
Revises:
Create Date: 2026-10-26 00:01:00.000000

Creates all 8 application tables:
  users, videos, jobs, attestations, revocations, shares, anomaly_events, audit_log
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSON, UUID

# ---------------------------------------------------------------------------
# Revision identifiers
# ---------------------------------------------------------------------------

revision: str = "20261026_0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# ---------------------------------------------------------------------------
# Upgrade
# ---------------------------------------------------------------------------

def upgrade() -> None:
    # ── users ────────────────────────────────────────────────────────────────
    op.create_table(
        "users",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("email", sa.String(320), nullable=False),
        sa.Column("display_name", sa.String(128), nullable=False),
        sa.Column("password_hash", sa.String(256), nullable=False),
        sa.Column("role", sa.String(16), nullable=False, server_default="user"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("x25519_public_key", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=True,
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
        ),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)

    # ── videos ───────────────────────────────────────────────────────────────
    op.create_table(
        "videos",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("owner_id", UUID(as_uuid=True), nullable=False),
        sa.Column("filename", sa.String(512), nullable=False),
        sa.Column("content_type", sa.String(64), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("sha256", sa.String(64), nullable=False),
        sa.Column("s3_key", sa.String(1024), nullable=False),
        sa.Column("duration_s", sa.Float(), nullable=True),
        sa.Column("encrypted", sa.Boolean(), server_default=sa.true()),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(
            ["owner_id"], ["users.id"], ondelete="CASCADE"
        ),
    )
    op.create_index("ix_videos_sha256", "videos", ["sha256"], unique=False)
    op.create_index(
        "ix_videos_owner_created", "videos", ["owner_id", "created_at"], unique=False
    )

    # ── jobs ─────────────────────────────────────────────────────────────────
    op.create_table(
        "jobs",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("video_id", UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", UUID(as_uuid=True), nullable=False),
        sa.Column(
            "status", sa.String(24), nullable=False, server_default="pending"
        ),
        sa.Column("celery_task_id", sa.String(128), nullable=True),
        sa.Column("worker_id", sa.String(128), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("result_summary", JSON, nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(
            ["video_id"], ["videos.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], ondelete="CASCADE"
        ),
    )
    op.create_index(
        "ix_jobs_user_status", "jobs", ["user_id", "status"], unique=False
    )

    # ── attestations ─────────────────────────────────────────────────────────
    op.create_table(
        "attestations",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("video_id", UUID(as_uuid=True), nullable=False),
        sa.Column("job_id", UUID(as_uuid=True), nullable=True),
        sa.Column("attestation_id", sa.String(64), nullable=False),
        sa.Column("manifest", JSON, nullable=False),
        sa.Column("signature", sa.Text(), nullable=False),
        sa.Column("public_key_pem", sa.Text(), nullable=False),
        sa.Column("timestamp_token", sa.Text(), nullable=True),
        sa.Column("merkle_leaf_index", sa.Integer(), nullable=True),
        sa.Column("verdict", sa.String(32), nullable=False),
        sa.Column("fake_probability", sa.Float(), nullable=False),
        sa.Column(
            "is_revoked",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(
            ["video_id"], ["videos.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["job_id"], ["jobs.id"], ondelete="SET NULL"
        ),
    )
    op.create_index(
        "ix_attestations_attestation_id",
        "attestations",
        ["attestation_id"],
        unique=True,
    )
    op.create_index(
        "ix_attestations_verdict", "attestations", ["verdict"], unique=False
    )

    # ── revocations ──────────────────────────────────────────────────────────
    op.create_table(
        "revocations",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("attestation_id", sa.String(64), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("revoked_by", UUID(as_uuid=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(
            ["revoked_by"], ["users.id"], ondelete="SET NULL"
        ),
    )
    op.create_index(
        "ix_revocations_attestation_id",
        "revocations",
        ["attestation_id"],
        unique=False,
    )

    # ── shares ───────────────────────────────────────────────────────────────
    op.create_table(
        "shares",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("attestation_id", sa.String(64), nullable=False),
        sa.Column("sender_id", UUID(as_uuid=True), nullable=False),
        sa.Column("recipient_id", UUID(as_uuid=True), nullable=False),
        sa.Column("envelope", JSON, nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(
            ["sender_id"], ["users.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["recipient_id"], ["users.id"], ondelete="CASCADE"
        ),
    )
    op.create_index(
        "ix_shares_attestation_id", "shares", ["attestation_id"], unique=False
    )
    op.create_index(
        "ix_shares_recipient", "shares", ["recipient_id"], unique=False
    )

    # ── anomaly_events ───────────────────────────────────────────────────────
    op.create_table(
        "anomaly_events",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("event_id", sa.String(64), nullable=False),
        sa.Column("subject_type", sa.String(16), nullable=False),
        sa.Column("subject_id", sa.String(128), nullable=False),
        sa.Column("alert_level", sa.Integer(), nullable=False),
        sa.Column("action", sa.String(64), nullable=False),
        sa.Column("anomaly_score", sa.Float(), nullable=False),
        sa.Column("features", JSON, nullable=True),
        sa.Column("rule_hits", JSON, nullable=True),
        sa.Column(
            "resolved",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index(
        "ix_anomaly_events_event_id", "anomaly_events", ["event_id"], unique=True
    )
    op.create_index(
        "ix_anomaly_subject",
        "anomaly_events",
        ["subject_type", "subject_id"],
        unique=False,
    )

    # ── audit_log ────────────────────────────────────────────────────────────
    op.create_table(
        "audit_log",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("user_id", UUID(as_uuid=True), nullable=True),
        sa.Column("action", sa.String(64), nullable=False),
        sa.Column("resource_type", sa.String(32), nullable=True),
        sa.Column("resource_id", sa.String(128), nullable=True),
        sa.Column("ip_address", sa.String(45), nullable=True),
        sa.Column("user_agent", sa.String(512), nullable=True),
        sa.Column("details", JSON, nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index(
        "ix_audit_user_action", "audit_log", ["user_id", "action"], unique=False
    )
    op.create_index(
        "ix_audit_created", "audit_log", ["created_at"], unique=False
    )


# ---------------------------------------------------------------------------
# Downgrade
# ---------------------------------------------------------------------------

def downgrade() -> None:
    # Drop in reverse dependency order

    # audit_log — no foreign keys pointing to other app tables
    op.drop_index("ix_audit_created", table_name="audit_log")
    op.drop_index("ix_audit_user_action", table_name="audit_log")
    op.drop_table("audit_log")

    # anomaly_events
    op.drop_index("ix_anomaly_subject", table_name="anomaly_events")
    op.drop_index("ix_anomaly_events_event_id", table_name="anomaly_events")
    op.drop_table("anomaly_events")

    # shares
    op.drop_index("ix_shares_recipient", table_name="shares")
    op.drop_index("ix_shares_attestation_id", table_name="shares")
    op.drop_table("shares")

    # revocations
    op.drop_index("ix_revocations_attestation_id", table_name="revocations")
    op.drop_table("revocations")

    # attestations
    op.drop_index("ix_attestations_verdict", table_name="attestations")
    op.drop_index("ix_attestations_attestation_id", table_name="attestations")
    op.drop_table("attestations")

    # jobs
    op.drop_index("ix_jobs_user_status", table_name="jobs")
    op.drop_table("jobs")

    # videos
    op.drop_index("ix_videos_owner_created", table_name="videos")
    op.drop_index("ix_videos_sha256", table_name="videos")
    op.drop_table("videos")

    # users
    op.drop_index("ix_users_email", table_name="users")
    op.drop_table("users")
