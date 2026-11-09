"""
GradCAM visualization for deepfake detection explainability.

Generates heatmaps showing which facial regions the model focuses on
when making its prediction. This is crucial for:
1. Debugging false positives/negatives
2. Understanding model behaviour for the report
3. Building trust (showing the model isn't random)

Usage:
    python -m ml.gradcam --model spatial --weights checkpoints/spatial.pt --image face.jpg
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Optional

import cv2
import numpy as np
import torch
import torch.nn.functional as F
from torchvision import transforms

from ml.models.efficientnet_b4 import EfficientNetB4Detector
from ml.models.frequency_cnn import FrequencyCNN


class GradCAM:
    """
    Gradient-weighted Class Activation Mapping.

    Hooks into the last convolutional layer and uses gradients
    to weight the activation maps, producing a heatmap showing
    which spatial regions drive the prediction.
    """

    def __init__(self, model: torch.nn.Module, target_layer: torch.nn.Module) -> None:
        self.model = model
        self.target_layer = target_layer
        self.gradients: Optional[torch.Tensor] = None
        self.activations: Optional[torch.Tensor] = None

        # Register hooks
        target_layer.register_forward_hook(self._forward_hook)
        target_layer.register_full_backward_hook(self._backward_hook)

    def _forward_hook(self, module, input, output):
        self.activations = output.detach()

    def _backward_hook(self, module, grad_input, grad_output):
        self.gradients = grad_output[0].detach()

    def generate(self, input_tensor: torch.Tensor) -> np.ndarray:
        """
        Generate a GradCAM heatmap for the input.

        Args:
            input_tensor: (1, 3, H, W) preprocessed face crop.

        Returns:
            (H, W) heatmap normalized to [0, 1].
        """
        self.model.eval()
        input_tensor.requires_grad_(True)

        # Forward pass
        output = self.model(input_tensor)

        # Backward pass
        self.model.zero_grad()
        output.backward()

        # Compute GradCAM
        weights = self.gradients.mean(dim=[2, 3], keepdim=True)  # (1, C, 1, 1)
        cam = (weights * self.activations).sum(dim=1, keepdim=True)  # (1, 1, h, w)
        cam = F.relu(cam)

        # Upsample to input size
        cam = F.interpolate(
            cam,
            size=input_tensor.shape[2:],
            mode="bilinear",
            align_corners=False,
        )

        # Normalize to [0, 1]
        cam = cam.squeeze().cpu().numpy()
        cam = (cam - cam.min()) / (cam.max() - cam.min() + 1e-8)

        return cam


def overlay_heatmap(
    image: np.ndarray,
    heatmap: np.ndarray,
    alpha: float = 0.5,
    colormap: int = cv2.COLORMAP_JET,
) -> np.ndarray:
    """
    Overlay a heatmap on an image.

    Args:
        image: (H, W, 3) BGR image.
        heatmap: (H, W) normalized heatmap [0, 1].
        alpha: blending factor.
        colormap: OpenCV colormap.

    Returns:
        (H, W, 3) BGR overlay image.
    """
    heatmap_colored = cv2.applyColorMap(
        (heatmap * 255).astype(np.uint8), colormap
    )
    heatmap_resized = cv2.resize(heatmap_colored, (image.shape[1], image.shape[0]))
    overlay = cv2.addWeighted(image, 1 - alpha, heatmap_resized, alpha, 0)
    return overlay


def get_target_layer(model: torch.nn.Module, model_name: str) -> torch.nn.Module:
    """Get the appropriate target layer for GradCAM based on model type."""
    if model_name == "spatial":
        # Last convolutional block of EfficientNet-B4
        return model.features[-1]
    elif model_name == "frequency":
        # Last conv layer of frequency CNN backbone
        return model.backbone[-1]
    else:
        raise ValueError(f"GradCAM not supported for model: {model_name}")


def main():
    parser = argparse.ArgumentParser(description="GradCAM visualization")
    parser.add_argument("--model", choices=["spatial", "frequency"], required=True)
    parser.add_argument("--weights", required=True, help="Path to model weights")
    parser.add_argument("--image", required=True, help="Path to face crop image")
    parser.add_argument("--output", default=None, help="Output path (default: input_gradcam.jpg)")
    parser.add_argument("--device", default="cpu")
    args = parser.parse_args()

    device = torch.device(args.device)

    # Load model
    if args.model == "spatial":
        model = EfficientNetB4Detector(pretrained=False)
    else:
        model = FrequencyCNN()

    state = torch.load(args.weights, map_location=device)
    if "model_state_dict" in state:
        model.load_state_dict(state["model_state_dict"])
    else:
        model.load_state_dict(state)
    model.to(device)

    # Load and preprocess image
    img = cv2.imread(args.image)
    if img is None:
        raise FileNotFoundError(f"Image not found: {args.image}")

    transform = transforms.Compose([
        transforms.ToPILImage(),
        transforms.Resize((380, 380)),
        transforms.ToTensor(),
        transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
    ])

    img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    input_tensor = transform(img_rgb).unsqueeze(0).to(device)

    # Generate GradCAM
    target_layer = get_target_layer(model, args.model)
    gradcam = GradCAM(model, target_layer)
    heatmap = gradcam.generate(input_tensor)

    # Get prediction
    with torch.no_grad():
        score = model(input_tensor).item()

    # Create overlay
    img_resized = cv2.resize(img, (380, 380))
    overlay = overlay_heatmap(img_resized, heatmap)

    # Add prediction text
    label = f"Score: {score:.4f} ({'FAKE' if score > 0.5 else 'REAL'})"
    cv2.putText(overlay, label, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2)

    # Save
    output_path = args.output or str(Path(args.image).stem) + "_gradcam.jpg"
    cv2.imwrite(output_path, overlay)
    print(f"GradCAM saved to: {output_path}")
    print(f"Prediction: {label}")


if __name__ == "__main__":
    main()
