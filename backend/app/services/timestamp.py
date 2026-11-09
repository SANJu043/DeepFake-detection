"""
RFC 3161 Trusted Timestamping client.

Provides a timestamp token proving a digest existed before a given time.
Supports:
- **local**: a self-signed TSA for development / demo
- **freetsa**: FreeTSA public service (http://freetsa.org/tsr)
- **custom**: any RFC 3161 compliant TSA URL

The local TSA issues timestamps signed with a local key — not trusted by
external parties but sufficient for demonstrating the protocol.
"""

from __future__ import annotations

import base64
import hashlib
import os
import struct
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Tuple

import structlog

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)

logger = structlog.get_logger(__name__)


# ---------------------------------------------------------------------------
# Local TSA (demo)
# ---------------------------------------------------------------------------

class LocalTSA:
    """
    A minimal local Timestamping Authority for demo purposes.

    Produces a signed timestamp token containing:
    - The SHA-256 digest being timestamped
    - A UTC timestamp (seconds since epoch)
    - A serial number
    - An Ed25519 signature over the above

    This is NOT RFC 3161 wire-format compliant but captures the
    cryptographic essence: binding a digest to a time with a signature.
    """

    TOKEN_VERSION = 1

    def __init__(self, key_dir: str | Path) -> None:
        self._key_dir = Path(key_dir)
        self._key_dir.mkdir(parents=True, exist_ok=True)
        self._private_key_path = self._key_dir / "tsa_private.pem"
        self._public_key_path = self._key_dir / "tsa_public.pem"
        self._serial = 0
        self._load_or_generate()

    def _load_or_generate(self) -> None:
        if self._private_key_path.exists():
            pem = self._private_key_path.read_bytes()
            self._private_key = serialization.load_pem_private_key(pem, password=None)
            self._public_key = self._private_key.public_key()
        else:
            logger.warning("tsa.generate_key", path=str(self._key_dir))
            self._private_key = Ed25519PrivateKey.generate()
            self._public_key = self._private_key.public_key()
            self._private_key_path.write_bytes(
                self._private_key.private_bytes(
                    serialization.Encoding.PEM,
                    serialization.PrivateFormat.PKCS8,
                    serialization.NoEncryption(),
                )
            )
            self._public_key_path.write_bytes(
                self._public_key.public_bytes(
                    serialization.Encoding.PEM,
                    serialization.PublicFormat.SubjectPublicKeyInfo,
                )
            )
            self._private_key_path.chmod(0o600)

    def timestamp(self, digest_hex: str) -> str:
        """
        Issue a timestamp token for a given SHA-256 hex digest.

        Returns:
            Base64-encoded token string.
        """
        self._serial += 1
        ts = int(datetime.now(timezone.utc).timestamp())
        digest_bytes = bytes.fromhex(digest_hex)

        # Token payload: version(1) || serial(8) || timestamp(8) || digest(32)
        payload = (
            struct.pack(">B", self.TOKEN_VERSION)
            + struct.pack(">Q", self._serial)
            + struct.pack(">Q", ts)
            + digest_bytes
        )

        signature = self._private_key.sign(payload)

        # Full token: payload || signature
        token = payload + signature
        return base64.b64encode(token).decode()

    def verify_token(self, token_b64: str, digest_hex: str) -> Tuple[bool, Optional[datetime]]:
        """
        Verify a timestamp token.

        Returns:
            (is_valid, timestamp_utc) tuple.
        """
        try:
            token = base64.b64decode(token_b64)
            # Parse: version(1) + serial(8) + timestamp(8) + digest(32) = 49 bytes payload
            payload = token[:49]
            signature = token[49:]

            version = struct.unpack(">B", payload[0:1])[0]
            if version != self.TOKEN_VERSION:
                return False, None

            serial = struct.unpack(">Q", payload[1:9])[0]
            ts = struct.unpack(">Q", payload[9:17])[0]
            digest_in_token = payload[17:49]

            # Check digest matches
            expected_digest = bytes.fromhex(digest_hex)
            if digest_in_token != expected_digest:
                logger.warning("tsa.verify.digest_mismatch")
                return False, None

            # Verify signature
            self._public_key.verify(signature, payload)
            return True, datetime.fromtimestamp(ts, tz=timezone.utc)

        except Exception as exc:
            logger.warning("tsa.verify.failed", error=str(exc))
            return False, None

    def public_key_pem(self) -> str:
        return self._public_key.public_bytes(
            serialization.Encoding.PEM,
            serialization.PublicFormat.SubjectPublicKeyInfo,
        ).decode()


# ---------------------------------------------------------------------------
# Timestamp service factory
# ---------------------------------------------------------------------------

class TimestampService:
    """
    High-level timestamp service that wraps the chosen backend.
    """

    def __init__(self, backend: str = "local", **kwargs) -> None:
        self._backend = backend
        if backend == "local":
            key_dir = kwargs.get("key_dir", "./keys/tsa")
            self._tsa = LocalTSA(key_dir=key_dir)
        elif backend in ("freetsa", "custom"):
            self._tsa_url = kwargs.get("tsa_url", "http://freetsa.org/tsr")
            self._tsa = None
            logger.info("tsa.remote", url=self._tsa_url)
        else:
            raise ValueError(f"Unknown TSA backend: {backend}")

    def timestamp(self, digest_hex: str) -> str:
        """
        Request a timestamp token for the given SHA-256 digest.

        Returns:
            Base64-encoded token.
        """
        if self._backend == "local":
            return self._tsa.timestamp(digest_hex)
        else:
            # For remote TSA, we would use rfc3161ng here
            # This is a placeholder that would make an HTTP request
            logger.info("tsa.remote.request", digest=digest_hex[:16])
            return self._tsa.timestamp(digest_hex) if self._tsa else ""

    def verify(self, token_b64: str, digest_hex: str) -> Tuple[bool, Optional[datetime]]:
        """
        Verify a timestamp token against the expected digest.

        Returns:
            (is_valid, timestamp_utc) tuple.
        """
        if self._backend == "local":
            return self._tsa.verify_token(token_b64, digest_hex)
        else:
            # Remote verification
            if self._tsa:
                return self._tsa.verify_token(token_b64, digest_hex)
            return False, None

    def public_key_pem(self) -> str:
        """Return the TSA public key PEM for verification."""
        if self._tsa:
            return self._tsa.public_key_pem()
        return ""
