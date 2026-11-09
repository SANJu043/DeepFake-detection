"""
FastAPI application entry point.

Configures CORS, middleware, routes, and startup events.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.app.config import get_settings
from backend.app.core.logging import setup_logging
from backend.app.api import auth, upload, jobs, attestations, verify, admin, shares


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator:
    """Application lifespan: startup and shutdown events."""
    settings = get_settings()
    setup_logging(level="DEBUG" if settings.debug else "INFO")
    yield


def create_app() -> FastAPI:
    """Application factory."""
    settings = get_settings()

    app = FastAPI(
        title="Deepfake Detection & Cryptographic Authenticity System",
        description=(
            "Upload videos for AI-powered deepfake detection with "
            "cryptographic attestation (Ed25519, RFC 3161, Merkle log)."
        ),
        version="1.0.0",
        lifespan=lifespan,
    )

    # ── CORS ────────────────────────────────────────────────
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ── Routes ──────────────────────────────────────────────
    app.include_router(auth.router, prefix="/auth", tags=["Authentication"])
    app.include_router(upload.router, prefix="/videos", tags=["Videos"])
    app.include_router(jobs.router, prefix="/jobs", tags=["Jobs"])
    app.include_router(attestations.router, prefix="/attestations", tags=["Attestations"])
    app.include_router(verify.router, prefix="/verify", tags=["Verification"])
    app.include_router(admin.router, prefix="/admin", tags=["Admin"])
    app.include_router(shares.router, prefix="/shares", tags=["Sharing"])

    # ── Health ──────────────────────────────────────────────
    @app.get("/health", tags=["Operations"])
    async def health_check():
        return {"status": "healthy", "version": "1.0.0"}

    return app


app = create_app()
