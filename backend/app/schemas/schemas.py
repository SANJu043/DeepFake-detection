"""
Pydantic schemas for request/response validation.

Organized by domain:
- Auth (register, login, token refresh)
- Videos (upload response, listing)
- Jobs (status, result)
- Attestations (detail, verification)
- Admin (keys, revocation, anomalies)
- Shares (create, list)
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field, field_validator


# ═══════════════════════════════════════════════════════════════
# Auth
# ═══════════════════════════════════════════════════════════════

class RegisterRequest(BaseModel):
    email: EmailStr
    display_name: str = Field(..., min_length=2, max_length=128)
    password: str = Field(..., min_length=8, max_length=128)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int


class RefreshRequest(BaseModel):
    refresh_token: str


class UserResponse(BaseModel):
    id: UUID
    email: str
    display_name: str
    role: str
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


# ═══════════════════════════════════════════════════════════════
# Videos
# ═══════════════════════════════════════════════════════════════

class VideoUploadResponse(BaseModel):
    video_id: UUID
    job_id: UUID
    filename: str
    sha256: str
    size_bytes: int
    message: str = "Upload successful. Detection job queued."


class VideoDetail(BaseModel):
    id: UUID
    filename: str
    content_type: str
    size_bytes: int
    sha256: str
    duration_s: Optional[float] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class VideoListResponse(BaseModel):
    videos: List[VideoDetail]
    total: int


# ═══════════════════════════════════════════════════════════════
# Jobs
# ═══════════════════════════════════════════════════════════════

class JobStatus(BaseModel):
    id: UUID
    video_id: UUID
    status: str
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error_message: Optional[str] = None
    result_summary: Optional[Dict[str, Any]] = None

    model_config = {"from_attributes": True}


class JobListResponse(BaseModel):
    jobs: List[JobStatus]
    total: int


# ═══════════════════════════════════════════════════════════════
# Attestations
# ═══════════════════════════════════════════════════════════════

class AttestationSummary(BaseModel):
    id: UUID
    attestation_id: str
    video_id: UUID
    verdict: str
    fake_probability: float
    is_revoked: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class AttestationDetail(BaseModel):
    id: UUID
    attestation_id: str
    video_id: UUID
    manifest: Dict[str, Any]
    signature: str
    public_key_pem: str
    timestamp_token: Optional[str] = None
    merkle_leaf_index: Optional[int] = None
    verdict: str
    fake_probability: float
    is_revoked: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class AttestationListResponse(BaseModel):
    attestations: List[AttestationSummary]
    total: int


# ═══════════════════════════════════════════════════════════════
# Verification (public)
# ═══════════════════════════════════════════════════════════════

class CheckResultSchema(BaseModel):
    name: str
    status: str
    detail: str = ""


class VerifyByIdRequest(BaseModel):
    attestation_id: str


class VerificationResponse(BaseModel):
    attestation_id: Optional[str] = None
    checks: List[CheckResultSchema]
    hash_match_type: Optional[str] = None
    ai_verdict: Optional[str] = None
    ai_score: Optional[float] = None
    timestamp_utc: Optional[datetime] = None
    all_passed: bool
    reminder: str = (
        "Cryptography proves who vouched for what, when, and that nothing "
        "changed since. The AI verdict is a probabilistic opinion, not "
        "absolute truth."
    )


# ═══════════════════════════════════════════════════════════════
# Admin
# ═══════════════════════════════════════════════════════════════

class KeyInfoResponse(BaseModel):
    key_id: str
    algorithm: str
    cert_fingerprint_sha256: str
    public_key_pem: str


class RevokeRequest(BaseModel):
    attestation_id: str
    reason: str = Field(..., min_length=4, max_length=1024)


class RevokeResponse(BaseModel):
    attestation_id: str
    reason: str
    revoked_by: str
    revoked_at: str
    list_version: int


class AnomalyEventResponse(BaseModel):
    event_id: str
    subject_type: str
    subject_id: str
    alert_level: int
    action: str
    anomaly_score: float
    features: Optional[Dict[str, Any]] = None
    rule_hits: Optional[List[str]] = None
    resolved: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class AnomalyListResponse(BaseModel):
    events: List[AnomalyEventResponse]
    total: int


# ═══════════════════════════════════════════════════════════════
# Shares
# ═══════════════════════════════════════════════════════════════

class ShareCreateRequest(BaseModel):
    attestation_id: str
    recipient_email: str


class ShareResponse(BaseModel):
    id: UUID
    attestation_id: str
    sender_id: UUID
    recipient_id: UUID
    created_at: datetime

    model_config = {"from_attributes": True}


class ShareListResponse(BaseModel):
    shares: List[ShareResponse]
    total: int


# ═══════════════════════════════════════════════════════════════
# Generic
# ═══════════════════════════════════════════════════════════════

class MessageResponse(BaseModel):
    message: str
    detail: Optional[str] = None


class ErrorResponse(BaseModel):
    error: str
    detail: Optional[str] = None
