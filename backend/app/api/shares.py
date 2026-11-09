"""
Secure sharing endpoints.

POST /shares        → share an attestation with another user (encrypted)
GET  /shares        → list shares received by the current user
GET  /shares/{id}   → get share detail / envelope
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.config import get_settings
from backend.app.core.database import get_db
from backend.app.core.deps import get_current_user
from backend.app.models.models import Attestation, Share, User, Video
from backend.app.schemas.schemas import (
    MessageResponse,
    ShareCreateRequest,
    ShareListResponse,
    ShareResponse,
)
from backend.app.services.sharing import encrypt_for_recipient
from backend.app.services.signer import create_signer

import structlog

logger = structlog.get_logger(__name__)
router = APIRouter()


@router.post("/", response_model=ShareResponse, status_code=status.HTTP_201_CREATED)
async def create_share(
    body: ShareCreateRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Share an attestation with another user via end-to-end encryption.

    Requires the recipient to have registered an X25519 public key.
    """
    # Verify the attestation exists and belongs to the user
    att_result = await db.execute(
        select(Attestation).where(Attestation.attestation_id == body.attestation_id)
    )
    att = att_result.scalar_one_or_none()
    if not att:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Attestation not found")

    vid_result = await db.execute(select(Video).where(Video.id == att.video_id))
    video = vid_result.scalar_one_or_none()
    if not video or video.owner_id != user.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "You can only share your own attestations")

    # Find recipient
    rec_result = await db.execute(
        select(User).where(User.email == body.recipient_email)
    )
    recipient = rec_result.scalar_one_or_none()
    if not recipient:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Recipient not found")

    if recipient.id == user.id:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Cannot share with yourself")

    # Build envelope (requires recipient's X25519 key)
    import base64
    import json

    if not recipient.x25519_public_key:
        # If no X25519 key, store a placeholder envelope
        envelope_dict = {
            "status": "pending_key",
            "attestation_id": body.attestation_id,
            "sender_id": str(user.id),
            "recipient_id": str(recipient.id),
            "message": "Recipient has not registered an X25519 public key yet.",
        }
    else:
        settings = get_settings()
        signer = create_signer(
            backend=settings.signer_backend,
            key_dir=settings.signing_key_dir,
        )

        # Package the manifest as plaintext to encrypt
        plaintext = json.dumps(att.manifest, sort_keys=True).encode()
        recipient_pub_raw = base64.b64decode(recipient.x25519_public_key)

        envelope = encrypt_for_recipient(
            plaintext=plaintext,
            attestation_id=body.attestation_id,
            sender_id=str(user.id),
            recipient_id=str(recipient.id),
            recipient_public_key_raw=recipient_pub_raw,
            signer=signer,
        )
        envelope_dict = envelope.to_dict()

    share = Share(
        attestation_id=body.attestation_id,
        sender_id=user.id,
        recipient_id=recipient.id,
        envelope=envelope_dict,
    )
    db.add(share)
    await db.flush()
    await db.refresh(share)

    logger.info(
        "share.created",
        share_id=str(share.id),
        attestation_id=body.attestation_id,
        sender=str(user.id),
        recipient=str(recipient.id),
    )

    return ShareResponse.model_validate(share)


@router.get("/", response_model=ShareListResponse)
async def list_shares(
    skip: int = 0,
    limit: int = 50,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List shares sent to or received by the current user."""
    count_q = (
        select(func.count())
        .select_from(Share)
        .where(or_(Share.sender_id == user.id, Share.recipient_id == user.id))
    )
    total = (await db.execute(count_q)).scalar() or 0

    q = (
        select(Share)
        .where(or_(Share.sender_id == user.id, Share.recipient_id == user.id))
        .order_by(Share.created_at.desc())
        .offset(skip)
        .limit(limit)
    )
    result = await db.execute(q)
    shares = result.scalars().all()

    return ShareListResponse(
        shares=[ShareResponse.model_validate(s) for s in shares],
        total=total,
    )


@router.get("/{share_id}")
async def get_share_detail(
    share_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get full share detail including encrypted envelope."""
    result = await db.execute(
        select(Share).where(Share.id == uuid.UUID(share_id))
    )
    share = result.scalar_one_or_none()
    if not share:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Share not found")

    if share.sender_id != user.id and share.recipient_id != user.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Access denied")

    return {
        "id": str(share.id),
        "attestation_id": share.attestation_id,
        "sender_id": str(share.sender_id),
        "recipient_id": str(share.recipient_id),
        "envelope": share.envelope,
        "created_at": share.created_at.isoformat(),
    }
