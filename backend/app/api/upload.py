"""
Video upload and management endpoints.

POST   /videos         → upload a video, validate, hash, store, enqueue job
GET    /videos         → list current user's videos
DELETE /videos/{id}    → soft-delete video data (hashes + attestations preserved)
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.config import get_settings
from backend.app.core.database import get_db
from backend.app.core.deps import get_current_user
from backend.app.models.models import Job, User, Video
from backend.app.schemas.schemas import (
    MessageResponse,
    VideoDetail,
    VideoListResponse,
    VideoUploadResponse,
)
from backend.app.services.hashing import sha256_digest
from backend.app.services.video_io import VideoValidationError, validate_video

import structlog

logger = structlog.get_logger(__name__)
router = APIRouter()


@router.post("/", response_model=VideoUploadResponse, status_code=status.HTTP_202_ACCEPTED)
async def upload_video(
    file: UploadFile = File(...),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Upload a video for deepfake analysis.

    Validates type, size, and magic bytes, computes SHA-256,
    stores the record, and enqueues a detection job.
    """
    settings = get_settings()

    # Read file bytes
    data = await file.read()

    # Validate
    try:
        video_info = validate_video(
            data,
            max_size_bytes=settings.max_upload_size_bytes,
            allowed_extensions=settings.allowed_extensions_list,
            filename=file.filename,
        )
    except VideoValidationError as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(e))

    # Compute SHA-256
    content_hash = sha256_digest(data)

    # Create video record
    video = Video(
        owner_id=user.id,
        filename=file.filename or "unknown.mp4",
        content_type=file.content_type or "video/mp4",
        size_bytes=len(data),
        sha256=content_hash,
        s3_key=f"videos/{user.id}/{uuid.uuid4()}/{file.filename}",
        duration_s=video_info.get("duration_s"),
    )
    db.add(video)
    await db.flush()

    # Create detection job
    job = Job(
        video_id=video.id,
        user_id=user.id,
        status="pending",
    )
    db.add(job)
    await db.flush()

    # TODO: In production, upload `data` to MinIO under `video.s3_key`
    # and dispatch Celery task: detect_video.delay(str(job.id))

    logger.info(
        "video.uploaded",
        video_id=str(video.id),
        job_id=str(job.id),
        size=len(data),
        sha256=content_hash[:16],
    )

    return VideoUploadResponse(
        video_id=video.id,
        job_id=job.id,
        filename=video.filename,
        sha256=content_hash,
        size_bytes=len(data),
    )


@router.get("/", response_model=VideoListResponse)
async def list_videos(
    skip: int = 0,
    limit: int = 50,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List the current user's uploaded videos (paginated)."""
    count_q = select(func.count()).select_from(Video).where(Video.owner_id == user.id)
    total = (await db.execute(count_q)).scalar() or 0

    q = (
        select(Video)
        .where(Video.owner_id == user.id)
        .order_by(Video.created_at.desc())
        .offset(skip)
        .limit(limit)
    )
    result = await db.execute(q)
    videos = result.scalars().all()

    return VideoListResponse(
        videos=[VideoDetail.model_validate(v) for v in videos],
        total=total,
    )


@router.delete("/{video_id}", response_model=MessageResponse)
async def delete_video(
    video_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    FR14: Soft-delete stored video data. Hashes, manifest, and log entries
    remain so past verification still works.
    """
    result = await db.execute(
        select(Video).where(Video.id == uuid.UUID(video_id), Video.owner_id == user.id)
    )
    video = result.scalar_one_or_none()
    if not video:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Video not found")

    # TODO: Delete the actual object from MinIO
    # Mark as deleted by clearing the S3 key
    video.s3_key = f"DELETED/{video.s3_key}"

    logger.info("video.deleted", video_id=video_id)
    return MessageResponse(
        message="Video data deleted. Hash and attestation preserved for verification."
    )
