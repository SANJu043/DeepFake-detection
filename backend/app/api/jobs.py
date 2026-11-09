"""
Job status endpoints.

GET /jobs         → list current user's jobs
GET /jobs/{id}    → check single job progress
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.database import get_db
from backend.app.core.deps import get_current_user
from backend.app.models.models import Job, User
from backend.app.schemas.schemas import JobListResponse, JobStatus

router = APIRouter()


@router.get("/", response_model=JobListResponse)
async def list_jobs(
    skip: int = 0,
    limit: int = 50,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List the current user's detection jobs (paginated)."""
    count_q = select(func.count()).select_from(Job).where(Job.user_id == user.id)
    total = (await db.execute(count_q)).scalar() or 0

    q = (
        select(Job)
        .where(Job.user_id == user.id)
        .order_by(Job.created_at.desc())
        .offset(skip)
        .limit(limit)
    )
    result = await db.execute(q)
    jobs = result.scalars().all()

    return JobListResponse(
        jobs=[JobStatus.model_validate(j) for j in jobs],
        total=total,
    )


@router.get("/{job_id}", response_model=JobStatus)
async def get_job_status(
    job_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get the status and progress of a detection job."""
    result = await db.execute(
        select(Job).where(Job.id == uuid.UUID(job_id), Job.user_id == user.id)
    )
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Job not found")

    return JobStatus.model_validate(job)
