"""
SQLAlchemy ORM models.

Tables:
- ``users``: user accounts with Argon2 password hashes and RBAC roles.
- ``videos``: uploaded video metadata, S3 object key, and encryption info.
- ``jobs``: detection pipeline job tracking (status, worker, timing).
- ``attestations``: signed manifest JSON, signature, timestamp, Merkle proof.
- ``revocations``: revoked attestation records.
- ``shares``: encrypted sharing envelopes between users.
- ``anomaly_events``: anomaly / threat alerts from the Isolation Forest + rules.
- ``audit_log``: immutable event log for every security-relevant action.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import JSON, UUID
from sqlalchemy.orm import relationship

from backend.app.core.database import Base


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _uuid() -> uuid.UUID:
    return uuid.uuid4()


# ---------------------------------------------------------------------------
# Users
# ---------------------------------------------------------------------------

class User(Base):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    email = Column(String(320), unique=True, nullable=False, index=True)
    display_name = Column(String(128), nullable=False)
    password_hash = Column(String(256), nullable=False)
    role = Column(String(16), nullable=False, default="user")  # user | admin
    is_active = Column(Boolean, default=True, nullable=False)
    x25519_public_key = Column(Text, nullable=True)  # base64 for sharing
    created_at = Column(DateTime(timezone=True), default=_utcnow, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow)

    # Relationships
    videos = relationship("Video", back_populates="owner", lazy="selectin")
    jobs = relationship("Job", back_populates="user", lazy="selectin")


# ---------------------------------------------------------------------------
# Videos
# ---------------------------------------------------------------------------

class Video(Base):
    __tablename__ = "videos"

    id = Column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    owner_id = Column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    filename = Column(String(512), nullable=False)
    content_type = Column(String(64), nullable=False)
    size_bytes = Column(Integer, nullable=False)
    sha256 = Column(String(64), nullable=False, index=True)
    s3_key = Column(String(1024), nullable=False)
    duration_s = Column(Float, nullable=True)
    encrypted = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), default=_utcnow, nullable=False)

    # Relationships
    owner = relationship("User", back_populates="videos")
    jobs = relationship("Job", back_populates="video", lazy="selectin")
    attestations = relationship("Attestation", back_populates="video", lazy="selectin")

    __table_args__ = (
        Index("ix_videos_owner_created", "owner_id", "created_at"),
    )


# ---------------------------------------------------------------------------
# Jobs (detection pipeline)
# ---------------------------------------------------------------------------

class Job(Base):
    __tablename__ = "jobs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    video_id = Column(
        UUID(as_uuid=True), ForeignKey("videos.id", ondelete="CASCADE"), nullable=False
    )
    user_id = Column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    status = Column(
        String(24), nullable=False, default="pending"
    )  # pending | running | completed | failed
    celery_task_id = Column(String(128), nullable=True)
    worker_id = Column(String(128), nullable=True)
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    error_message = Column(Text, nullable=True)
    result_summary = Column(JSON, nullable=True)  # {verdict, score, ...}
    created_at = Column(DateTime(timezone=True), default=_utcnow, nullable=False)

    # Relationships
    video = relationship("Video", back_populates="jobs")
    user = relationship("User", back_populates="jobs")

    __table_args__ = (
        Index("ix_jobs_user_status", "user_id", "status"),
    )


# ---------------------------------------------------------------------------
# Attestations
# ---------------------------------------------------------------------------

class Attestation(Base):
    __tablename__ = "attestations"

    id = Column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    video_id = Column(
        UUID(as_uuid=True), ForeignKey("videos.id", ondelete="CASCADE"), nullable=False
    )
    job_id = Column(
        UUID(as_uuid=True), ForeignKey("jobs.id", ondelete="SET NULL"), nullable=True
    )
    attestation_id = Column(String(64), unique=True, nullable=False, index=True)
    manifest = Column(JSON, nullable=False)
    signature = Column(Text, nullable=False)
    public_key_pem = Column(Text, nullable=False)
    timestamp_token = Column(Text, nullable=True)
    merkle_leaf_index = Column(Integer, nullable=True)
    verdict = Column(String(32), nullable=False)
    fake_probability = Column(Float, nullable=False)
    is_revoked = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime(timezone=True), default=_utcnow, nullable=False)

    # Relationships
    video = relationship("Video", back_populates="attestations")

    __table_args__ = (
        Index("ix_attestations_verdict", "verdict"),
    )


# ---------------------------------------------------------------------------
# Revocations
# ---------------------------------------------------------------------------

class Revocation(Base):
    __tablename__ = "revocations"

    id = Column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    attestation_id = Column(String(64), nullable=False, index=True)
    reason = Column(Text, nullable=False)
    revoked_by = Column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at = Column(DateTime(timezone=True), default=_utcnow, nullable=False)


# ---------------------------------------------------------------------------
# Shares
# ---------------------------------------------------------------------------

class Share(Base):
    __tablename__ = "shares"

    id = Column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    attestation_id = Column(String(64), nullable=False, index=True)
    sender_id = Column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    recipient_id = Column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    envelope = Column(JSON, nullable=False)  # encrypted ShareEnvelope
    created_at = Column(DateTime(timezone=True), default=_utcnow, nullable=False)

    __table_args__ = (
        Index("ix_shares_recipient", "recipient_id"),
    )


# ---------------------------------------------------------------------------
# Anomaly events
# ---------------------------------------------------------------------------

class AnomalyEventRecord(Base):
    __tablename__ = "anomaly_events"

    id = Column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    event_id = Column(String(64), unique=True, nullable=False, index=True)
    subject_type = Column(String(16), nullable=False)
    subject_id = Column(String(128), nullable=False)
    alert_level = Column(Integer, nullable=False)
    action = Column(String(64), nullable=False)
    anomaly_score = Column(Float, nullable=False)
    features = Column(JSON, nullable=True)
    rule_hits = Column(JSON, nullable=True)
    resolved = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime(timezone=True), default=_utcnow, nullable=False)

    __table_args__ = (
        Index("ix_anomaly_subject", "subject_type", "subject_id"),
    )


# ---------------------------------------------------------------------------
# Audit log
# ---------------------------------------------------------------------------

class AuditLog(Base):
    __tablename__ = "audit_log"

    id = Column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    user_id = Column(UUID(as_uuid=True), nullable=True)
    action = Column(String(64), nullable=False)
    resource_type = Column(String(32), nullable=True)
    resource_id = Column(String(128), nullable=True)
    ip_address = Column(String(45), nullable=True)
    user_agent = Column(String(512), nullable=True)
    details = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), default=_utcnow, nullable=False)

    __table_args__ = (
        Index("ix_audit_user_action", "user_id", "action"),
        Index("ix_audit_created", "created_at"),
    )
