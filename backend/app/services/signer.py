"""
Ed25519 digital signature service.

Provides a signer abstraction with pluggable backends:
- **local**: key pair read from PEM files on disk (demo / dev)
- **softhsm**: key held in SoftHSM2 (closer to production)
- **vault**: key held in HashiCorp Vault transit engine

The application only ever calls ``signer.sign(data)`` and
``signer.verify(data, signature)``; the private key never enters
general application memory when using HSM / Vault backends.
"""

from __future__ import annotations

import base64
import hashlib
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional, Tuple

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)

import structlog

logger = structlog.get_logger(__name__)


# ---------------------------------------------------------------------------
# Abstract base
# ---------------------------------------------------------------------------

class SignerBackend(ABC):
    """Interface that all signer backends must implement."""

    @abstractmethod
    def sign(self, data: bytes) -> bytes:
        """Sign *data* and return the raw signature bytes."""

    @abstractmethod
    def verify(self, data: bytes, signature: bytes) -> bool:
        """Verify *signature* over *data*. Return True if valid."""

    @abstractmethod
    def public_key_bytes(self) -> bytes:
        """Return the raw 32-byte public key."""

    @abstractmethod
    def public_key_pem(self) -> str:
        """Return the PEM-encoded public key."""

    @property
    @abstractmethod
    def key_id(self) -> str:
        """A short identifier for the currently active key."""

    @property
    @abstractmethod
    def cert_fingerprint_sha256(self) -> str:
        """SHA-256 hex fingerprint of the signing certificate (or public key if no cert)."""


# ---------------------------------------------------------------------------
# Local file backend (demo / development)
# ---------------------------------------------------------------------------

class LocalSigner(SignerBackend):
    """
    Ed25519 signer using PEM key files on the local filesystem.

    If no key exists at *key_dir*, a new key pair is generated on first use.
    This is intended for development and demo only.
    """

    def __init__(self, key_dir: str | Path) -> None:
        self._key_dir = Path(key_dir)
        self._key_dir.mkdir(parents=True, exist_ok=True)
        self._private_key_path = self._key_dir / "ed25519_private.pem"
        self._public_key_path = self._key_dir / "ed25519_public.pem"
        self._private_key: Ed25519PrivateKey
        self._public_key: Ed25519PublicKey
        self._load_or_generate()

    def _load_or_generate(self) -> None:
        if self._private_key_path.exists():
            logger.info("signer.load_key", path=str(self._private_key_path))
            pem = self._private_key_path.read_bytes()
            self._private_key = serialization.load_pem_private_key(pem, password=None)  # type: ignore[assignment]
            self._public_key = self._private_key.public_key()
        else:
            logger.warning("signer.generate_key", path=str(self._private_key_path))
            self._private_key = Ed25519PrivateKey.generate()
            self._public_key = self._private_key.public_key()
            # Save private key
            self._private_key_path.write_bytes(
                self._private_key.private_bytes(
                    serialization.Encoding.PEM,
                    serialization.PrivateFormat.PKCS8,
                    serialization.NoEncryption(),
                )
            )
            # Save public key
            self._public_key_path.write_bytes(
                self._public_key.public_bytes(
                    serialization.Encoding.PEM,
                    serialization.PublicFormat.SubjectPublicKeyInfo,
                )
            )
            # Restrict permissions
            self._private_key_path.chmod(0o600)

    # ── SignerBackend interface ──────────────────────────────

    def sign(self, data: bytes) -> bytes:
        """Sign data with the Ed25519 private key."""
        return self._private_key.sign(data)

    def verify(self, data: bytes, signature: bytes) -> bool:
        """Verify an Ed25519 signature. Returns False on invalid."""
        try:
            self._public_key.verify(signature, data)
            return True
        except InvalidSignature:
            return False

    def public_key_bytes(self) -> bytes:
        return self._public_key.public_bytes(
            serialization.Encoding.Raw,
            serialization.PublicFormat.Raw,
        )

    def public_key_pem(self) -> str:
        return self._public_key.public_bytes(
            serialization.Encoding.PEM,
            serialization.PublicFormat.SubjectPublicKeyInfo,
        ).decode()

    @property
    def key_id(self) -> str:
        """Key ID = first 16 hex chars of SHA-256 of the raw public key."""
        digest = hashlib.sha256(self.public_key_bytes()).hexdigest()
        return digest[:16]

    @property
    def cert_fingerprint_sha256(self) -> str:
        """
        Without a real certificate, return SHA-256 of the raw public key
        as a stand-in fingerprint.
        """
        return hashlib.sha256(self.public_key_bytes()).hexdigest()


# ---------------------------------------------------------------------------
# Standalone verify helper (for public verification endpoint)
# ---------------------------------------------------------------------------

def verify_with_public_key(
    data: bytes,
    signature: bytes,
    public_key_pem: str,
) -> bool:
    """
    Verify an Ed25519 signature given a PEM-encoded public key.

    Used by the public verification endpoint where the signer backend
    is not available — only the public key from the certificate.
    """
    try:
        pub = serialization.load_pem_public_key(public_key_pem.encode())
        if not isinstance(pub, Ed25519PublicKey):
            logger.error("verify.wrong_key_type", key_type=type(pub).__name__)
            return False
        pub.verify(signature, data)
        return True
    except (InvalidSignature, Exception) as exc:
        logger.warning("verify.failed", error=str(exc))
        return False


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------

def create_signer(backend: str = "local", **kwargs) -> SignerBackend:
    """
    Factory function to create the appropriate signer backend.

    Args:
        backend: One of 'local', 'softhsm', 'vault'.
        **kwargs: Backend-specific arguments (key_dir, etc.).
    """
    if backend == "local":
        key_dir = kwargs.get("key_dir", "./keys")
        return LocalSigner(key_dir=key_dir)
    elif backend == "softhsm":
        # SoftHSM backend would be implemented here for production
        raise NotImplementedError(
            "SoftHSM backend requires SoftHSM2 installation. "
            "See deploy/softhsm-setup.md for instructions."
        )
    elif backend == "vault":
        # Vault transit backend would be implemented here
        raise NotImplementedError(
            "Vault backend requires a running Vault instance. "
            "See deploy/vault-config.md for instructions."
        )
    else:
        raise ValueError(f"Unknown signer backend: {backend}")
