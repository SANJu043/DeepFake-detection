"""
Export trained models to ONNX or TorchScript for deployment.

Usage:
    python -m ml.export --model spatial --weights checkpoints/spatial.pt --format onnx
    python -m ml.export --model spatial --weights checkpoints/spatial.pt --format torchscript
"""

from __future__ import annotations

import argparse
import hashlib
from pathlib import Path

import torch

from ml.models.efficientnet_b4 import EfficientNetB4Detector
from ml.models.frequency_cnn import FrequencyCNN
from ml.models.temporal_bigru import TemporalBiGRU


def export_onnx(
    model: torch.nn.Module,
    dummy_input: torch.Tensor,
    output_path: str,
    input_names: list[str] | None = None,
    output_names: list[str] | None = None,
) -> str:
    """Export model to ONNX format."""
    model.eval()
    torch.onnx.export(
        model,
        dummy_input,
        output_path,
        input_names=input_names or ["input"],
        output_names=output_names or ["score"],
        dynamic_axes={"input": {0: "batch_size"}, "score": {0: "batch_size"}},
        opset_version=17,
        do_constant_folding=True,
    )

    # Compute hash
    sha256 = hashlib.sha256(Path(output_path).read_bytes()).hexdigest()
    print(f"ONNX exported to: {output_path}")
    print(f"SHA-256: {sha256}")
    return sha256


def export_torchscript(
    model: torch.nn.Module,
    dummy_input: torch.Tensor,
    output_path: str,
) -> str:
    """Export model to TorchScript format."""
    model.eval()
    scripted = torch.jit.trace(model, dummy_input)
    scripted.save(output_path)

    sha256 = hashlib.sha256(Path(output_path).read_bytes()).hexdigest()
    print(f"TorchScript exported to: {output_path}")
    print(f"SHA-256: {sha256}")
    return sha256


def main():
    parser = argparse.ArgumentParser(description="Export models for deployment")
    parser.add_argument("--model", required=True, choices=["spatial", "frequency", "temporal"])
    parser.add_argument("--weights", required=True)
    parser.add_argument("--format", default="onnx", choices=["onnx", "torchscript"])
    parser.add_argument("--output", default=None)
    parser.add_argument("--device", default="cpu")
    args = parser.parse_args()

    device = torch.device(args.device)

    # Build model
    if args.model == "spatial":
        model = EfficientNetB4Detector(pretrained=False)
        dummy = torch.randn(1, 3, 380, 380, device=device)
    elif args.model == "frequency":
        model = FrequencyCNN()
        dummy = torch.randn(1, 3, 380, 380, device=device)
    elif args.model == "temporal":
        model = TemporalBiGRU()
        dummy = torch.randn(1, 30, 1792, device=device)
    else:
        raise ValueError(f"Unknown model: {args.model}")

    # Load weights
    state = torch.load(args.weights, map_location=device)
    if "model_state_dict" in state:
        model.load_state_dict(state["model_state_dict"])
    else:
        model.load_state_dict(state)
    model.to(device)
    model.eval()

    # Output path
    output = args.output or f"{args.model}.{'onnx' if args.format == 'onnx' else 'pt'}"

    if args.format == "onnx":
        export_onnx(model, dummy, output)
    else:
        export_torchscript(model, dummy, output)


if __name__ == "__main__":
    main()
