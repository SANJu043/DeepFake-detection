"""
Weighted ensemble of the three deepfake detection models.

Architecture:
- EfficientNet-B4 (spatial) → score_s
- FrequencyCNN (frequency)  → score_f
- TemporalBiGRU (temporal)  → score_t
- Final: w_s * score_s + w_f * score_f + w_t * score_t

The weights are learnable (softmax-normalized) and trained on the
validation set after the individual models are frozen.

When temporal features are unavailable (single-frame input),
the ensemble falls back to a 2-model weighted average.
"""

from __future__ import annotations

from pathlib import Path
from typing import Dict, Optional

import torch
import torch.nn as nn
import torch.nn.functional as F

from ml.models.efficientnet_b4 import EfficientNetB4Detector
from ml.models.frequency_cnn import FrequencyCNN
from ml.models.temporal_bigru import TemporalBiGRU


class DeepfakeEnsemble(nn.Module):
    """
    Weighted ensemble combining spatial, frequency, and temporal detectors.

    Each sub-model produces a fake probability in [0, 1]. The ensemble
    combines them with learnable softmax-normalized weights.
    """

    def __init__(
        self,
        spatial_model: Optional[EfficientNetB4Detector] = None,
        frequency_model: Optional[FrequencyCNN] = None,
        temporal_model: Optional[TemporalBiGRU] = None,
        freeze_submodels: bool = True,
    ) -> None:
        super().__init__()

        self.spatial = spatial_model or EfficientNetB4Detector(pretrained=True)
        self.frequency = frequency_model or FrequencyCNN()
        self.temporal = temporal_model or TemporalBiGRU()

        # Learnable logits for ensemble weights (softmax-normalized)
        self.weight_logits = nn.Parameter(torch.tensor([1.0, 0.8, 0.6]))

        if freeze_submodels:
            for model in [self.spatial, self.frequency, self.temporal]:
                for param in model.parameters():
                    param.requires_grad = False

    @property
    def weights(self) -> torch.Tensor:
        """Softmax-normalized ensemble weights."""
        return F.softmax(self.weight_logits, dim=0)

    def forward(
        self,
        frames: torch.Tensor,
        frame_features: Optional[torch.Tensor] = None,
        lengths: Optional[torch.Tensor] = None,
    ) -> Dict[str, torch.Tensor]:
        """
        Run the full ensemble.

        Args:
            frames: (B, 3, 380, 380) face crop tensor for spatial + frequency.
            frame_features: (B, T, D) optional temporal features for BiGRU.
                If None, temporal model is skipped and weights renormalized.
            lengths: (B,) optional sequence lengths for temporal model.

        Returns:
            Dict with keys:
                - "score": (B,) final ensemble fake probability
                - "spatial_score": (B,) spatial model score
                - "frequency_score": (B,) frequency model score
                - "temporal_score": (B,) temporal model score (or zeros)
                - "weights": (3,) ensemble weights used
        """
        w = self.weights

        # Spatial model
        spatial_score = self.spatial(frames)           # (B,)
        frequency_score = self.frequency(frames)       # (B,)

        if frame_features is not None:
            temporal_score = self.temporal(frame_features, lengths)  # (B,)
            score = (
                w[0] * spatial_score
                + w[1] * frequency_score
                + w[2] * temporal_score
            )
        else:
            # Fall back to 2-model ensemble
            w2 = F.softmax(self.weight_logits[:2], dim=0)
            temporal_score = torch.zeros_like(spatial_score)
            score = w2[0] * spatial_score + w2[1] * frequency_score

        return {
            "score": score,
            "spatial_score": spatial_score,
            "frequency_score": frequency_score,
            "temporal_score": temporal_score,
            "weights": w.detach(),
        }

    def predict_score(self, frames: torch.Tensor, **kwargs) -> float:
        """Convenience: return a single float score for one input."""
        self.eval()
        with torch.no_grad():
            result = self.forward(frames, **kwargs)
            return result["score"].mean().item()


def load_ensemble(
    weights_dir: str | Path,
    device: str = "cpu",
) -> DeepfakeEnsemble:
    """
    Load a trained ensemble from disk.

    Expects:
        weights_dir/spatial.pt
        weights_dir/frequency.pt
        weights_dir/temporal.pt
        weights_dir/ensemble.pt (optional, for ensemble weights only)
    """
    weights_dir = Path(weights_dir)

    spatial = EfficientNetB4Detector(pretrained=False)
    frequency = FrequencyCNN()
    temporal = TemporalBiGRU()

    spatial_path = weights_dir / "spatial.pt"
    if spatial_path.exists():
        spatial.load_state_dict(torch.load(spatial_path, map_location=device))

    freq_path = weights_dir / "frequency.pt"
    if freq_path.exists():
        frequency.load_state_dict(torch.load(freq_path, map_location=device))

    temp_path = weights_dir / "temporal.pt"
    if temp_path.exists():
        temporal.load_state_dict(torch.load(temp_path, map_location=device))

    ensemble = DeepfakeEnsemble(
        spatial_model=spatial,
        frequency_model=frequency,
        temporal_model=temporal,
        freeze_submodels=True,
    )

    ens_path = weights_dir / "ensemble.pt"
    if ens_path.exists():
        state = torch.load(ens_path, map_location=device)
        ensemble.weight_logits.data = state["weight_logits"]

    ensemble.to(device)
    ensemble.eval()
    return ensemble
