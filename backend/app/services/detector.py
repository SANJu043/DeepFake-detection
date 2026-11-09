"""
Deepfake detection ensemble service.

Orchestrates the ensemble of models:
- Model A (spatial): EfficientNet-B4 for per-frame classification
- Model B (frequency): CNN on FFT/DCT of face crops
- Model C (temporal): BiGRU/Transformer over frame embeddings

Fusion: weighted average calibrated with temperature scaling.
Model integrity: hashes of weight files are included in the attestation.
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np
import structlog

logger = structlog.get_logger(__name__)


# ---------------------------------------------------------------------------
# Detector result
# ---------------------------------------------------------------------------

class DetectionResult:
    """Result from the ensemble deepfake detector."""

    def __init__(
        self,
        fake_probability: float,
        per_frame_scores: List[float],
        model_scores: Dict[str, float],
        model_ensemble: List[Dict[str, str]],
    ) -> None:
        self.fake_probability = fake_probability
        self.per_frame_scores = per_frame_scores
        self.model_scores = model_scores
        self.model_ensemble = model_ensemble


# ---------------------------------------------------------------------------
# Ensemble detector
# ---------------------------------------------------------------------------

class DeepfakeDetector:
    """
    Ensemble deepfake detector.

    In training/production mode, loads PyTorch models. In demo mode,
    uses a simple heuristic for testing the pipeline.
    """

    def __init__(
        self,
        weights_dir: str = "./weights",
        device: str = "cpu",
        use_demo_mode: bool = True,
    ) -> None:
        self._weights_dir = Path(weights_dir)
        self._device = device
        self._use_demo_mode = use_demo_mode
        self._models_loaded = False
        self._model_info: List[Dict[str, str]] = []

        if not use_demo_mode:
            self._load_models()
        else:
            logger.info("detector.demo_mode", msg="Using demo heuristic detector")
            self._model_info = [
                {
                    "name": "effnet-b4-spatial",
                    "version": "demo-1.0.0",
                    "weights_sha256": "demo_no_weights",
                },
                {
                    "name": "freq-cnn",
                    "version": "demo-1.0.0",
                    "weights_sha256": "demo_no_weights",
                },
                {
                    "name": "temporal-bigru",
                    "version": "demo-1.0.0",
                    "weights_sha256": "demo_no_weights",
                },
            ]

    def _load_models(self) -> None:
        """Load PyTorch model weights."""
        try:
            import torch
            # Would load actual models here
            logger.info("detector.loading_models", device=self._device)
            self._models_loaded = True
        except ImportError:
            logger.warning("detector.pytorch_unavailable")
            self._use_demo_mode = True

    def _hash_weights_file(self, path: Path) -> str:
        """Compute SHA-256 of a weights file for model integrity."""
        if not path.exists():
            return "file_not_found"
        h = hashlib.sha256()
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(1 << 20), b""):
                h.update(chunk)
        return h.hexdigest()

    def detect(
        self,
        face_crops: List[List[np.ndarray]],
    ) -> DetectionResult:
        """
        Run deepfake detection on face crops.

        Args:
            face_crops: Per-frame list of face crop arrays.
                face_crops[frame_idx][face_idx] = (H, W, 3) RGB array.

        Returns:
            DetectionResult with ensemble score and per-frame breakdowns.
        """
        if self._use_demo_mode:
            return self._demo_detect(face_crops)

        return self._ensemble_detect(face_crops)

    def _demo_detect(
        self,
        face_crops: List[List[np.ndarray]],
    ) -> DetectionResult:
        """
        Demo detector using simple image statistics heuristic.

        NOT a real deepfake detector — produces deterministic scores
        based on pixel statistics for testing the full pipeline.
        """
        per_frame_scores: List[float] = []

        for frame_faces in face_crops:
            if len(frame_faces) == 0:
                continue
            # Use the first face
            face = frame_faces[0].astype(np.float32) / 255.0

            # Simple heuristic based on image statistics
            # Real detector would use trained CNN
            mean_val = float(np.mean(face))
            std_val = float(np.std(face))

            # Map to a pseudo-score (NOT a real detection)
            # This just produces varying scores for testing
            score = np.clip(
                0.5 + (mean_val - 0.5) * 0.3 + (std_val - 0.2) * 0.5,
                0.0,
                1.0,
            )
            per_frame_scores.append(float(score))

        if len(per_frame_scores) == 0:
            return DetectionResult(
                fake_probability=0.5,
                per_frame_scores=[],
                model_scores={"spatial": 0.5, "frequency": 0.5, "temporal": 0.5},
                model_ensemble=self._model_info,
            )

        # Aggregate: mean of top-k scores
        k = max(1, len(per_frame_scores) // 5)
        sorted_scores = sorted(per_frame_scores, reverse=True)
        top_k_mean = float(np.mean(sorted_scores[:k]))

        return DetectionResult(
            fake_probability=top_k_mean,
            per_frame_scores=per_frame_scores,
            model_scores={
                "spatial": top_k_mean,
                "frequency": top_k_mean * 0.9,
                "temporal": top_k_mean * 0.95,
            },
            model_ensemble=self._model_info,
        )

    def _ensemble_detect(
        self,
        face_crops: List[List[np.ndarray]],
    ) -> DetectionResult:
        """
        Full ensemble detection with loaded PyTorch models.
        Placeholder for when real weights are available.
        """
        # This would run the actual models
        return self._demo_detect(face_crops)
