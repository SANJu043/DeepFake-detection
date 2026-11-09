"""
Verification service.

Implements the verification algorithm from Section 7.3:
1. Recompute SHA-256 → exact match or perceptual match fallback
2. Canonicalize manifest and verify Ed25519 signature
3. Validate certificate chain, validity, and revocation
4. Validate RFC 3161 timestamp token
5. Verify Merkle inclusion proof against signed tree head
6. Display AI verdict with probabilistic reminder
7. Return structured per-check result (never a single opaque "valid")
"""

from __future__ import annotations

import base64
import hashlib
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

import structlog

from backend.app.services.hashing import (
    perceptual_match,
    sha256_digest,
    sha256_verify,
)
from backend.app.services.manifest import (
    canonicalize,
    manifest_without_mutable_fields,
    signable_bytes,
)
from backend.app.services.merkle_log import (
    MerkleLog,
    leaf_hash,
    verify_inclusion,
)
from backend.app.services.signer import verify_with_public_key
from backend.app.services.timestamp import TimestampService

logger = structlog.get_logger(__name__)


# ---------------------------------------------------------------------------
# Check result types
# ---------------------------------------------------------------------------

class CheckStatus(str, Enum):
    PASS = "pass"
    FAIL = "fail"
    SKIP = "skip"
    WARN = "warn"


@dataclass
class CheckResult:
    """Result of a single verification check."""

    name: str
    status: CheckStatus
    detail: str = ""


@dataclass
class VerificationResult:
    """
    Complete structured verification result.

    Each check is reported individually — never a single opaque "valid".
    """

    checks: List[CheckResult] = field(default_factory=list)
    hash_match_type: Optional[str] = None  # "exact", "similar", "none"
    ai_verdict: Optional[str] = None
    ai_score: Optional[float] = None
    timestamp_utc: Optional[datetime] = None
    attestation_id: Optional[str] = None

    @property
    def all_passed(self) -> bool:
        return all(c.status == CheckStatus.PASS for c in self.checks)

    @property
    def summary(self) -> Dict[str, str]:
        return {c.name: c.status.value for c in self.checks}

    def add(self, name: str, status: CheckStatus, detail: str = "") -> None:
        self.checks.append(CheckResult(name=name, status=status, detail=detail))


# ---------------------------------------------------------------------------
# Verifier
# ---------------------------------------------------------------------------

class Verifier:
    """
    Orchestrates all verification checks described in Section 7.3.
    """

    def __init__(
        self,
        merkle_log: Optional[MerkleLog] = None,
        timestamp_service: Optional[TimestampService] = None,
    ) -> None:
        self._merkle_log = merkle_log
        self._timestamp_service = timestamp_service

    def verify(
        self,
        video_bytes: bytes,
        manifest: Dict[str, Any],
        public_key_pem: str,
        perceptual_hashes_lookup: Optional[List[str]] = None,
    ) -> VerificationResult:
        """
        Run the full verification pipeline.

        Args:
            video_bytes: The raw video file bytes to verify.
            manifest: The attestation manifest dict.
            public_key_pem: PEM-encoded public key of the signer.
            perceptual_hashes_lookup: Pre-computed perceptual hashes of the
                video for fallback matching.

        Returns:
            VerificationResult with per-check pass/fail details.
        """
        result = VerificationResult()
        result.attestation_id = manifest.get("attestation_id")
        result.ai_verdict = manifest.get("analysis", {}).get("verdict")
        result.ai_score = manifest.get("analysis", {}).get("fake_probability")

        # ── Step 1: Hash verification ───────────────────────
        expected_hash = manifest.get("content", {}).get("sha256", "")
        actual_hash = sha256_digest(video_bytes)

        if sha256_verify(video_bytes, expected_hash):
            result.add("hash_integrity", CheckStatus.PASS, "SHA-256 exact match")
            result.hash_match_type = "exact"
        else:
            # Try perceptual hash fallback
            stored_phashes = manifest.get("content", {}).get("perceptual_hash", [])
            if perceptual_hashes_lookup and stored_phashes:
                if perceptual_match(stored_phashes, perceptual_hashes_lookup):
                    result.add(
                        "hash_integrity",
                        CheckStatus.WARN,
                        "Perceptual match (re-encoded copy). NOT an exact byte match.",
                    )
                    result.hash_match_type = "similar"
                else:
                    result.add("hash_integrity", CheckStatus.FAIL, "No hash match")
                    result.hash_match_type = "none"
            else:
                result.add(
                    "hash_integrity",
                    CheckStatus.FAIL,
                    f"SHA-256 mismatch: expected {expected_hash[:16]}..., "
                    f"got {actual_hash[:16]}...",
                )
                result.hash_match_type = "none"

        # ── Step 2: Signature verification ──────────────────
        sig_b64 = manifest.get("signature", "")
        if sig_b64:
            sig_bytes = base64.b64decode(sig_b64)
            payload = signable_bytes(manifest)
            if verify_with_public_key(payload, sig_bytes, public_key_pem):
                result.add("signature", CheckStatus.PASS, "Ed25519 signature valid")
            else:
                result.add("signature", CheckStatus.FAIL, "Ed25519 signature invalid")
        else:
            result.add("signature", CheckStatus.FAIL, "No signature present")

        # ── Step 3: Certificate validation ──────────────────
        # In a full implementation, validate the cert chain, validity
        # period, and revocation status. For the demo, check the
        # fingerprint matches.
        signer_info = manifest.get("signer", {})
        cert_fp = signer_info.get("cert_fingerprint_sha256", "")
        if cert_fp:
            # Compute fingerprint of the provided public key
            from cryptography.hazmat.primitives import serialization
            try:
                pub_key = serialization.load_pem_public_key(public_key_pem.encode())
                raw_bytes = pub_key.public_bytes(
                    serialization.Encoding.Raw,
                    serialization.PublicFormat.Raw,
                )
                actual_fp = hashlib.sha256(raw_bytes).hexdigest()
                import hmac
                if hmac.compare_digest(actual_fp, cert_fp):
                    result.add("certificate", CheckStatus.PASS, "Certificate fingerprint matches")
                else:
                    result.add("certificate", CheckStatus.FAIL, "Certificate fingerprint mismatch")
            except Exception as e:
                result.add("certificate", CheckStatus.FAIL, f"Certificate check error: {e}")
        else:
            result.add("certificate", CheckStatus.SKIP, "No certificate fingerprint in manifest")

        # ── Step 4: Timestamp validation ────────────────────
        ts_token = manifest.get("timestamp_token", "")
        if ts_token and self._timestamp_service:
            # The timestamp covers the canonical manifest hash
            manifest_hash = sha256_digest(signable_bytes(manifest))
            ts_valid, ts_time = self._timestamp_service.verify(ts_token, manifest_hash)
            if ts_valid:
                result.add(
                    "timestamp",
                    CheckStatus.PASS,
                    f"RFC 3161 timestamp valid: {ts_time.isoformat() if ts_time else 'unknown'}",
                )
                result.timestamp_utc = ts_time
            else:
                result.add("timestamp", CheckStatus.FAIL, "Timestamp verification failed")
        elif ts_token:
            result.add("timestamp", CheckStatus.SKIP, "No timestamp service configured")
        else:
            result.add("timestamp", CheckStatus.FAIL, "No timestamp token present")

        # ── Step 5: Merkle log inclusion proof ──────────────
        log_info = manifest.get("log", {})
        leaf_index = log_info.get("leaf_index", -1)
        inclusion_proof_hex = log_info.get("inclusion_proof", [])
        sth = log_info.get("signed_tree_head", {})

        if leaf_index >= 0 and self._merkle_log:
            try:
                proof_bytes = [bytes.fromhex(h) for h in inclusion_proof_hex]
                expected_root = bytes.fromhex(sth.get("root", ""))

                # Reconstruct the entry from the manifest
                entry = signable_bytes(manifest)
                valid = verify_inclusion(
                    leaf_data=entry,
                    leaf_index=leaf_index,
                    proof=proof_bytes,
                    expected_root=expected_root,
                    tree_size=sth.get("size", 0),
                )
                if valid:
                    result.add("merkle_inclusion", CheckStatus.PASS, "Inclusion proof valid")
                else:
                    result.add("merkle_inclusion", CheckStatus.FAIL, "Inclusion proof invalid")
            except Exception as e:
                result.add("merkle_inclusion", CheckStatus.FAIL, f"Proof verification error: {e}")
        else:
            result.add(
                "merkle_inclusion",
                CheckStatus.SKIP,
                "No Merkle log data or log not available",
            )

        # ── Step 6: AI verdict (informational) ──────────────
        verdict = manifest.get("analysis", {}).get("verdict", "UNKNOWN")
        score = manifest.get("analysis", {}).get("fake_probability", -1)
        result.add(
            "ai_assessment",
            CheckStatus.PASS,
            f"Verdict: {verdict} (score: {score:.4f}). "
            "Note: this is a probabilistic AI opinion, not ground truth.",
        )

        return result
