"""
Attestation manifest builder and canonicalization.

Builds the JSON manifest described in Section 7.2 of the spec and
canonicalizes it with RFC 8785 (JSON Canonicalization Scheme) before
signing, so the signature is deterministic regardless of key order or
whitespace.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import jcs


# ---------------------------------------------------------------------------
# Verdict constants (Section 5a — locked decisions)
# ---------------------------------------------------------------------------

VERDICT_NO_MANIPULATION = "NO_MANIPULATION_DETECTED"
VERDICT_INCONCLUSIVE = "INCONCLUSIVE"
VERDICT_LIKELY_MANIPULATED = "LIKELY_MANIPULATED"

VALID_VERDICTS = {VERDICT_NO_MANIPULATION, VERDICT_INCONCLUSIVE, VERDICT_LIKELY_MANIPULATED}


# ---------------------------------------------------------------------------
# Manifest building
# ---------------------------------------------------------------------------

def build_manifest(
    *,
    content_sha256: str,
    content_size_bytes: int,
    content_duration_s: float,
    perceptual_hash: Optional[List[str]],
    verdict: str,
    fake_probability: float,
    model_ensemble: List[Dict[str, str]],
    thresholds: Dict[str, float],
    submitter_user_id: str,
    submitter_display: str,
    signer_cert_fingerprint: str,
    signer_key_id: str,
    signer_alg: str = "Ed25519",
    inconclusive_reason: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Build a complete attestation manifest (unsigned).

    The ``signature``, ``timestamp_token`` and ``log`` fields are left as
    empty strings / dicts — they are filled in by the signer and Merkle log
    services after canonicalization and signing.

    Args:
        content_sha256: SHA-256 hex of the original uploaded bytes.
        content_size_bytes: File size.
        content_duration_s: Video duration in seconds.
        perceptual_hash: List of pHash hex strings for sampled frames.
        verdict: One of the three locked verdict labels.
        fake_probability: Ensemble score 0.0–1.0.
        model_ensemble: List of dicts with 'name', 'version', 'weights_sha256'.
        thresholds: Dict with 'clean_lt' and 'manipulated_gt'.
        submitter_user_id: UUID of the uploader.
        submitter_display: Display name of the uploader.
        signer_cert_fingerprint: SHA-256 of the signing certificate.
        signer_key_id: Identifier for the signing key.
        signer_alg: Signature algorithm name.
        inconclusive_reason: If verdict is INCONCLUSIVE, optional reason string.

    Returns:
        Manifest dict ready for canonicalization and signing.

    Raises:
        ValueError: If verdict is not one of the locked labels.
    """
    if verdict not in VALID_VERDICTS:
        raise ValueError(
            f"Invalid verdict '{verdict}'. Must be one of {VALID_VERDICTS}"
        )

    manifest: Dict[str, Any] = {
        "version": "1.0",
        "attestation_id": str(uuid.uuid4()),
        "content": {
            "sha256": content_sha256,
            "size_bytes": content_size_bytes,
            "duration_s": round(content_duration_s, 3),
            "perceptual_hash": perceptual_hash or [],
        },
        "analysis": {
            "verdict": verdict,
            "fake_probability": round(fake_probability, 6),
            "model_ensemble": model_ensemble,
            "thresholds": thresholds,
        },
        "submitter": {
            "user_id": submitter_user_id,
            "display": submitter_display,
        },
        "issued_at": datetime.now(timezone.utc).isoformat(),
        "nonce": uuid.uuid4().hex,
        "signer": {
            "cert_fingerprint_sha256": signer_cert_fingerprint,
            "key_id": signer_key_id,
            "alg": signer_alg,
        },
        "signature": "",
        "timestamp_token": "",
        "log": {
            "leaf_index": -1,
            "inclusion_proof": [],
            "signed_tree_head": {
                "size": 0,
                "root": "",
                "sig": "",
            },
        },
    }

    if verdict == VERDICT_INCONCLUSIVE and inconclusive_reason:
        manifest["analysis"]["inconclusive_reason"] = inconclusive_reason

    return manifest


# ---------------------------------------------------------------------------
# Canonicalization (RFC 8785)
# ---------------------------------------------------------------------------

def canonicalize(manifest: Dict[str, Any]) -> bytes:
    """
    Produce the RFC 8785 canonical JSON form of *manifest*.

    This deterministic byte sequence is what gets signed, ensuring that
    any two implementations produce the same bytes for the same logical
    content.
    """
    return jcs.canonicalize(manifest)


def manifest_without_mutable_fields(manifest: Dict[str, Any]) -> Dict[str, Any]:
    """
    Return a copy of *manifest* with fields that are filled after signing
    removed. This is the payload that gets signed.

    Removed fields: ``signature``, ``timestamp_token``, ``log``.
    """
    m = dict(manifest)
    m.pop("signature", None)
    m.pop("timestamp_token", None)
    m.pop("log", None)
    return m


def signable_bytes(manifest: Dict[str, Any]) -> bytes:
    """
    Return the canonical bytes of the manifest without mutable fields.
    This is the exact byte sequence that is signed.
    """
    return canonicalize(manifest_without_mutable_fields(manifest))
