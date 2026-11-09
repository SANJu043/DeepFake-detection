"""
Secure sharing service (Section 7.6).

Implements end-to-end encrypted sharing of videos and attestation packages
using X25519 key exchange + HKDF-SHA256 + AES-256-GCM.

Flow:
1. Each user registers an X25519 public key.
2. Sender generates ephemeral X25519 key pair.
3. Shared secret = X25519(ephemeral_private, recipient_public).
4. Derive 256-bit key with HKDF-SHA256 (random salt, context="deepfake-auth/share/v1").
5. Encrypt with AES-256-GCM (fresh 96-bit nonce, attestation_id as AAD).
6. Sender signs the envelope with Ed25519.
7. Recipient verifies sender signature, derives key, decrypts.
"""

from __future__ import annotations

import base64
import hashlib
import os
from dataclasses import dataclass
from typing import Optional, Tuple

import structlog
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric.x25519 import (
    X25519PrivateKey,
    X25519PublicKey,
)
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

from backend.app.services.signer import SignerBackend

logger = structlog.get_logger(__name__)

# HKDF context string (locked in spec)
_HKDF_INFO = b"deepfake-auth/share/v1"


# ---------------------------------------------------------------------------
# Key pair generation
# ---------------------------------------------------------------------------

def generate_x25519_keypair() -> Tuple[bytes, bytes]:
    """
    Generate an X25519 key pair.

    Returns:
        (private_key_raw_32_bytes, public_key_raw_32_bytes)
    """
    private_key = X25519PrivateKey.generate()
    public_key = private_key.public_key()

    private_raw = private_key.private_bytes(
        serialization.Encoding.Raw,
        serialization.PrivateFormat.Raw,
        serialization.NoEncryption(),
    )
    public_raw = public_key.public_bytes(
        serialization.Encoding.Raw,
        serialization.PublicFormat.Raw,
    )
    return private_raw, public_raw


# ---------------------------------------------------------------------------
# Envelope
# ---------------------------------------------------------------------------

@dataclass
class ShareEnvelope:
    """Encrypted sharing envelope."""

    ephemeral_public_key: str   # base64
    salt: str                   # base64
    nonce: str                  # base64
    ciphertext: str             # base64
    ciphertext_sha256: str      # hex
    attestation_id: str
    sender_id: str
    recipient_id: str
    sender_signature: str       # base64 (Ed25519 over the envelope fields)

    def to_dict(self) -> dict:
        return {
            "ephemeral_public_key": self.ephemeral_public_key,
            "salt": self.salt,
            "nonce": self.nonce,
            "ciphertext": self.ciphertext,
            "ciphertext_sha256": self.ciphertext_sha256,
            "attestation_id": self.attestation_id,
            "sender_id": self.sender_id,
            "recipient_id": self.recipient_id,
            "sender_signature": self.sender_signature,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "ShareEnvelope":
        return cls(**d)

    def signable_payload(self) -> bytes:
        """
        The byte sequence that the sender signs.
        Deterministic concatenation of all fields except the signature itself.
        """
        parts = [
            self.ephemeral_public_key,
            self.salt,
            self.nonce,
            self.ciphertext_sha256,
            self.attestation_id,
            self.sender_id,
            self.recipient_id,
        ]
        return "|".join(parts).encode("utf-8")


# ---------------------------------------------------------------------------
# Encrypt
# ---------------------------------------------------------------------------

def encrypt_for_recipient(
    plaintext: bytes,
    attestation_id: str,
    sender_id: str,
    recipient_id: str,
    recipient_public_key_raw: bytes,
    signer: SignerBackend,
) -> ShareEnvelope:
    """
    Encrypt *plaintext* for a specific recipient.

    Args:
        plaintext: Data to encrypt (video + package bytes).
        attestation_id: ID of the attestation being shared.
        sender_id: UUID of the sender.
        recipient_id: UUID of the recipient.
        recipient_public_key_raw: 32-byte X25519 public key of recipient.
        signer: Ed25519 signer for signing the envelope.

    Returns:
        ShareEnvelope ready for storage/transmission.
    """
    # Step 2: Generate ephemeral key pair
    ephemeral_private = X25519PrivateKey.generate()
    ephemeral_public = ephemeral_private.public_key()

    ephemeral_public_raw = ephemeral_public.public_bytes(
        serialization.Encoding.Raw,
        serialization.PublicFormat.Raw,
    )

    # Step 3: ECDH
    recipient_pub = X25519PublicKey.from_public_bytes(recipient_public_key_raw)
    shared_secret = ephemeral_private.exchange(recipient_pub)

    # Step 4: HKDF
    salt = os.urandom(32)
    derived_key = HKDF(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        info=_HKDF_INFO,
    ).derive(shared_secret)

    # Step 5: AES-256-GCM encrypt
    nonce = os.urandom(12)  # 96-bit
    aad = attestation_id.encode("utf-8")  # associated data
    aesgcm = AESGCM(derived_key)
    ciphertext = aesgcm.encrypt(nonce, plaintext, aad)

    ciphertext_hash = hashlib.sha256(ciphertext).hexdigest()

    # Build envelope (unsigned)
    envelope = ShareEnvelope(
        ephemeral_public_key=base64.b64encode(ephemeral_public_raw).decode(),
        salt=base64.b64encode(salt).decode(),
        nonce=base64.b64encode(nonce).decode(),
        ciphertext=base64.b64encode(ciphertext).decode(),
        ciphertext_sha256=ciphertext_hash,
        attestation_id=attestation_id,
        sender_id=sender_id,
        recipient_id=recipient_id,
        sender_signature="",
    )

    # Step 6: Sign
    sig = signer.sign(envelope.signable_payload())
    envelope.sender_signature = base64.b64encode(sig).decode()

    logger.info(
        "share.encrypted",
        attestation_id=attestation_id,
        sender=sender_id,
        recipient=recipient_id,
    )
    return envelope


# ---------------------------------------------------------------------------
# Decrypt
# ---------------------------------------------------------------------------

def decrypt_share(
    envelope: ShareEnvelope,
    recipient_private_key_raw: bytes,
    sender_public_key_pem: str,
) -> bytes:
    """
    Decrypt a shared envelope.

    Args:
        envelope: The ShareEnvelope to decrypt.
        recipient_private_key_raw: 32-byte X25519 private key of recipient.
        sender_public_key_pem: PEM-encoded Ed25519 public key of sender.

    Returns:
        Decrypted plaintext bytes.

    Raises:
        ValueError: If sender signature verification fails.
        cryptography.exceptions.InvalidTag: If decryption fails (wrong key,
            tampered ciphertext, or wrong associated data).
    """
    # Verify sender signature
    from backend.app.services.signer import verify_with_public_key

    sig_bytes = base64.b64decode(envelope.sender_signature)
    if not verify_with_public_key(
        envelope.signable_payload(), sig_bytes, sender_public_key_pem
    ):
        raise ValueError("Sender signature verification failed")

    # Derive shared secret
    ephemeral_pub_raw = base64.b64decode(envelope.ephemeral_public_key)
    ephemeral_pub = X25519PublicKey.from_public_bytes(ephemeral_pub_raw)

    recipient_private = X25519PrivateKey.from_private_bytes(recipient_private_key_raw)
    shared_secret = recipient_private.exchange(ephemeral_pub)

    # HKDF
    salt = base64.b64decode(envelope.salt)
    derived_key = HKDF(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        info=_HKDF_INFO,
    ).derive(shared_secret)

    # AES-256-GCM decrypt
    nonce = base64.b64decode(envelope.nonce)
    ciphertext = base64.b64decode(envelope.ciphertext)
    aad = envelope.attestation_id.encode("utf-8")

    aesgcm = AESGCM(derived_key)
    plaintext = aesgcm.decrypt(nonce, ciphertext, aad)

    logger.info("share.decrypted", attestation_id=envelope.attestation_id)
    return plaintext
