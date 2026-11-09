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


@celery_app.task(bind=True, name="detect_video", max_retries=2)
def detect_video(self, job_id: str) -> dict:
    """
    Run the full deepfake detection pipeline for a job.

    This task runs on GPU workers. It is designed to be idempotent:
    re-running the same job_id will overwrite the previous result.
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

    # Use sync engine for Celery tasks
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
            job.worker_id = self.request.hostname or "unknown"
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

            # ── Step 1-4: Detection pipeline ────────────────────
            # In production, this would:
            # 1. Download from MinIO: minio_client.get_object(bucket, video.s3_key)
            # 2. Extract frames: video_io.extract_frames(...)
            # 3. Detect faces: face.detect_faces(...)
            # 4. Run ensemble: detector.predict(...)
            #
            # For now, simulate with a deterministic score based on the hash
            hash_bytes = bytes.fromhex(video.sha256)
            # Use first 4 bytes of hash to generate a deterministic "score"
            simulated_score = int.from_bytes(hash_bytes[:4], "big") / (2**32)

            duration_s = video.duration_s or 5.0
            has_face = True  # simulated

            # ── Step 5: Policy engine ───────────────────────────
            policy = PolicyEngine(
                threshold_clean=settings.threshold_clean,
                threshold_manipulated=settings.threshold_manipulated,
            )
            policy_result = policy.evaluate(
                fake_probability=simulated_score,
                has_face=has_face,
                duration_s=duration_s,
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
                perceptual_hash=[],  # Would be computed from actual frames
                verdict=policy_result.verdict,
                fake_probability=simulated_score,
                model_ensemble=[
                    {"name": "EfficientNet-B4", "version": "1.0", "weights_sha256": "simulated"},
                    {"name": "FrequencyCNN", "version": "1.0", "weights_sha256": "simulated"},
                    {"name": "TemporalBiGRU", "version": "1.0", "weights_sha256": "simulated"},
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
            from backend.app.services.timestamp import LocalTSA, TimestampService

            tsa = LocalTSA(key_dir=settings.tsa_key_dir)
            ts_service = TimestampService(tsa)
            manifest_hash = sha256_digest(payload)
            ts_token = ts_service.stamp(manifest_hash)
            manifest["timestamp_token"] = ts_token

            # ── Step 9: Merkle log ──────────────────────────────
            from backend.app.services.merkle_log import MerkleLog

            merkle_log = MerkleLog(signer=signer)
            leaf_index = merkle_log.append(payload)
            sth = merkle_log.signed_tree_head()
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
                fake_probability=simulated_score,
            )
            db.add(attestation)

            # Update job
            job.status = "completed"
            job.completed_at = datetime.now(timezone.utc)
            job.result_summary = {
                "verdict": policy_result.verdict,
                "fake_probability": round(simulated_score, 6),
                "attestation_id": manifest["attestation_id"],
                "reason": policy_result.reason,
            }

            db.commit()

            logger.info(
                "detect.complete",
                job_id=job_id,
                verdict=policy_result.verdict,
                score=round(simulated_score, 4),
                attestation_id=manifest["attestation_id"],
            )

            return {
                "status": "completed",
                "verdict": policy_result.verdict,
                "fake_probability": round(simulated_score, 6),
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

        raise self.retry(exc=exc, countdown=30)
