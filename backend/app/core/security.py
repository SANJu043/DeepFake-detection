"""
Security utilities: JWT, password hashing, and helper functions.

Passwords: Argon2 (argon2-cffi)
JWT: PyJWT with HS256 (short-lived access + refresh tokens)
"""

from __future__ import annotations

import hmac
import secrets
import time
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError

import structlog

logger = structlog.get_logger(__name__)

# ---------------------------------------------------------------------------
# Password hashing (Argon2)
# ---------------------------------------------------------------------------

_ph = PasswordHasher(
    time_cost=3,
    memory_cost=65536,
    parallelism=4,
    hash_len=32,
    salt_len=16,
)


def hash_password(password: str) -> str:
    """Hash a password with Argon2id."""
    return _ph.hash(password)


def verify_password(password: str, hashed: str) -> bool:
    """Verify a password against its Argon2id hash."""
    try:
        return _ph.verify(hashed, password)
    except VerifyMismatchError:
        return False


# ---------------------------------------------------------------------------
# JWT tokens
# ---------------------------------------------------------------------------

def create_access_token(
    data: Dict[str, Any],
    secret_key: str,
    algorithm: str = "HS256",
    expire_minutes: int = 30,
) -> str:
    """
    Create a JWT access token.

    Args:
        data: Payload to encode (must include 'sub' with user ID).
        secret_key: HMAC secret.
        algorithm: JWT algorithm.
        expire_minutes: Token lifetime in minutes.

    Returns:
        Encoded JWT string.
    """
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(minutes=expire_minutes)
    to_encode.update({
        "exp": expire,
        "iat": datetime.now(timezone.utc),
        "type": "access",
    })
    return jwt.encode(to_encode, secret_key, algorithm=algorithm)


def create_refresh_token(
    data: Dict[str, Any],
    secret_key: str,
    algorithm: str = "HS256",
    expire_minutes: int = 10080,
) -> str:
    """Create a JWT refresh token (longer-lived)."""
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(minutes=expire_minutes)
    to_encode.update({
        "exp": expire,
        "iat": datetime.now(timezone.utc),
        "type": "refresh",
    })
    return jwt.encode(to_encode, secret_key, algorithm=algorithm)


def decode_token(
    token: str,
    secret_key: str,
    algorithm: str = "HS256",
) -> Dict[str, Any]:
    """
    Decode and validate a JWT token.

    Raises:
        jwt.ExpiredSignatureError: Token has expired.
        jwt.InvalidTokenError: Token is invalid.
    """
    return jwt.decode(token, secret_key, algorithms=[algorithm])


# ---------------------------------------------------------------------------
# Constant-time comparison
# ---------------------------------------------------------------------------

def constant_time_compare(a: str, b: str) -> bool:
    """Constant-time string comparison to prevent timing attacks."""
    return hmac.compare_digest(a.encode(), b.encode())


# ---------------------------------------------------------------------------
# Secure random
# ---------------------------------------------------------------------------

def generate_nonce(nbytes: int = 16) -> str:
    """Generate a cryptographically secure random hex nonce."""
    return secrets.token_hex(nbytes)
