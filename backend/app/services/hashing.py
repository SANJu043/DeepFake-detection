"""
Cryptographic hashing service.

Provides SHA-256 for exact content fingerprinting and perceptual hashing
for re-encoded copy matching. SHA-256 is used throughout the attestation
pipeline; perceptual hashes are a fallback when exact bytes differ.
"""

from __future__ import annotations

import hashlib
import io
from pathlib import Path
from typing import BinaryIO, List, Optional, Sequence, Union

import imagehash
import numpy as np
from PIL import Image


# ---------------------------------------------------------------------------
# SHA-256 — exact content fingerprint
# ---------------------------------------------------------------------------

def sha256_digest(data: Union[bytes, BinaryIO, Path]) -> str:
    """
    Compute the SHA-256 hex digest of *data*.

    Args:
        data: raw bytes, a file-like object (seeked to 0), or a Path.

    Returns:
        Lowercase hex string (64 chars).
    """
    h = hashlib.sha256()
    if isinstance(data, (bytes, bytearray, memoryview)):
        h.update(data)
    elif isinstance(data, Path):
        with open(data, "rb") as f:
            for chunk in iter(lambda: f.read(1 << 20), b""):  # 1 MiB chunks
                h.update(chunk)
    else:
        # file-like
        data.seek(0)
        for chunk in iter(lambda: data.read(1 << 20), b""):
            h.update(chunk)
        data.seek(0)
    return h.hexdigest()


def sha256_verify(data: Union[bytes, BinaryIO, Path], expected: str) -> bool:
    """
    Constant-time comparison of SHA-256 digest against *expected*.

    Uses hmac.compare_digest to prevent timing attacks.
    """
    import hmac
    actual = sha256_digest(data)
    return hmac.compare_digest(actual, expected.lower())


# ---------------------------------------------------------------------------
# Perceptual hashing — survives re-encoding
# ---------------------------------------------------------------------------

def perceptual_hash_frame(frame: Union[np.ndarray, Image.Image]) -> str:
    """
    Compute a 64-bit pHash of a single frame.

    Args:
        frame: RGB numpy array (H, W, 3) or PIL Image.

    Returns:
        Hex string of the perceptual hash.
    """
    if isinstance(frame, np.ndarray):
        frame = Image.fromarray(frame)
    return str(imagehash.phash(frame))


def perceptual_hash_video(
    frames: Sequence[Union[np.ndarray, Image.Image]],
) -> List[str]:
    """
    Compute perceptual hashes for a list of sampled frames.

    Returns:
        List of hex-string hashes, one per frame.
    """
    return [perceptual_hash_frame(f) for f in frames]


def hamming_distance(hash_a: str, hash_b: str) -> int:
    """
    Hamming distance between two hex-encoded perceptual hashes.
    """
    a = imagehash.hex_to_hash(hash_a)
    b = imagehash.hex_to_hash(hash_b)
    return int(a - b)


def perceptual_match(
    hashes_a: Sequence[str],
    hashes_b: Sequence[str],
    max_distance: int = 10,
    min_match_ratio: float = 0.80,
) -> bool:
    """
    Check whether two videos are perceptually similar.

    Compares frame hashes pairwise (by index). At least *min_match_ratio* of
    the paired frames must have Hamming distance ≤ *max_distance*.

    If frame counts differ, the comparison uses the shorter list.
    """
    n = min(len(hashes_a), len(hashes_b))
    if n == 0:
        return False
    matches = sum(
        1 for i in range(n)
        if hamming_distance(hashes_a[i], hashes_b[i]) <= max_distance
    )
    return (matches / n) >= min_match_ratio
