"""
Frequency-domain CNN deepfake detector.

Architecture:
- Preprocessing: 2D DCT (computed on the fly or precomputed)
- Backbone: Custom 5-layer CNN on DCT coefficients
- Head: Global average pooling → Linear(256, 1) → Sigmoid
- Input: 380×380 DCT coefficient maps (from face crops)
- Output: fake probability ∈ [0, 1]

This is one of three ensemble members. It captures frequency-domain
artifacts that GAN generators introduce (spectral peaks, missing
high-frequency detail, periodic patterns in DCT space).
"""

from __future__ import annotations

import torch
import torch.nn as nn
import torch.nn.functional as F


class DCTLayer(nn.Module):
    """
    Differentiable 2D DCT approximation using conv layers.

    For efficiency, we use a learned approximation rather than exact DCT.
    The first conv layer is initialized to approximate low-frequency DCT
    basis functions.
    """

    def __init__(self, in_channels: int = 3, out_channels: int = 32) -> None:
        super().__init__()
        self.conv = nn.Conv2d(in_channels, out_channels, kernel_size=8, stride=8, bias=False)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.conv(x)


class FrequencyCNN(nn.Module):
    """
    Frequency-domain deepfake detector.

    Applies a learned DCT-like transform followed by a 5-layer CNN
    that looks for spectral artifacts.
    """

    def __init__(self, dropout: float = 0.3) -> None:
        super().__init__()

        # DCT-like front-end
        self.dct = DCTLayer(in_channels=3, out_channels=32)

        # CNN backbone on frequency features
        self.backbone = nn.Sequential(
            # Block 1
            nn.Conv2d(32, 64, 3, padding=1),
            nn.BatchNorm2d(64),
            nn.ReLU(inplace=True),
            nn.MaxPool2d(2),

            # Block 2
            nn.Conv2d(64, 128, 3, padding=1),
            nn.BatchNorm2d(128),
            nn.ReLU(inplace=True),
            nn.MaxPool2d(2),

            # Block 3
            nn.Conv2d(128, 256, 3, padding=1),
            nn.BatchNorm2d(256),
            nn.ReLU(inplace=True),
            nn.MaxPool2d(2),

            # Block 4
            nn.Conv2d(256, 256, 3, padding=1),
            nn.BatchNorm2d(256),
            nn.ReLU(inplace=True),

            # Block 5
            nn.Conv2d(256, 256, 3, padding=1),
            nn.BatchNorm2d(256),
            nn.ReLU(inplace=True),
        )

        self.avgpool = nn.AdaptiveAvgPool2d(1)

        self.classifier = nn.Sequential(
            nn.Dropout(p=dropout),
            nn.Linear(256, 1),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """
        Args:
            x: (B, 3, 380, 380) face crop tensor.

        Returns:
            (B,) tensor of fake probabilities.
        """
        freq = self.dct(x)
        features = self.backbone(freq)
        pooled = self.avgpool(features).flatten(1)
        logits = self.classifier(pooled)
        return torch.sigmoid(logits).squeeze(-1)


def get_model(**kwargs) -> FrequencyCNN:
    """Factory for creating the Frequency CNN detector."""
    return FrequencyCNN(**kwargs)
