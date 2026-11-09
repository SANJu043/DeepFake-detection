"""
Attestation endpoints.

GET /attestations              → list current user's attestations
GET /attestations/{id}         → full attestation detail
GET /attestations/{id}/package → download signed verification package
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.database import get_db
from backend.app.core.deps import get_current_user
from backend.app.models.models import Attestation, User, Video
from backend.app.schemas.schemas import (
    AttestationDetail,
    AttestationListResponse,
    AttestationSummary,
)

import structlog

logger = structlog.get_logger(__name__)
router = APIRouter()


@router.get("/", response_model=AttestationListResponse)
async def list_attestations(
    skip: int = 0,
    limit: int = 50,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List attestations for the current user's videos."""
    # Get user's video IDs
    vid_q = select(Video.id).where(Video.owner_id == user.id)

    count_q = (
        select(func.count())
        .select_from(Attestation)
        .where(Attestation.video_id.in_(vid_q))
    )
    total = (await db.execute(count_q)).scalar() or 0

    q = (
        select(Attestation)
        .where(Attestation.video_id.in_(vid_q))
        .order_by(Attestation.created_at.desc())
        .offset(skip)
        .limit(limit)
    )
    result = await db.execute(q)
    attestations = result.scalars().all()

    return AttestationListResponse(
        attestations=[AttestationSummary.model_validate(a) for a in attestations],
        total=total,
    )


@router.get("/{attestation_id}", response_model=AttestationDetail)
async def get_attestation(
    attestation_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get full attestation detail by attestation UUID."""
    # Look up by the human-readable attestation_id field
    result = await db.execute(
        select(Attestation).where(Attestation.attestation_id == attestation_id)
    )
    att = result.scalar_one_or_none()
    if not att:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Attestation not found")

    # Ownership check
    vid_result = await db.execute(select(Video).where(Video.id == att.video_id))
    video = vid_result.scalar_one_or_none()
    if not video or (video.owner_id != user.id and user.role != "admin"):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Access denied")

    return AttestationDetail.model_validate(att)


@router.get("/{attestation_id}/package")
async def get_attestation_package(
    attestation_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Download the signed verification package:
    manifest JSON + signature + public key + timestamp + Merkle proof.
    """
    result = await db.execute(
        select(Attestation).where(Attestation.attestation_id == attestation_id)
    )
    att = result.scalar_one_or_none()
    if not att:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Attestation not found")

    # Ownership check
    vid_result = await db.execute(select(Video).where(Video.id == att.video_id))
    video = vid_result.scalar_one_or_none()
    if not video or (video.owner_id != user.id and user.role != "admin"):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Access denied")

    return {
        "attestation_id": att.attestation_id,
        "manifest": att.manifest,
        "signature": att.signature,
        "public_key_pem": att.public_key_pem,
        "timestamp_token": att.timestamp_token,
        "merkle_leaf_index": att.merkle_leaf_index,
    }
