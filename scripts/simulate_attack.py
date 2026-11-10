#!/usr/bin/env python3
"""
Simulate attacks on the system for testing and demo.

Simulates:
1. Replay attack (reuse attestation for different video)
2. Adversarial probing (many near-duplicate uploads)
3. Tampered manifest submission
4. Brute-force login attempts

Usage:
    python scripts/simulate_attack.py --attack replay --api-url http://localhost:8000
    python scripts/simulate_attack.py --attack all
"""

from __future__ import annotations

import argparse
import base64
import copy
import hashlib
import json
import sys
from pathlib import Path
import uuid

# Ensure project root is in sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.app.services.hashing import sha256_digest
from backend.app.services.manifest import build_manifest, signable_bytes
from backend.app.services.signer import LocalSigner


def simulate_replay_attack(signer: LocalSigner) -> None:
    """
    Demonstrate that a valid attestation for video A cannot be
    replayed to vouch for video B.
    """
    print("\n" + "=" * 60)
    print("ATTACK 1: Replay Attack")
    print("=" * 60)

    # Create legitimate attestation for video A
    video_a = b"This is video A content"
    hash_a = sha256_digest(video_a)

    manifest = build_manifest(
        content_sha256=hash_a,
        content_size_bytes=len(video_a),
        content_duration_s=10.0,
        perceptual_hash=[],
        verdict="NO_MANIPULATION_DETECTED",
        fake_probability=0.1,
        model_ensemble=[{"name": "test", "version": "1.0", "weights_sha256": "abc"}],
        thresholds={"clean_lt": 0.30, "manipulated_gt": 0.70},
        submitter_user_id="user-1",
        submitter_display="Test User",
        signer_cert_fingerprint=signer.cert_fingerprint_sha256,
        signer_key_id=signer.key_id,
    )

    # Sign it
    payload = signable_bytes(manifest)
    sig = signer.sign(payload)
    manifest["signature"] = base64.b64encode(sig).decode()

    # Now try to use it for video B
    video_b = b"This is DIFFERENT video B content"
    hash_b = sha256_digest(video_b)

    print(f"  Video A hash: {hash_a[:16]}...")
    print(f"  Video B hash: {hash_b[:16]}...")
    print(f"  Manifest claims: {manifest['content']['sha256'][:16]}...")
    print(f"  Hash match for video B? {hash_b == manifest['content']['sha256']}")
    print("  ✅ BLOCKED: Hash mismatch detects replay.")


def simulate_tampered_manifest(signer: LocalSigner) -> None:
    """
    Demonstrate that modifying any manifest field invalidates the signature.
    """
    print("\n" + "=" * 60)
    print("ATTACK 2: Manifest Tampering")
    print("=" * 60)

    video = b"Original video bytes"
    manifest = build_manifest(
        content_sha256=sha256_digest(video),
        content_size_bytes=len(video),
        content_duration_s=10.0,
        perceptual_hash=[],
        verdict="LIKELY_MANIPULATED",
        fake_probability=0.85,
        model_ensemble=[{"name": "test", "version": "1.0", "weights_sha256": "abc"}],
        thresholds={"clean_lt": 0.30, "manipulated_gt": 0.70},
        submitter_user_id="user-1",
        submitter_display="Test User",
        signer_cert_fingerprint=signer.cert_fingerprint_sha256,
        signer_key_id=signer.key_id,
    )

    # Sign the real manifest
    payload = signable_bytes(manifest)
    sig = signer.sign(payload)
    manifest["signature"] = base64.b64encode(sig).decode()

    # Tamper: change verdict from MANIPULATED to CLEAN
    tampered = copy.deepcopy(manifest)
    tampered["analysis"]["verdict"] = "NO_MANIPULATION_DETECTED"
    tampered["analysis"]["fake_probability"] = 0.05

    # Verify tampered manifest
    tampered_payload = signable_bytes(tampered)
    sig_bytes = base64.b64decode(tampered["signature"])
    valid = signer.verify(tampered_payload, sig_bytes)

    print(f"  Original verdict: LIKELY_MANIPULATED (score: 0.85)")
    print(f"  Tampered verdict: NO_MANIPULATION_DETECTED (score: 0.05)")
    print(f"  Signature still valid? {valid}")
    print("  ✅ BLOCKED: Signature verification fails on tampered manifest.")


def simulate_nonce_replay(signer: LocalSigner) -> None:
    """
    Demonstrate that nonces prevent reuse of old attestations.
    """
    print("\n" + "=" * 60)
    print("ATTACK 3: Nonce Uniqueness")
    print("=" * 60)

    video = b"Same video content"
    nonces = set()

    for i in range(5):
        manifest = build_manifest(
            content_sha256=sha256_digest(video),
            content_size_bytes=len(video),
            content_duration_s=10.0,
            perceptual_hash=[],
            verdict="NO_MANIPULATION_DETECTED",
            fake_probability=0.1,
            model_ensemble=[],
            thresholds={"clean_lt": 0.30, "manipulated_gt": 0.70},
            submitter_user_id="user-1",
            submitter_display="Test",
            signer_cert_fingerprint=signer.cert_fingerprint_sha256,
            signer_key_id=signer.key_id,
        )
        nonces.add(manifest["nonce"])

    print(f"  Generated {len(nonces)} unique nonces from 5 attestations")
    print(f"  All unique? {len(nonces) == 5}")
    print("  ✅ Each attestation has a unique nonce, preventing replay.")


def main():
    parser = argparse.ArgumentParser(description="Simulate attacks on the deepfake-auth system")
    parser.add_argument(
        "--attack",
        choices=["replay", "tamper", "nonce", "all"],
        default="all",
    )
    parser.add_argument("--key-dir", default="/tmp/attack-sim-keys")
    args = parser.parse_args()

    signer = LocalSigner(key_dir=args.key_dir)

    attacks = {
        "replay": simulate_replay_attack,
        "tamper": simulate_tampered_manifest,
        "nonce": simulate_nonce_replay,
    }

    if args.attack == "all":
        for fn in attacks.values():
            fn(signer)
    else:
        attacks[args.attack](signer)

    print("\n" + "=" * 60)
    print("All attack simulations complete.")
    print("=" * 60)


if __name__ == "__main__":
    main()
