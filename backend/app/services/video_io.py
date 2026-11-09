"""
Video I/O service.

Handles validation, FFmpeg-based decoding, and frame sampling.
Validates uploads by magic bytes, caps size, and probes with FFprobe
before processing.
"""

from __future__ import annotations

import io
import json
import subprocess
import tempfile
from pathlib import Path
from typing import BinaryIO, List, Optional, Tuple, Union

import cv2
import numpy as np
import structlog

logger = structlog.get_logger(__name__)

# Magic bytes for supported containers
_MAGIC_BYTES = {
    # MP4 / MOV (ftyp box)
    b"\x00\x00\x00": "mp4/mov",
    b"\x66\x74\x79\x70": "mp4/mov",
    # WebM (EBML header)
    b"\x1a\x45\xdf\xa3": "webm",
}

# Minimum file size (1 KB)
_MIN_FILE_SIZE = 1024


class VideoValidationError(Exception):
    """Raised when a video file fails validation."""
    pass


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

def validate_video(
    data: bytes,
    max_size_bytes: int = 200 * 1024 * 1024,
    allowed_extensions: Optional[List[str]] = None,
    filename: Optional[str] = None,
) -> dict:
    """
    Validate a video upload by size, magic bytes, and FFprobe metadata.

    Args:
        data: Raw file bytes.
        max_size_bytes: Maximum allowed file size.
        allowed_extensions: List of allowed extensions (e.g., ["mp4", "mov"]).
        filename: Original filename for extension checking.

    Returns:
        Dict with 'duration_s', 'width', 'height', 'fps', 'codec', 'format'.

    Raises:
        VideoValidationError: If validation fails.
    """
    # Size checks
    if len(data) < _MIN_FILE_SIZE:
        raise VideoValidationError(
            f"File too small ({len(data)} bytes). Minimum: {_MIN_FILE_SIZE}"
        )
    if len(data) > max_size_bytes:
        raise VideoValidationError(
            f"File too large ({len(data)} bytes). Maximum: {max_size_bytes}"
        )

    # Extension check
    if filename and allowed_extensions:
        ext = Path(filename).suffix.lstrip(".").lower()
        if ext not in allowed_extensions:
            raise VideoValidationError(
                f"Extension '.{ext}' not allowed. Allowed: {allowed_extensions}"
            )

    # Magic bytes check
    header = data[:12]
    valid_magic = False
    for magic, fmt in _MAGIC_BYTES.items():
        if magic in header:
            valid_magic = True
            break
    if not valid_magic:
        raise VideoValidationError("File does not match any supported video format magic bytes")

    # FFprobe validation
    return ffprobe_info(data)


def ffprobe_info(data: bytes) -> dict:
    """
    Run FFprobe on the video data and return metadata.

    Raises:
        VideoValidationError: If FFprobe fails or the file is not a valid video.
    """
    with tempfile.NamedTemporaryFile(suffix=".mp4", delete=True) as tmp:
        tmp.write(data)
        tmp.flush()

        try:
            result = subprocess.run(
                [
                    "ffprobe",
                    "-v", "quiet",
                    "-print_format", "json",
                    "-show_format",
                    "-show_streams",
                    tmp.name,
                ],
                capture_output=True,
                text=True,
                timeout=30,
            )
        except FileNotFoundError:
            logger.warning("ffprobe.not_found", msg="FFprobe not installed, skipping probe")
            return _fallback_opencv_info(data)
        except subprocess.TimeoutExpired:
            raise VideoValidationError("FFprobe timed out")

        if result.returncode != 0:
            raise VideoValidationError(f"FFprobe failed: {result.stderr[:200]}")

        try:
            probe = json.loads(result.stdout)
        except json.JSONDecodeError:
            raise VideoValidationError("FFprobe returned invalid JSON")

    # Extract video stream info
    video_stream = None
    for stream in probe.get("streams", []):
        if stream.get("codec_type") == "video":
            video_stream = stream
            break

    if video_stream is None:
        raise VideoValidationError("No video stream found in file")

    duration = float(probe.get("format", {}).get("duration", 0))
    fps_str = video_stream.get("r_frame_rate", "30/1")
    try:
        num, den = fps_str.split("/")
        fps = float(num) / float(den)
    except (ValueError, ZeroDivisionError):
        fps = 30.0

    return {
        "duration_s": duration,
        "width": int(video_stream.get("width", 0)),
        "height": int(video_stream.get("height", 0)),
        "fps": fps,
        "codec": video_stream.get("codec_name", "unknown"),
        "format": probe.get("format", {}).get("format_name", "unknown"),
    }


def _fallback_opencv_info(data: bytes) -> dict:
    """Fallback video info extraction using OpenCV when FFprobe is unavailable."""
    with tempfile.NamedTemporaryFile(suffix=".mp4", delete=True) as tmp:
        tmp.write(data)
        tmp.flush()

        cap = cv2.VideoCapture(tmp.name)
        if not cap.isOpened():
            raise VideoValidationError("Cannot open video file with OpenCV")

        fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
        frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        duration = frame_count / fps if fps > 0 else 0.0
        cap.release()

        return {
            "duration_s": duration,
            "width": width,
            "height": height,
            "fps": fps,
            "codec": "unknown",
            "format": "unknown",
        }


# ---------------------------------------------------------------------------
# Frame sampling
# ---------------------------------------------------------------------------

def sample_frames(
    data: bytes,
    interval_s: float = 0.2,
    max_frames: int = 300,
) -> Tuple[List[np.ndarray], float]:
    """
    Sample frames from video at regular intervals.

    Args:
        data: Raw video bytes.
        interval_s: Time between sampled frames (seconds).
        max_frames: Maximum number of frames to extract.

    Returns:
        (list_of_RGB_frames, duration_s)
    """
    with tempfile.NamedTemporaryFile(suffix=".mp4", delete=True) as tmp:
        tmp.write(data)
        tmp.flush()

        cap = cv2.VideoCapture(tmp.name)
        if not cap.isOpened():
            raise VideoValidationError("Cannot open video for frame sampling")

        fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        duration = total_frames / fps if fps > 0 else 0.0

        frame_interval = max(1, int(fps * interval_s))
        frames: List[np.ndarray] = []

        frame_idx = 0
        while len(frames) < max_frames:
            cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)
            ret, frame = cap.read()
            if not ret:
                break
            # Convert BGR to RGB
            frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            frames.append(frame_rgb)
            frame_idx += frame_interval

        cap.release()

    logger.info(
        "video.sampled",
        n_frames=len(frames),
        duration_s=round(duration, 2),
        interval_s=interval_s,
    )
    return frames, duration
