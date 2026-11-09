"""
Temporal BiGRU deepfake detector.

Architecture:
- Input: sequence of per-frame feature vectors (from EfficientNet-B4 backbone)
- Layers: 2-layer Bidirectional GRU → attention pooling → Linear(512, 1) → Sigmoid
- Output: fake probability ∈ [0, 1]

This is one of three ensemble members. It captures temporal
inconsistencies: flickering, inter-frame jitter, and unnatural
motion patterns that frame-level detectors miss.
"""

from __future__ import annotations

import torch
import torch.nn as nn
import torch.nn.functional as F


class TemporalAttention(nn.Module):
    """
    Scaled dot-product self-attention pooling over the time dimension.

    Learns which frames are most informative for the fake/real decision
    and weights them accordingly.
    """

    def __init__(self, hidden_size: int) -> None:
        super().__init__()
        self.query = nn.Linear(hidden_size, hidden_size)
        self.key = nn.Linear(hidden_size, hidden_size)
        self.scale = hidden_size ** 0.5

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """
        Args:
            x: (B, T, H) sequence of hidden states.

        Returns:
            (B, H) attention-pooled representation.
        """
        q = self.query(x)         # (B, T, H)
        k = self.key(x)           # (B, T, H)
        scores = (q * k).sum(-1) / self.scale  # (B, T)
        weights = F.softmax(scores, dim=-1)     # (B, T)
        pooled = (x * weights.unsqueeze(-1)).sum(dim=1)  # (B, H)
        return pooled


class TemporalBiGRU(nn.Module):
    """
    Temporal deepfake detector using Bidirectional GRU + attention.

    Processes a sequence of frame-level features and captures
    temporal inconsistencies across the video.
    """

    def __init__(
        self,
        input_size: int = 1792,  # EfficientNet-B4 feature dim
        hidden_size: int = 256,
        num_layers: int = 2,
        dropout: float = 0.3,
    ) -> None:
        super().__init__()

        # Optional projection if input features are high-dimensional
        self.project = nn.Linear(input_size, hidden_size) if input_size != hidden_size else nn.Identity()

        self.gru = nn.GRU(
            input_size=hidden_size,
            hidden_size=hidden_size,
            num_layers=num_layers,
            batch_first=True,
            bidirectional=True,
            dropout=dropout if num_layers > 1 else 0.0,
        )

        # BiGRU output is 2 * hidden_size
        self.attention = TemporalAttention(hidden_size * 2)

        self.classifier = nn.Sequential(
            nn.Dropout(p=dropout),
            nn.Linear(hidden_size * 2, 128),
            nn.ReLU(inplace=True),
            nn.Dropout(p=dropout / 2),
            nn.Linear(128, 1),
        )

    def forward(
        self,
        x: torch.Tensor,
        lengths: torch.Tensor | None = None,
    ) -> torch.Tensor:
        """
        Args:
            x: (B, T, D) sequence of frame features.
            lengths: (B,) optional actual sequence lengths for packing.

        Returns:
            (B,) tensor of fake probabilities.
        """
        projected = self.project(x)  # (B, T, H)

        if lengths is not None:
            packed = nn.utils.rnn.pack_padded_sequence(
                projected, lengths.cpu(), batch_first=True, enforce_sorted=False
            )
            output, _ = self.gru(packed)
            output, _ = nn.utils.rnn.pad_packed_sequence(output, batch_first=True)
        else:
            output, _ = self.gru(projected)  # (B, T, 2H)

        pooled = self.attention(output)  # (B, 2H)
        logits = self.classifier(pooled)
        return torch.sigmoid(logits).squeeze(-1)


def get_model(**kwargs) -> TemporalBiGRU:
    """Factory for creating the Temporal BiGRU detector."""
    return TemporalBiGRU(**kwargs)
