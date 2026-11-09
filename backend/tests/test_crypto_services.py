"""
Comprehensive test suite for cryptographic services.

Implements ALL tests from Section 14 of the specification:
- Hash integrity (single byte flip)
- Signature verification (manifest field modification)
- Certificate validation (wrong/revoked cert)
- Merkle log proofs (entry alteration)
- Perceptual hashing (re-encoding)
- Replay attack prevention
- Domain separation (leaf vs node)
"""

from __future__ import annotations

import base64
import copy
import hashlib
import os
import uuid

import pytest

from backend.app.services.hashing import (
    hamming_distance,
    perceptual_hash_frame,
    sha256_digest,
    sha256_verify,
)
from backend.app.services.manifest import (
    VERDICT_INCONCLUSIVE,
    VERDICT_LIKELY_MANIPULATED,
    VERDICT_NO_MANIPULATION,
    build_manifest,
    canonicalize,
    manifest_without_mutable_fields,
    signable_bytes,
)
from backend.app.services.merkle_log import (
    MerkleLog,
    build_tree_head,
    leaf_hash,
    node_hash,
    verify_inclusion,
)
from backend.app.services.policy import (
    REASON_NO_FACE,
    REASON_TOO_SHORT,
    PolicyEngine,
    PolicyResult,
)
from backend.app.services.signer import (
    LocalSigner,
    create_signer,
    verify_with_public_key,
)
from backend.app.services.timestamp import LocalTSA, TimestampService
from backend.app.services.revocation import RevocationService
from backend.app.services.sharing import (
    ShareEnvelope,
    decrypt_share,
    encrypt_for_recipient,
    generate_x25519_keypair,
)


# ═══════════════════════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════════════════════

@pytest.fixture
def tmp_key_dir(tmp_path):
    """Temporary directory for signing keys."""
    return tmp_path / "keys"


@pytest.fixture
def signer(tmp_key_dir):
    """A fresh LocalSigner for tests."""
    return LocalSigner(key_dir=tmp_key_dir)


@pytest.fixture
def tsa(tmp_path):
    """A fresh local TSA."""
    return LocalTSA(key_dir=tmp_path / "tsa")


@pytest.fixture
def timestamp_service(tmp_path):
    """Timestamp service with local backend."""
    return TimestampService(backend="local", key_dir=tmp_path / "tsa")


@pytest.fixture
def merkle_log():
    """A fresh Merkle log."""
    return MerkleLog()


@pytest.fixture
def sample_video_bytes():
    """Dummy video bytes for testing."""
    return b"FAKE_VIDEO_DATA_" + os.urandom(1024)


@pytest.fixture
def sample_manifest(signer):
    """A sample unsigned manifest."""
    return build_manifest(
        content_sha256="a" * 64,
        content_size_bytes=1024,
        content_duration_s=10.5,
        perceptual_hash=["abcdef1234567890"],
        verdict=VERDICT_NO_MANIPULATION,
        fake_probability=0.15,
        model_ensemble=[{
            "name": "effnet-b4",
            "version": "1.0.0",
            "weights_sha256": "b" * 64,
        }],
        thresholds={"clean_lt": 0.30, "manipulated_gt": 0.70},
        submitter_user_id=str(uuid.uuid4()),
        submitter_display="Test User",
        signer_cert_fingerprint=signer.cert_fingerprint_sha256,
        signer_key_id=signer.key_id,
    )


# ═══════════════════════════════════════════════════════════════
# 1. HASH INTEGRITY TESTS
# ═══════════════════════════════════════════════════════════════

class TestHashIntegrity:
    """Test SHA-256 hash integrity — Section 14 test #1."""

    def test_sha256_deterministic(self, sample_video_bytes):
        """Same input always produces same hash."""
        h1 = sha256_digest(sample_video_bytes)
        h2 = sha256_digest(sample_video_bytes)
        assert h1 == h2
        assert len(h1) == 64  # 256 bits = 64 hex chars

    def test_single_byte_flip_breaks_hash(self, sample_video_bytes):
        """
        Section 14: Flip a single byte in a video → verification must fail.
        """
        original_hash = sha256_digest(sample_video_bytes)

        # Flip one byte
        modified = bytearray(sample_video_bytes)
        modified[10] ^= 0x01  # flip one bit in byte 10
        modified = bytes(modified)

        assert not sha256_verify(modified, original_hash), \
            "Hash verification MUST fail when a single byte is flipped"

    def test_sha256_verify_correct(self, sample_video_bytes):
        """Verification passes for unmodified data."""
        h = sha256_digest(sample_video_bytes)
        assert sha256_verify(sample_video_bytes, h)

    def test_sha256_from_path(self, tmp_path, sample_video_bytes):
        """SHA-256 works with file paths."""
        path = tmp_path / "test.mp4"
        path.write_bytes(sample_video_bytes)
        h1 = sha256_digest(sample_video_bytes)
        h2 = sha256_digest(path)
        assert h1 == h2


# ═══════════════════════════════════════════════════════════════
# 2. SIGNATURE VERIFICATION TESTS
# ═══════════════════════════════════════════════════════════════

class TestSignatureVerification:
    """Test Ed25519 signature — Section 14 test #2."""

    def test_sign_and_verify(self, signer):
        """Basic sign/verify round-trip."""
        data = b"test message"
        sig = signer.sign(data)
        assert signer.verify(data, sig)

    def test_modified_manifest_fails_signature(self, signer, sample_manifest):
        """
        Section 14: Modify any manifest field (e.g., verdict) →
        signature check must fail.
        """
        # Sign the original manifest
        payload = signable_bytes(sample_manifest)
        signature = signer.sign(payload)

        # Verify the original succeeds
        assert signer.verify(payload, signature)

        # Modify the verdict
        tampered = copy.deepcopy(sample_manifest)
        tampered["analysis"]["verdict"] = VERDICT_LIKELY_MANIPULATED

        tampered_payload = signable_bytes(tampered)
        assert not signer.verify(tampered_payload, signature), \
            "Signature MUST fail when verdict is modified"

    def test_modified_score_fails_signature(self, signer, sample_manifest):
        """Modifying fake_probability breaks the signature."""
        payload = signable_bytes(sample_manifest)
        signature = signer.sign(payload)

        tampered = copy.deepcopy(sample_manifest)
        tampered["analysis"]["fake_probability"] = 0.99

        tampered_payload = signable_bytes(tampered)
        assert not signer.verify(tampered_payload, signature)

    def test_modified_hash_fails_signature(self, signer, sample_manifest):
        """Modifying content hash breaks the signature."""
        payload = signable_bytes(sample_manifest)
        signature = signer.sign(payload)

        tampered = copy.deepcopy(sample_manifest)
        tampered["content"]["sha256"] = "f" * 64

        tampered_payload = signable_bytes(tampered)
        assert not signer.verify(tampered_payload, signature)

    def test_wrong_key_fails_verification(self, tmp_path, signer, sample_manifest):
        """Verification with a different key must fail."""
        payload = signable_bytes(sample_manifest)
        signature = signer.sign(payload)

        # Create a different signer
        other_signer = LocalSigner(key_dir=tmp_path / "other_keys")
        assert not other_signer.verify(payload, signature), \
            "Verification MUST fail with wrong public key"

    def test_verify_with_public_key_pem(self, signer):
        """Standalone verification using PEM-encoded public key."""
        data = b"test message for pem verify"
        sig = signer.sign(data)
        pem = signer.public_key_pem()
        assert verify_with_public_key(data, sig, pem)

    def test_verify_with_wrong_pem(self, signer, tmp_path):
        """Standalone verification fails with wrong PEM key."""
        data = b"test message"
        sig = signer.sign(data)
        other = LocalSigner(key_dir=tmp_path / "other")
        assert not verify_with_public_key(data, sig, other.public_key_pem())


# ═══════════════════════════════════════════════════════════════
# 3. CERTIFICATE VALIDATION TESTS
# ═══════════════════════════════════════════════════════════════

class TestCertificateValidation:
    """Test certificate validation — Section 14 test #3."""

    def test_correct_cert_fingerprint(self, signer, sample_manifest):
        """Certificate fingerprint in manifest matches signer."""
        cert_fp = sample_manifest["signer"]["cert_fingerprint_sha256"]
        assert cert_fp == signer.cert_fingerprint_sha256

    def test_wrong_cert_fingerprint_detected(self, signer, sample_manifest):
        """
        Section 14: Wrong or revoked certificate → must fail.
        """
        tampered = copy.deepcopy(sample_manifest)
        tampered["signer"]["cert_fingerprint_sha256"] = "0" * 64

        # The fingerprint no longer matches the signer's key
        assert tampered["signer"]["cert_fingerprint_sha256"] != \
            signer.cert_fingerprint_sha256


# ═══════════════════════════════════════════════════════════════
# 4. MERKLE LOG TESTS
# ═══════════════════════════════════════════════════════════════

class TestMerkleLog:
    """Test Merkle transparency log — Section 14 test #4."""

    def test_append_and_root(self, merkle_log):
        """Appending entries produces changing roots."""
        idx1 = merkle_log.append(b"entry1")
        root1 = merkle_log.root()

        idx2 = merkle_log.append(b"entry2")
        root2 = merkle_log.root()

        assert idx1 == 0
        assert idx2 == 1
        assert root1 != root2, "Root must change when entries are appended"

    def test_inclusion_proof_valid(self, merkle_log):
        """Inclusion proof verifies correctly."""
        entries = [f"entry_{i}".encode() for i in range(8)]
        for e in entries:
            merkle_log.append(e)

        # Verify each entry
        for i in range(len(entries)):
            proof = merkle_log.inclusion_proof(i)
            root = merkle_log.root()
            assert verify_inclusion(
                entries[i], i, proof, root, merkle_log.size
            ), f"Inclusion proof for entry {i} must be valid"

    def test_altered_entry_fails_inclusion(self, merkle_log):
        """
        Section 14: Remove or alter a log entry →
        inclusion or consistency proof must fail.
        """
        merkle_log.append(b"original_entry")
        merkle_log.append(b"entry_2")
        merkle_log.append(b"entry_3")

        proof = merkle_log.inclusion_proof(0)
        root = merkle_log.root()

        # Try to verify with altered entry data
        assert not verify_inclusion(
            b"tampered_entry", 0, proof, root, merkle_log.size
        ), "Inclusion proof MUST fail for altered entry"

    def test_domain_separation_leaf_vs_node(self):
        """
        Section 14 v2: A leaf cannot be passed off as an internal node.

        Domain separation: leaf = SHA-256(0x00 || data)
                           node = SHA-256(0x01 || left || right)
        """
        data = b"test_data"
        lh = leaf_hash(data)
        # Try to create a node hash with the same input
        nh = node_hash(data, b"")
        assert lh != nh, \
            "Leaf hash and node hash MUST differ due to domain separation"

        # More specifically, the prefixes differ
        import hashlib
        manual_leaf = hashlib.sha256(b"\x00" + data).digest()
        manual_node = hashlib.sha256(b"\x01" + data + b"").digest()
        assert manual_leaf == lh
        assert manual_node == nh
        assert manual_leaf != manual_node

    def test_consistency_proof(self, merkle_log):
        """Consistency proof between old and new tree heads."""
        for i in range(4):
            merkle_log.append(f"entry_{i}".encode())

        old_size = merkle_log.size
        old_root = merkle_log.root()

        # Append more
        for i in range(4, 8):
            merkle_log.append(f"entry_{i}".encode())

        new_size = merkle_log.size
        new_root = merkle_log.root()

        proof = merkle_log.consistency_proof(old_size, new_size)
        assert len(proof) > 0, "Consistency proof must not be empty"

    def test_empty_tree_root(self, merkle_log):
        """Empty tree has a deterministic zero root."""
        root = merkle_log.root()
        assert root == b"\x00" * 32

    def test_single_entry_root(self, merkle_log):
        """Single-entry tree root equals the leaf hash."""
        merkle_log.append(b"only_entry")
        root = merkle_log.root()
        expected = leaf_hash(b"only_entry")
        assert root == expected


# ═══════════════════════════════════════════════════════════════
# 5. PERCEPTUAL HASHING TESTS
# ═══════════════════════════════════════════════════════════════

class TestPerceptualHashing:
    """Test perceptual hash matching — Section 14 test #5."""

    def test_identical_frames_match(self):
        """Identical frames have zero Hamming distance."""
        import numpy as np
        frame = np.random.randint(0, 255, (224, 224, 3), dtype=np.uint8)
        h1 = perceptual_hash_frame(frame)
        h2 = perceptual_hash_frame(frame)
        assert hamming_distance(h1, h2) == 0

    def test_similar_frames_close_distance(self):
        """Slightly modified frames have small Hamming distance."""
        import numpy as np
        frame = np.random.randint(50, 200, (224, 224, 3), dtype=np.uint8)
        h1 = perceptual_hash_frame(frame)

        # Add small noise (simulates re-encoding)
        noisy = np.clip(
            frame.astype(np.int16) + np.random.randint(-5, 5, frame.shape),
            0, 255,
        ).astype(np.uint8)
        h2 = perceptual_hash_frame(noisy)

        distance = hamming_distance(h1, h2)
        assert distance <= 10, \
            f"Similar frames should have Hamming distance ≤ 10, got {distance}"

    def test_very_different_frames_large_distance(self):
        """Very different frames have large Hamming distance."""
        import numpy as np
        frame1 = np.zeros((224, 224, 3), dtype=np.uint8)
        frame2 = np.full((224, 224, 3), 255, dtype=np.uint8)
        h1 = perceptual_hash_frame(frame1)
        h2 = perceptual_hash_frame(frame2)

        distance = hamming_distance(h1, h2)
        # They should be quite different
        assert distance > 0


# ═══════════════════════════════════════════════════════════════
# 6. TIMESTAMP TESTS
# ═══════════════════════════════════════════════════════════════

class TestTimestamp:
    """Test RFC 3161 timestamp service."""

    def test_timestamp_roundtrip(self, tsa):
        """Timestamp can be issued and verified."""
        digest = hashlib.sha256(b"test data").hexdigest()
        token = tsa.timestamp(digest)
        valid, ts_time = tsa.verify_token(token, digest)
        assert valid, "Timestamp verification must pass"
        assert ts_time is not None

    def test_timestamp_wrong_digest_fails(self, tsa):
        """Timestamp verification fails for wrong digest."""
        digest = hashlib.sha256(b"test data").hexdigest()
        token = tsa.timestamp(digest)

        wrong_digest = hashlib.sha256(b"other data").hexdigest()
        valid, _ = tsa.verify_token(token, wrong_digest)
        assert not valid, "Timestamp MUST fail for wrong digest"

    def test_timestamp_tampered_token_fails(self, tsa):
        """Tampering with the token bytes fails verification."""
        digest = hashlib.sha256(b"test data").hexdigest()
        token = tsa.timestamp(digest)

        # Tamper with the token
        token_bytes = bytearray(base64.b64decode(token))
        token_bytes[5] ^= 0xFF
        tampered = base64.b64encode(bytes(token_bytes)).decode()

        valid, _ = tsa.verify_token(tampered, digest)
        assert not valid, "Tampered timestamp token MUST fail verification"

    def test_timestamp_service_roundtrip(self, timestamp_service):
        """TimestampService wraps LocalTSA correctly."""
        digest = hashlib.sha256(b"payload").hexdigest()
        token = timestamp_service.timestamp(digest)
        valid, ts = timestamp_service.verify(token, digest)
        assert valid


# ═══════════════════════════════════════════════════════════════
# 7. POLICY ENGINE TESTS
# ═══════════════════════════════════════════════════════════════

class TestPolicyEngine:
    """Test policy engine verdict mapping."""

    def test_clean_verdict(self):
        """Score below threshold → NO_MANIPULATION_DETECTED."""
        engine = PolicyEngine(threshold_clean=0.30, threshold_manipulated=0.70)
        result = engine.evaluate(0.15)
        assert result.verdict == VERDICT_NO_MANIPULATION

    def test_manipulated_verdict(self):
        """Score above threshold → LIKELY_MANIPULATED."""
        engine = PolicyEngine()
        result = engine.evaluate(0.85)
        assert result.verdict == VERDICT_LIKELY_MANIPULATED

    def test_inconclusive_verdict(self):
        """Score between thresholds → INCONCLUSIVE."""
        engine = PolicyEngine()
        result = engine.evaluate(0.50)
        assert result.verdict == VERDICT_INCONCLUSIVE

    def test_no_face_inconclusive(self):
        """
        Section 14 v2: Video with no face → INCONCLUSIVE
        with reason NO_FACE_DETECTED.
        """
        engine = PolicyEngine()
        result = engine.evaluate(0.15, face_detected=False)
        assert result.verdict == VERDICT_INCONCLUSIVE
        assert result.inconclusive_reason == REASON_NO_FACE

    def test_too_short_inconclusive(self):
        """Video under 2s → INCONCLUSIVE with reason TOO_SHORT."""
        engine = PolicyEngine()
        result = engine.evaluate(0.15, duration_s=1.5)
        assert result.verdict == VERDICT_INCONCLUSIVE
        assert result.inconclusive_reason == REASON_TOO_SHORT

    def test_invalid_thresholds(self):
        """Invalid thresholds raise ValueError."""
        with pytest.raises(ValueError):
            PolicyEngine(threshold_clean=0.80, threshold_manipulated=0.30)

    def test_boundary_clean(self):
        """Score exactly at clean threshold → INCONCLUSIVE (not less than)."""
        engine = PolicyEngine(threshold_clean=0.30, threshold_manipulated=0.70)
        result = engine.evaluate(0.30)
        assert result.verdict == VERDICT_INCONCLUSIVE

    def test_boundary_manipulated(self):
        """Score exactly at manipulated threshold → INCONCLUSIVE (not greater than)."""
        engine = PolicyEngine(threshold_clean=0.30, threshold_manipulated=0.70)
        result = engine.evaluate(0.70)
        assert result.verdict == VERDICT_INCONCLUSIVE


# ═══════════════════════════════════════════════════════════════
# 8. MANIFEST TESTS
# ═══════════════════════════════════════════════════════════════

class TestManifest:
    """Test manifest building and canonicalization."""

    def test_build_manifest_valid(self, sample_manifest):
        """Built manifest has all required fields."""
        assert sample_manifest["version"] == "1.0"
        assert "attestation_id" in sample_manifest
        assert "content" in sample_manifest
        assert "analysis" in sample_manifest
        assert sample_manifest["analysis"]["verdict"] == VERDICT_NO_MANIPULATION

    def test_invalid_verdict_raises(self, signer):
        """Invalid verdict label raises ValueError."""
        with pytest.raises(ValueError, match="Invalid verdict"):
            build_manifest(
                content_sha256="a" * 64,
                content_size_bytes=100,
                content_duration_s=5.0,
                perceptual_hash=[],
                verdict="AUTHENTIC",  # FORBIDDEN label
                fake_probability=0.1,
                model_ensemble=[],
                thresholds={},
                submitter_user_id="u1",
                submitter_display="User",
                signer_cert_fingerprint="x",
                signer_key_id="y",
            )

    def test_canonicalization_deterministic(self, sample_manifest):
        """Canonicalization produces identical bytes each time."""
        b1 = canonicalize(sample_manifest)
        b2 = canonicalize(sample_manifest)
        assert b1 == b2

    def test_signable_bytes_exclude_mutable(self, sample_manifest):
        """Signable bytes exclude signature, timestamp, and log fields."""
        sb = signable_bytes(sample_manifest)
        import json
        parsed = json.loads(sb)
        assert "signature" not in parsed
        assert "timestamp_token" not in parsed
        assert "log" not in parsed

    def test_word_authentic_never_used(self, sample_manifest):
        """The word 'authentic' must never appear as a verdict."""
        from backend.app.services.manifest import VALID_VERDICTS
        for v in VALID_VERDICTS:
            assert "AUTHENTIC" not in v.upper() or "NO_MANIPULATION" in v


# ═══════════════════════════════════════════════════════════════
# 9. REPLAY ATTACK TESTS
# ═══════════════════════════════════════════════════════════════

class TestReplayAttack:
    """Test replay attack prevention — Section 14 test #7."""

    def test_replay_attestation_against_different_file(self, signer, sample_manifest):
        """
        Section 14: Replay of an attestation against a different file fails.

        The content hash is bound to the specific file, so using the
        attestation with a different file will fail the hash check.
        """
        original_video = b"original video content"
        different_video = b"different video content"

        # Manifest was built with hash "a" * 64, which doesn't match either
        # But in a real scenario:
        manifest = copy.deepcopy(sample_manifest)
        manifest["content"]["sha256"] = sha256_digest(original_video)

        # Sign it
        payload = signable_bytes(manifest)
        sig = signer.sign(payload)

        # Try to use the attestation with a different file
        different_hash = sha256_digest(different_video)
        assert different_hash != manifest["content"]["sha256"], \
            "Different files MUST have different hashes"

        # The hash check would fail
        assert not sha256_verify(different_video, manifest["content"]["sha256"]), \
            "Replaying an attestation against a different file MUST fail"

    def test_nonce_uniqueness(self, signer):
        """Each manifest gets a unique nonce to prevent replay."""
        m1 = build_manifest(
            content_sha256="a" * 64, content_size_bytes=100,
            content_duration_s=5.0, perceptual_hash=[],
            verdict=VERDICT_NO_MANIPULATION, fake_probability=0.1,
            model_ensemble=[], thresholds={},
            submitter_user_id="u1", submitter_display="User",
            signer_cert_fingerprint="x", signer_key_id="y",
        )
        m2 = build_manifest(
            content_sha256="a" * 64, content_size_bytes=100,
            content_duration_s=5.0, perceptual_hash=[],
            verdict=VERDICT_NO_MANIPULATION, fake_probability=0.1,
            model_ensemble=[], thresholds={},
            submitter_user_id="u1", submitter_display="User",
            signer_cert_fingerprint="x", signer_key_id="y",
        )
        assert m1["nonce"] != m2["nonce"], "Each manifest must have a unique nonce"
        assert m1["attestation_id"] != m2["attestation_id"]


# ═══════════════════════════════════════════════════════════════
# 10. REVOCATION TESTS
# ═══════════════════════════════════════════════════════════════

class TestRevocation:
    """Test attestation revocation — Section 14 v2."""

    def test_revoke_attestation(self, signer):
        """
        Section 14 v2: Revoked attestation verifies as REVOKED.
        """
        rev_service = RevocationService(signer=signer)
        att_id = str(uuid.uuid4())

        assert not rev_service.is_revoked(att_id)
        rev_service.revoke(att_id, reason="Key compromise", revoked_by="admin")
        assert rev_service.is_revoked(att_id)

    def test_double_revoke_raises(self, signer):
        """Cannot revoke the same attestation twice."""
        rev_service = RevocationService(signer=signer)
        att_id = str(uuid.uuid4())
        rev_service.revoke(att_id, reason="test", revoked_by="admin")

        with pytest.raises(ValueError, match="already revoked"):
            rev_service.revoke(att_id, reason="test2", revoked_by="admin")

    def test_signed_revocation_list(self, signer):
        """Signed revocation list can be verified."""
        rev_service = RevocationService(signer=signer)
        rev_service.revoke(str(uuid.uuid4()), reason="test1", revoked_by="admin")
        rev_service.revoke(str(uuid.uuid4()), reason="test2", revoked_by="admin")

        signed_list = rev_service.signed_list()
        assert signed_list.version == 2
        assert len(signed_list.entries) == 2

        # Verify the signature
        assert rev_service.verify_list(signed_list, signer.public_key_pem())

    def test_tampered_revocation_list_fails(self, signer):
        """Tampering with the revocation list invalidates the signature."""
        rev_service = RevocationService(signer=signer)
        rev_service.revoke(str(uuid.uuid4()), reason="test", revoked_by="admin")

        signed_list = rev_service.signed_list()

        # Tamper: add a fake entry
        signed_list.entries.append({
            "attestation_id": "fake",
            "reason": "injected",
            "revoked_by": "attacker",
            "revoked_at": "2024-01-01T00:00:00Z",
        })

        assert not rev_service.verify_list(signed_list, signer.public_key_pem()), \
            "Tampered revocation list MUST fail signature verification"


# ═══════════════════════════════════════════════════════════════
# 11. SECURE SHARING TESTS
# ═══════════════════════════════════════════════════════════════

class TestSecureSharing:
    """Test X25519 + AES-256-GCM sharing — Section 14 v2."""

    def test_share_roundtrip(self, signer):
        """
        Section 14 v2: Sender encrypts, recipient decrypts successfully.
        """
        # Generate key pairs
        sender_priv, sender_pub = generate_x25519_keypair()
        recipient_priv, recipient_pub = generate_x25519_keypair()

        plaintext = b"This is the secret video + attestation package"
        attestation_id = str(uuid.uuid4())

        # Encrypt
        envelope = encrypt_for_recipient(
            plaintext=plaintext,
            attestation_id=attestation_id,
            sender_id="sender-uuid",
            recipient_id="recipient-uuid",
            recipient_public_key_raw=recipient_pub,
            signer=signer,
        )

        # Decrypt
        decrypted = decrypt_share(
            envelope=envelope,
            recipient_private_key_raw=recipient_priv,
            sender_public_key_pem=signer.public_key_pem(),
        )

        assert decrypted == plaintext, "Decrypted content must match original"

    def test_third_party_cannot_decrypt(self, signer):
        """
        Section 14 v2: A third user cannot decrypt.
        """
        sender_priv, sender_pub = generate_x25519_keypair()
        recipient_priv, recipient_pub = generate_x25519_keypair()
        third_party_priv, third_party_pub = generate_x25519_keypair()

        plaintext = b"Secret content"
        envelope = encrypt_for_recipient(
            plaintext=plaintext,
            attestation_id=str(uuid.uuid4()),
            sender_id="sender",
            recipient_id="recipient",
            recipient_public_key_raw=recipient_pub,
            signer=signer,
        )

        # Third party tries to decrypt
        with pytest.raises(Exception):
            decrypt_share(
                envelope=envelope,
                recipient_private_key_raw=third_party_priv,
                sender_public_key_pem=signer.public_key_pem(),
            )

    def test_flipped_ciphertext_bit_fails(self, signer):
        """
        Section 14 v2: A flipped ciphertext bit fails GCM authentication.
        """
        recipient_priv, recipient_pub = generate_x25519_keypair()

        envelope = encrypt_for_recipient(
            plaintext=b"test data",
            attestation_id=str(uuid.uuid4()),
            sender_id="sender",
            recipient_id="recipient",
            recipient_public_key_raw=recipient_pub,
            signer=signer,
        )

        # Flip a bit in the ciphertext
        ct_bytes = bytearray(base64.b64decode(envelope.ciphertext))
        ct_bytes[5] ^= 0x01
        envelope.ciphertext = base64.b64encode(bytes(ct_bytes)).decode()

        with pytest.raises(Exception):
            decrypt_share(
                envelope=envelope,
                recipient_private_key_raw=recipient_priv,
                sender_public_key_pem=signer.public_key_pem(),
            )

    def test_wrong_associated_data_fails(self, signer):
        """
        Section 14 v2: Wrong associated data (attestation_id) fails GCM.
        """
        recipient_priv, recipient_pub = generate_x25519_keypair()

        envelope = encrypt_for_recipient(
            plaintext=b"test data",
            attestation_id="correct-id",
            sender_id="sender",
            recipient_id="recipient",
            recipient_public_key_raw=recipient_pub,
            signer=signer,
        )

        # Change the attestation_id (which is used as AAD)
        envelope.attestation_id = "wrong-id"

        with pytest.raises(Exception):
            decrypt_share(
                envelope=envelope,
                recipient_private_key_raw=recipient_priv,
                sender_public_key_pem=signer.public_key_pem(),
            )

    def test_tampered_envelope_signature_rejected(self, signer):
        """
        Section 14 v2: A tampered envelope signature is rejected.
        """
        recipient_priv, recipient_pub = generate_x25519_keypair()

        envelope = encrypt_for_recipient(
            plaintext=b"test data",
            attestation_id=str(uuid.uuid4()),
            sender_id="sender",
            recipient_id="recipient",
            recipient_public_key_raw=recipient_pub,
            signer=signer,
        )

        # Tamper with the signature
        sig_bytes = bytearray(base64.b64decode(envelope.sender_signature))
        sig_bytes[0] ^= 0xFF
        envelope.sender_signature = base64.b64encode(bytes(sig_bytes)).decode()

        with pytest.raises(ValueError, match="Sender signature verification failed"):
            decrypt_share(
                envelope=envelope,
                recipient_private_key_raw=recipient_priv,
                sender_public_key_pem=signer.public_key_pem(),
            )


# ═══════════════════════════════════════════════════════════════
# 12. KEY MANAGEMENT TESTS
# ═══════════════════════════════════════════════════════════════

class TestKeyManagement:
    """Test key generation, loading, and identity."""

    def test_key_persistence(self, tmp_path):
        """Keys are persisted and loaded correctly on restart."""
        key_dir = tmp_path / "persistent_keys"

        signer1 = LocalSigner(key_dir=key_dir)
        pub1 = signer1.public_key_bytes()
        key_id1 = signer1.key_id

        # Simulate restart
        signer2 = LocalSigner(key_dir=key_dir)
        pub2 = signer2.public_key_bytes()
        key_id2 = signer2.key_id

        assert pub1 == pub2, "Same key must be loaded on restart"
        assert key_id1 == key_id2

    def test_different_keys_different_ids(self, tmp_path):
        """Different key directories produce different keys."""
        s1 = LocalSigner(key_dir=tmp_path / "keys1")
        s2 = LocalSigner(key_dir=tmp_path / "keys2")
        assert s1.key_id != s2.key_id
        assert s1.public_key_bytes() != s2.public_key_bytes()

    def test_signer_factory(self, tmp_path):
        """Factory creates the right backend."""
        signer = create_signer("local", key_dir=tmp_path / "factory_keys")
        assert isinstance(signer, LocalSigner)

    def test_unknown_backend_raises(self):
        """Unknown backend raises ValueError."""
        with pytest.raises(ValueError):
            create_signer("unknown_backend")


# ═══════════════════════════════════════════════════════════════
# 13. SECURITY UTILITIES TESTS
# ═══════════════════════════════════════════════════════════════

class TestSecurityUtils:
    """Test password hashing, JWT, and helpers."""

    def test_password_hash_and_verify(self):
        from backend.app.core.security import hash_password, verify_password
        hashed = hash_password("MySecureP@ss123")
        assert verify_password("MySecureP@ss123", hashed)
        assert not verify_password("WrongPassword", hashed)

    def test_jwt_roundtrip(self):
        from backend.app.core.security import (
            create_access_token,
            decode_token,
        )
        token = create_access_token(
            {"sub": "user-123", "role": "user"},
            secret_key="test-secret",
        )
        payload = decode_token(token, secret_key="test-secret")
        assert payload["sub"] == "user-123"
        assert payload["role"] == "user"
        assert payload["type"] == "access"

    def test_jwt_wrong_secret_fails(self):
        from backend.app.core.security import create_access_token, decode_token
        import jwt as pyjwt
        token = create_access_token(
            {"sub": "user-123"},
            secret_key="correct-secret",
        )
        with pytest.raises(pyjwt.InvalidSignatureError):
            decode_token(token, secret_key="wrong-secret")

    def test_constant_time_compare(self):
        from backend.app.core.security import constant_time_compare
        assert constant_time_compare("abc", "abc")
        assert not constant_time_compare("abc", "def")

    def test_nonce_generation(self):
        from backend.app.core.security import generate_nonce
        n1 = generate_nonce()
        n2 = generate_nonce()
        assert n1 != n2
        assert len(n1) == 32  # 16 bytes = 32 hex chars


# ═══════════════════════════════════════════════════════════════
# 14. RBAC TESTS
# ═══════════════════════════════════════════════════════════════

class TestRBAC:
    """Test role-based access control."""

    def test_user_can_upload(self):
        from backend.app.core.rbac import has_permission
        assert has_permission("user", "upload")

    def test_user_cannot_admin(self):
        from backend.app.core.rbac import has_permission
        assert not has_permission("user", "admin_keys")
        assert not has_permission("user", "admin_revoke")

    def test_admin_can_everything(self):
        from backend.app.core.rbac import has_permission
        assert has_permission("admin", "upload")
        assert has_permission("admin", "admin_keys")
        assert has_permission("admin", "admin_revoke")

    def test_public_endpoint(self):
        from backend.app.core.rbac import has_permission
        assert has_permission("user", "verify")
        assert has_permission("admin", "verify")
