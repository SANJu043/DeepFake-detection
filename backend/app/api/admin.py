"""
Admin-only endpoints.

GET    /admin/keys       → active signing key info
POST   /admin/revoke     → revoke an attestation
GET    /admin/anomalies  → list anomaly events
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.config import get_settings
from backend.app.core.database import get_db
from backend.app.core.deps import require_role
from backend.app.models.models import (
    AnomalyEventRecord,
    Attestation,
    Revocation,
    User,
)
from backend.app.schemas.schemas import (
    AnomalyEventResponse,
    AnomalyListResponse,
    KeyInfoResponse,
    RevokeRequest,
    RevokeResponse,
)
from backend.app.services.signer import create_signer

import structlog

logger = structlog.get_logger(__name__)
router = APIRouter()


@router.get("/keys", response_model=KeyInfoResponse)
async def get_key_info(user: User = Depends(require_role("admin"))):
    """Return information about the active signing key."""
    settings = get_settings()
    signer = create_signer(
        backend=settings.signer_backend,
        key_dir=settings.signing_key_dir,
    )

    return KeyInfoResponse(
        key_id=signer.key_id,
        algorithm="Ed25519",
        cert_fingerprint_sha256=signer.cert_fingerprint_sha256,
        public_key_pem=signer.public_key_pem(),
    )


@router.post("/revoke", response_model=RevokeResponse, status_code=status.HTTP_201_CREATED)
async def revoke_attestation(
    body: RevokeRequest,
    user: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
):
    """
    Revoke an attestation. The attestation's signature remains valid
    but verifiers will see it in the signed revocation list.
    """
    # Find the attestation
    result = await db.execute(
        select(Attestation).where(Attestation.attestation_id == body.attestation_id)
    )
    att = result.scalar_one_or_none()
    if not att:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Attestation not found")

    if att.is_revoked:
        raise HTTPException(status.HTTP_409_CONFLICT, "Already revoked")

    # Mark as revoked in attestations table
    att.is_revoked = True

    # Create revocation record
    revocation = Revocation(
        attestation_id=body.attestation_id,
        reason=body.reason,
        revoked_by=user.id,
    )
    db.add(revocation)
    await db.flush()
    await db.refresh(revocation)

    logger.info(
        "admin.revoke",
        attestation_id=body.attestation_id,
        reason=body.reason,
        revoked_by=str(user.id),
    )

    return RevokeResponse(
        attestation_id=body.attestation_id,
        reason=body.reason,
        revoked_by=str(user.id),
        revoked_at=revocation.created_at.isoformat(),
        list_version=1,  # In production, tracked by RevocationService
    )


@router.get("/anomalies", response_model=AnomalyListResponse)
async def list_anomalies(
    skip: int = 0,
    limit: int = 50,
    resolved: bool = False,
    user: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
):
    """List anomaly/threat detection events (admin only)."""
    count_q = (
        select(func.count())
        .select_from(AnomalyEventRecord)
        .where(AnomalyEventRecord.resolved == resolved)
    )
    total = (await db.execute(count_q)).scalar() or 0

    q = (
        select(AnomalyEventRecord)
        .where(AnomalyEventRecord.resolved == resolved)
        .order_by(AnomalyEventRecord.created_at.desc())
        .offset(skip)
        .limit(limit)
    )
    result = await db.execute(q)
    events = result.scalars().all()

    return AnomalyListResponse(
        events=[AnomalyEventResponse.model_validate(e) for e in events],
        total=total,
    )
