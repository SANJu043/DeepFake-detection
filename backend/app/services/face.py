"""
Face detection and cropping service.

Detects faces in video frames using MTCNN (from facenet-pytorch)
and crops them with a configurable margin for the deepfake ensemble.
"""

from __future__ import annotations

from typing import List, Optional, Tuple

import numpy as np
from PIL import Image

import structlog

logger = structlog.get_logger(__name__)


# ---------------------------------------------------------------------------
# Face detector wrapper
# ---------------------------------------------------------------------------

class FaceDetector:
    """
    Face detector using MTCNN from facenet-pytorch.

    Falls back to a simple center-crop if MTCNN is not available
    (e.g., in unit tests without GPU).
    """

    def __init__(
        self,
        margin: float = 0.2,
        crop_size: int = 380,
        min_face_size: int = 40,
    ) -> None:
        self.margin = margin
        self.crop_size = crop_size
        self.min_face_size = min_face_size
        self._detector = None
        self._init_detector()

    def _init_detector(self) -> None:
        try:
            from facenet_pytorch import MTCNN
            self._detector = MTCNN(
                image_size=self.crop_size,
                margin=int(self.crop_size * self.margin),
                min_face_size=self.min_face_size,
                post_process=False,  # return PIL-range [0,255]
                device="cpu",
            )
            logger.info("face.detector_loaded", backend="MTCNN")
        except ImportError:
            logger.warning("face.mtcnn_unavailable", msg="Using center crop fallback")
            self._detector = None

    def detect_and_crop(
        self,
        frame: np.ndarray,
    ) -> List[np.ndarray]:
        """
        Detect faces in a frame and return cropped face images.

        Args:
            frame: RGB numpy array (H, W, 3).

        Returns:
            List of cropped face images as numpy arrays (crop_size, crop_size, 3).
            Empty list if no faces detected.
        """
        if self._detector is not None:
            return self._detect_mtcnn(frame)
        else:
            return self._center_crop_fallback(frame)

    def _detect_mtcnn(self, frame: np.ndarray) -> List[np.ndarray]:
        """Detect faces using MTCNN."""
        pil_img = Image.fromarray(frame)

        try:
            boxes, probs = self._detector.detect(pil_img)
        except Exception as e:
            logger.warning("face.detect_error", error=str(e))
            return []

        if boxes is None or len(boxes) == 0:
            return []

        crops: List[np.ndarray] = []
        h, w = frame.shape[:2]

        for box, prob in zip(boxes, probs):
            if prob < 0.9:
                continue

            x1, y1, x2, y2 = box.astype(int)
            # Apply margin
            bw = x2 - x1
            bh = y2 - y1
            margin_x = int(bw * self.margin)
            margin_y = int(bh * self.margin)

            x1 = max(0, x1 - margin_x)
            y1 = max(0, y1 - margin_y)
            x2 = min(w, x2 + margin_x)
            y2 = min(h, y2 + margin_y)

            crop = frame[y1:y2, x1:x2]
            if crop.size == 0:
                continue

            # Resize to standard size
            pil_crop = Image.fromarray(crop)
            pil_crop = pil_crop.resize(
                (self.crop_size, self.crop_size),
                Image.LANCZOS,
            )
            crops.append(np.array(pil_crop))

        return crops

    def _center_crop_fallback(self, frame: np.ndarray) -> List[np.ndarray]:
        """Fallback: center crop when no face detector is available."""
        h, w = frame.shape[:2]
        size = min(h, w)
        y = (h - size) // 2
        x = (w - size) // 2
        crop = frame[y:y + size, x:x + size]
        pil_crop = Image.fromarray(crop)
        pil_crop = pil_crop.resize(
            (self.crop_size, self.crop_size),
            Image.LANCZOS,
        )
        return [np.array(pil_crop)]


def detect_faces_in_frames(
    frames: List[np.ndarray],
    detector: Optional[FaceDetector] = None,
    margin: float = 0.2,
    crop_size: int = 380,
) -> Tuple[List[List[np.ndarray]], bool]:
    """
    Detect and crop faces across all sampled frames.

    Args:
        frames: List of RGB frames.
        detector: FaceDetector instance (created if None).
        margin: Crop margin as fraction of face box size.
        crop_size: Output crop size in pixels.

    Returns:
        (per_frame_face_crops, any_face_detected)
        per_frame_face_crops[i] is a list of face crops for frame i.
    """
    if detector is None:
        detector = FaceDetector(margin=margin, crop_size=crop_size)

    all_crops: List[List[np.ndarray]] = []
    any_face = False

    for i, frame in enumerate(frames):
        crops = detector.detect_and_crop(frame)
        all_crops.append(crops)
        if len(crops) > 0:
            any_face = True

    logger.info(
        "face.batch_detect",
        total_frames=len(frames),
        frames_with_faces=sum(1 for c in all_crops if len(c) > 0),
        any_face=any_face,
    )
    return all_crops, any_face
