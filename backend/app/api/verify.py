"""
Public verification endpoint (no authentication required).

POST /verify/by-id         → verify by attestation ID
POST /verify/by-upload     → verify by re-uploading the video + package

These endpoints are stateless and public per the spec:
anyone with an attestation ID or package can verify independently.
"""

from __future__ import annotations

from fastapi import APIRouter, File, Form, HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import Depends

from backend.app.core.database import get_db
from backend.app.models.models import Attestation
from backend.app.schemas.schemas import (
    CheckResultSchema,
    VerificationResponse,
    VerifyByIdRequest,
)
from backend.app.services.verifier import CheckStatus, Verifier

import structlog

logger = structlog.get_logger(__name__)
router = APIRouter()


@router.post("/by-id", response_model=VerificationResponse)
async def verify_by_id(
    body: VerifyByIdRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Verify an attestation by its ID.

    Performs signature verification, certificate check, timestamp validation,
    and Merkle inclusion proof (where data is available). Returns per-check
    pass/fail results, never a single opaque "valid" boolean.
    """
    result = await db.execute(
        select(Attestation).where(Attestation.attestation_id == body.attestation_id)
    )
    att = result.scalar_one_or_none()
    if not att:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Attestation not found")

    if att.is_revoked:
        return VerificationResponse(
            attestation_id=att.attestation_id,
            checks=[
                CheckResultSchema(
                    name="revocation",
                    status="fail",
                    detail="This attestation has been revoked.",
                )
            ],
            all_passed=False,
        )

    # Run the verification pipeline
    verifier = Verifier()
    manifest = att.manifest
    public_key_pem = att.public_key_pem

    # We don't have the video bytes for a by-ID verification,
    # so we skip the hash check and focus on crypto verification
    vr = verifier.verify(
        video_bytes=b"",  # Not available in by-ID mode
        manifest=manifest,
        public_key_pem=public_key_pem,
    )

    # Override hash check — not applicable in by-ID mode
    checks = []
    for c in vr.checks:
        if c.name == "hash_integrity":
            checks.append(
                CheckResultSchema(
                    name="hash_integrity",
                    status="skip",
                    detail="Hash check skipped in by-ID mode (no video provided).",
                )
            )
        else:
            checks.append(
                CheckResultSchema(
                    name=c.name,
                    status=c.status.value,
                    detail=c.detail,
                )
            )

    all_passed = all(
        c.status in ("pass", "skip") for c in checks
    )

    return VerificationResponse(
        attestation_id=att.attestation_id,
        checks=checks,
        hash_match_type=None,
        ai_verdict=vr.ai_verdict,
        ai_score=vr.ai_score,
        timestamp_utc=vr.timestamp_utc,
        all_passed=all_passed,
    )


@router.post("/by-upload", response_model=VerificationResponse)
async def verify_by_upload(
    attestation_id: str = Form(...),
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
):
    """
    Verify an attestation by re-uploading the original video.

    This enables the full verification pipeline including SHA-256 hash
    integrity, signature, certificate, timestamp, and Merkle proof checks.
    """
    result = await db.execute(
        select(Attestation).where(Attestation.attestation_id == attestation_id)
    )
    att = result.scalar_one_or_none()
    if not att:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Attestation not found")

    if att.is_revoked:
        return VerificationResponse(
            attestation_id=att.attestation_id,
            checks=[
                CheckResultSchema(
                    name="revocation",
                    status="fail",
                    detail="This attestation has been revoked.",
                )
            ],
            all_passed=False,
        )

    video_bytes = await file.read()

    verifier = Verifier()
    vr = verifier.verify(
        video_bytes=video_bytes,
        manifest=att.manifest,
        public_key_pem=att.public_key_pem,
    )

    checks = [
        CheckResultSchema(name=c.name, status=c.status.value, detail=c.detail)
        for c in vr.checks
    ]

    return VerificationResponse(
        attestation_id=att.attestation_id,
        checks=checks,
        hash_match_type=vr.hash_match_type,
        ai_verdict=vr.ai_verdict,
        ai_score=vr.ai_score,
        timestamp_utc=vr.timestamp_utc,
        all_passed=vr.all_passed,
    )
