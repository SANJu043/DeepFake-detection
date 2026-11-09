"""
EfficientNet-B4 spatial deepfake detector.

Architecture:
- Backbone: EfficientNet-B4 (pretrained on ImageNet)
- Head: Global average pooling → Dropout(0.4) → Linear(1792, 1) → Sigmoid
- Input: 380×380 face crops (RGB, normalized)
- Output: fake probability ∈ [0, 1]

This is one of three ensemble members. It captures spatial artifacts:
blending seams, texture inconsistencies, and colour mismatches.
"""

from __future__ import annotations

import torch
import torch.nn as nn
from torchvision import models


class EfficientNetB4Detector(nn.Module):
    """
    Spatial deepfake detector using EfficientNet-B4.

    Fine-tunes the last two stages of EfficientNet-B4 while keeping
    earlier feature extraction layers frozen.
    """

    def __init__(self, pretrained: bool = True, dropout: float = 0.4) -> None:
        super().__init__()

        # Load backbone
        weights = models.EfficientNet_B4_Weights.IMAGENET1K_V1 if pretrained else None
        backbone = models.efficientnet_b4(weights=weights)

        # Feature extractor (all layers except classifier)
        self.features = backbone.features
        self.avgpool = nn.AdaptiveAvgPool2d(1)

        # Freeze early layers (stages 0–5), fine-tune stages 6–7
        for i, block in enumerate(self.features):
            if i < 6:
                for param in block.parameters():
                    param.requires_grad = False

        # Classification head
        in_features = 1792  # EfficientNet-B4 output channels
        self.classifier = nn.Sequential(
            nn.Dropout(p=dropout),
            nn.Linear(in_features, 1),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """
        Args:
            x: (B, 3, 380, 380) face crop tensor.

        Returns:
            (B,) tensor of fake probabilities.
        """
        features = self.features(x)
        pooled = self.avgpool(features)
        pooled = pooled.flatten(1)
        logits = self.classifier(pooled)
        return torch.sigmoid(logits).squeeze(-1)


def get_model(pretrained: bool = True, **kwargs) -> EfficientNetB4Detector:
    """Factory for creating the EfficientNet-B4 detector."""
    return EfficientNetB4Detector(pretrained=pretrained, **kwargs)
