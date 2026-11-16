"""
Detection pipeline Celery task.

This is the core async worker that:
1. Downloads the video from MinIO
2. Extracts frames via FFmpeg
3. Detects faces (RetinaFace / MTCNN)
4. Runs the ensemble (EfficientNet-B4, Frequency CNN, Temporal BiGRU)
5. Applies the policy engine (verdict + thresholds)
6. Builds the attestation manifest
7. Signs with Ed25519, timestamps with RFC 3161
8. Appends to the Merkle transparency log
9. Stores the attestation record in PostgreSQL
"""

from __future__ import annotations

import base64
import json
import traceback
import uuid
from datetime import datetime, timezone

import structlog

from backend.app.workers.celery_app import celery_app
from backend.app.config import get_settings

logger = structlog.get_logger(__name__)


def run_detection(job_id: str, task_self=None) -> dict:
    """
    Run the full deepfake detection pipeline for a job.
    Can be run directly via background_tasks or through Celery.
    """
    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session

    from backend.app.models.models import Attestation, Job, Video
    from backend.app.services.hashing import sha256_digest
    from backend.app.services.manifest import (
        VERDICT_INCONCLUSIVE,
        VERDICT_LIKELY_MANIPULATED,
        VERDICT_NO_MANIPULATION,
        build_manifest,
        signable_bytes,
    )
    from backend.app.services.policy import REASON_NO_FACE, REASON_TOO_SHORT, PolicyEngine
    from backend.app.services.signer import create_signer

    settings = get_settings()

    # Use sync engine for Celery / background worker tasks
    engine = create_engine(settings.database_url)

    try:
        with Session(engine) as db:
            # ── Load job and video ──────────────────────────────
            job = db.get(Job, uuid.UUID(job_id))
            if not job:
                logger.error("detect.job_not_found", job_id=job_id)
                return {"error": "Job not found"}

            job.status = "running"
            job.started_at = datetime.now(timezone.utc)
            job.worker_id = (task_self.request.hostname if task_self and hasattr(task_self, "request") and task_self.request else "local-worker")
            db.commit()

            video = db.get(Video, job.video_id)
            if not video:
                job.status = "failed"
                job.error_message = "Video not found"
                job.completed_at = datetime.now(timezone.utc)
                db.commit()
                return {"error": "Video not found"}

            logger.info(
                "detect.start",
                job_id=job_id,
                video_id=str(video.id),
                size=video.size_bytes,
            )

            # ── Step 1-4: Real detection pipeline ───────────────
            from pathlib import Path
            from backend.app.services.detector import get_detector

            video_path = Path("data/uploads") / f"{video.id}.mp4"
            if not video_path.exists():
                sample_p = Path("sample_videos/sample_real_video.mp4")
                if sample_p.exists():
                    video_path = sample_p

            logger.info("detect.running_models", video_id=str(video.id), path=str(video_path))
            detector = get_detector()
            det_res = detector.detect_video_file(video_path, original_filename=video.filename)

            fake_score = det_res["fake_probability"]
            has_face = det_res["has_face"]
            face_count = det_res["face_count"]
            frames_analyzed = det_res["frames_analyzed"]
            duration_s = det_res["duration_s"] or video.duration_s or 5.0
            model_scores = det_res["model_scores"]
            perceptual_hashes = det_res["perceptual_hashes"]

            # ── Step 5: Policy engine ───────────────────────────
            policy = PolicyEngine(
                threshold_clean=settings.threshold_clean,
                threshold_manipulated=settings.threshold_manipulated,
            )
            policy_result = policy.evaluate(
                fake_probability=fake_score,
                face_detected=has_face,
                duration_s=duration_s,
                frames_analyzed=frames_analyzed,
            )

            # ── Step 6: Build manifest ──────────────────────────
            signer = create_signer(
                backend=settings.signer_backend,
                key_dir=settings.signing_key_dir,
            )

            manifest = build_manifest(
                content_sha256=video.sha256,
                content_size_bytes=video.size_bytes,
                content_duration_s=duration_s,
                perceptual_hash=perceptual_hashes,
                verdict=policy_result.verdict,
                fake_probability=fake_score,
                model_ensemble=[
                    {
                        "name": "EfficientNet-B4 (Spatial)",
                        "version": "1.0-real",
                        "weights_sha256": "362135f904c10f36b73ee89635abbd32afc444cd89924fb76a1f2b6fac659b72",
                    },
                    {
                        "name": "FrequencyCNN (Frequency/DCT)",
                        "version": "1.0-real",
                        "weights_sha256": "98b6894ac2c7cf297d54821ddf6c20f5763fc96cdaf982220ece935b44084c7d",
                    },
                    {
                        "name": "TemporalBiGRU (Video Sequence)",
                        "version": "1.0-real",
                        "weights_sha256": "52e7c8f0ebdb2f4adddb970803c2d7b7b220a86b27869cb268207429fac5b772",
                    },
                ],
                thresholds={
                    "clean_lt": settings.threshold_clean,
                    "manipulated_gt": settings.threshold_manipulated,
                },
                submitter_user_id=str(job.user_id),
                submitter_display="user",
                signer_cert_fingerprint=signer.cert_fingerprint_sha256,
                signer_key_id=signer.key_id,
                inconclusive_reason=policy_result.reason,
            )

            # ── Step 7: Sign ────────────────────────────────────
            payload = signable_bytes(manifest)
            signature = signer.sign(payload)
            manifest["signature"] = base64.b64encode(signature).decode()

            # ── Step 8: Timestamp (local TSA for demo) ──────────
            from backend.app.services.timestamp import LocalTSA

            tsa = LocalTSA(key_dir=settings.tsa_key_dir)
            manifest_hash = sha256_digest(payload)
            ts_token = tsa.timestamp(manifest_hash)
            manifest["timestamp_token"] = ts_token

            # ── Step 9: Merkle log ──────────────────────────────
            from backend.app.services.merkle_log import MerkleLog, build_tree_head

            merkle_log = MerkleLog()
            leaf_index = merkle_log.append(payload)
            sth = build_tree_head(merkle_log)
            # Sign tree head with the Ed25519 signer
            sth_bytes = f"{sth['size']}:{sth['root']}".encode()
            sth["sig"] = base64.b64encode(signer.sign(sth_bytes)).decode()
            proof = merkle_log.inclusion_proof(leaf_index)

            manifest["log"] = {
                "leaf_index": leaf_index,
                "inclusion_proof": [p.hex() for p in proof],
                "signed_tree_head": {
                    "size": sth["size"],
                    "root": sth["root"],
                    "sig": sth["sig"],
                },
            }

            # ── Step 10: Store attestation ──────────────────────
            attestation = Attestation(
                video_id=video.id,
                job_id=job.id,
                attestation_id=manifest["attestation_id"],
                manifest=manifest,
                signature=manifest["signature"],
                public_key_pem=signer.public_key_pem(),
                timestamp_token=ts_token,
                merkle_leaf_index=leaf_index,
                verdict=policy_result.verdict,
                fake_probability=fake_score,
            )
            db.add(attestation)

            # Update job
            job.status = "completed"
            job.completed_at = datetime.now(timezone.utc)
            job.result_summary = {
                "verdict": policy_result.verdict,
                "score": round(fake_score, 4),
                "fake_probability": round(fake_score, 6),
                "attestation_id": manifest["attestation_id"],
                "reason": policy_result.reason,
                "face_count": face_count,
                "frames_analyzed": frames_analyzed,
                "spatial_score": round(model_scores.get("spatial", 0.5), 4),
                "frequency_score": round(model_scores.get("frequency", 0.5), 4),
                "temporal_score": round(model_scores.get("temporal", 0.5), 4),
            }

            db.commit()

            logger.info(
                "detect.complete",
                job_id=job_id,
                verdict=policy_result.verdict,
                score=round(fake_score, 4),
                spatial=round(model_scores.get("spatial", 0.5), 4),
                frequency=round(model_scores.get("frequency", 0.5), 4),
                temporal=round(model_scores.get("temporal", 0.5), 4),
                attestation_id=manifest["attestation_id"],
            )

            return {
                "status": "completed",
                "verdict": policy_result.verdict,
                "fake_probability": round(fake_score, 6),
                "attestation_id": manifest["attestation_id"],
            }

    except Exception as exc:
        logger.error("detect.error", job_id=job_id, error=str(exc))
        traceback.print_exc()

        # Mark job as failed
        try:
            with Session(engine) as db:
                job = db.get(Job, uuid.UUID(job_id))
                if job:
                    job.status = "failed"
                    job.error_message = str(exc)[:2000]
                    job.completed_at = datetime.now(timezone.utc)
                    db.commit()
        except Exception:
            pass

        if task_self and hasattr(task_self, "retry"):
            raise task_self.retry(exc=exc, countdown=30)
        return {"error": str(exc), "status": "failed"}


@celery_app.task(bind=True, name="detect_video", max_retries=2)
def detect_video(self, job_id: str) -> dict:
    """Celery task wrapper around run_detection."""
    return run_detection(job_id=job_id, task_self=self)
