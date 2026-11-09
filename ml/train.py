"""
Training script for deepfake detection models.

Usage:
    python -m ml.train --config ml/configs/efficientnet_b4.yaml
    python -m ml.train --config ml/configs/frequency_cnn.yaml
    python -m ml.train --config ml/configs/temporal_bigru.yaml
    python -m ml.train --config ml/configs/ensemble.yaml

Supports:
- Single-model training (spatial, frequency, temporal)
- Ensemble weight calibration (freeze sub-models, train weights)
- Mixed-precision (AMP) training
- Checkpoint saving and early stopping
- WandB / TensorBoard logging
"""

from __future__ import annotations

import argparse
import hashlib
import json
import time
from pathlib import Path
from typing import Any, Dict, Optional

import torch
import torch.nn as nn
from torch.cuda.amp import GradScaler, autocast
from torch.optim import AdamW
from torch.optim.lr_scheduler import CosineAnnealingLR
from torch.utils.data import DataLoader

import yaml

from ml.datasets.loaders import create_frame_loaders, create_sequence_loaders
from ml.models.efficientnet_b4 import EfficientNetB4Detector
from ml.models.frequency_cnn import FrequencyCNN
from ml.models.temporal_bigru import TemporalBiGRU
from ml.models.ensemble import DeepfakeEnsemble


# ---------------------------------------------------------------------------
# Training loop
# ---------------------------------------------------------------------------

def train_one_epoch(
    model: nn.Module,
    loader: DataLoader,
    criterion: nn.Module,
    optimizer: torch.optim.Optimizer,
    device: torch.device,
    scaler: Optional[GradScaler] = None,
    is_temporal: bool = False,
) -> Dict[str, float]:
    """Train for one epoch, return metrics."""
    model.train()
    total_loss = 0.0
    correct = 0
    total = 0

    for batch in loader:
        if is_temporal:
            features, labels, lengths = batch
            features = features.to(device)
            labels = labels.float().to(device)
            lengths = lengths.to(device)
        else:
            features, labels = batch
            features = features.to(device)
            labels = labels.float().to(device)
            lengths = None

        optimizer.zero_grad()

        if scaler:
            with autocast():
                if is_temporal:
                    preds = model(features, lengths)
                else:
                    preds = model(features)
                loss = criterion(preds, labels)
            scaler.scale(loss).backward()
            scaler.step(optimizer)
            scaler.update()
        else:
            if is_temporal:
                preds = model(features, lengths)
            else:
                preds = model(features)
            loss = criterion(preds, labels)
            loss.backward()
            optimizer.step()

        total_loss += loss.item() * labels.size(0)
        predicted = (preds > 0.5).float()
        correct += (predicted == labels).sum().item()
        total += labels.size(0)

    return {
        "loss": total_loss / max(total, 1),
        "accuracy": correct / max(total, 1),
    }


@torch.no_grad()
def evaluate(
    model: nn.Module,
    loader: DataLoader,
    criterion: nn.Module,
    device: torch.device,
    is_temporal: bool = False,
) -> Dict[str, float]:
    """Evaluate on validation/test set."""
    model.eval()
    total_loss = 0.0
    correct = 0
    total = 0
    all_preds = []
    all_labels = []

    for batch in loader:
        if is_temporal:
            features, labels, lengths = batch
            features = features.to(device)
            labels = labels.float().to(device)
            lengths = lengths.to(device)
            preds = model(features, lengths)
        else:
            features, labels = batch
            features = features.to(device)
            labels = labels.float().to(device)
            preds = model(features)

        loss = criterion(preds, labels)
        total_loss += loss.item() * labels.size(0)
        predicted = (preds > 0.5).float()
        correct += (predicted == labels).sum().item()
        total += labels.size(0)

        all_preds.extend(preds.cpu().tolist())
        all_labels.extend(labels.cpu().tolist())

    return {
        "loss": total_loss / max(total, 1),
        "accuracy": correct / max(total, 1),
        "predictions": all_preds,
        "labels": all_labels,
    }


# ---------------------------------------------------------------------------
# Model factory
# ---------------------------------------------------------------------------

def build_model(config: Dict[str, Any]) -> nn.Module:
    """Build a model from config."""
    model_name = config["model"]["name"]

    if model_name == "efficientnet_b4":
        return EfficientNetB4Detector(
            pretrained=config["model"].get("pretrained", True),
            dropout=config["model"].get("dropout", 0.4),
        )
    elif model_name == "frequency_cnn":
        return FrequencyCNN(
            dropout=config["model"].get("dropout", 0.3),
        )
    elif model_name == "temporal_bigru":
        return TemporalBiGRU(
            input_size=config["model"].get("input_size", 1792),
            hidden_size=config["model"].get("hidden_size", 256),
            num_layers=config["model"].get("num_layers", 2),
            dropout=config["model"].get("dropout", 0.3),
        )
    elif model_name == "ensemble":
        return DeepfakeEnsemble(freeze_submodels=True)
    else:
        raise ValueError(f"Unknown model: {model_name}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Train deepfake detection models")
    parser.add_argument("--config", required=True, help="Path to YAML config")
    parser.add_argument("--device", default="auto", help="Device: auto, cpu, cuda, mps")
    parser.add_argument("--resume", default=None, help="Path to checkpoint to resume from")
    args = parser.parse_args()

    # Load config
    with open(args.config) as f:
        config = yaml.safe_load(f)

    # Device
    if args.device == "auto":
        device = torch.device(
            "cuda" if torch.cuda.is_available()
            else "mps" if torch.backends.mps.is_available()
            else "cpu"
        )
    else:
        device = torch.device(args.device)

    print(f"Device: {device}")
    print(f"Config: {json.dumps(config, indent=2)}")

    # Build model
    model = build_model(config).to(device)
    is_temporal = config["model"]["name"] == "temporal_bigru"

    # Data loaders
    if is_temporal:
        loaders = create_sequence_loaders(
            features_root=config["data"]["root"],
            batch_size=config["training"]["batch_size"],
            num_workers=config["data"].get("num_workers", 2),
            max_seq_len=config["data"].get("max_seq_len", 300),
        )
    else:
        loaders = create_frame_loaders(
            data_root=config["data"]["root"],
            batch_size=config["training"]["batch_size"],
            num_workers=config["data"].get("num_workers", 4),
            max_frames_per_video=config["data"].get("max_frames_per_video", 30),
        )

    train_loader = loaders.get("train")
    val_loader = loaders.get("val")

    if not train_loader:
        raise RuntimeError(f"No training data found at {config['data']['root']}/train")

    # Criterion, optimizer, scheduler
    criterion = nn.BCELoss()
    optimizer = AdamW(
        filter(lambda p: p.requires_grad, model.parameters()),
        lr=config["training"]["lr"],
        weight_decay=config["training"].get("weight_decay", 1e-4),
    )
    scheduler = CosineAnnealingLR(
        optimizer,
        T_max=config["training"]["epochs"],
        eta_min=config["training"].get("lr_min", 1e-6),
    )

    # Mixed precision
    use_amp = config["training"].get("amp", False) and device.type == "cuda"
    scaler = GradScaler() if use_amp else None

    # Checkpointing
    output_dir = Path(config["training"].get("output_dir", "./checkpoints"))
    output_dir.mkdir(parents=True, exist_ok=True)

    # Resume
    start_epoch = 0
    best_val_loss = float("inf")
    if args.resume:
        ckpt = torch.load(args.resume, map_location=device)
        model.load_state_dict(ckpt["model_state_dict"])
        optimizer.load_state_dict(ckpt["optimizer_state_dict"])
        start_epoch = ckpt.get("epoch", 0) + 1
        best_val_loss = ckpt.get("best_val_loss", float("inf"))
        print(f"Resumed from epoch {start_epoch}")

    # Early stopping
    patience = config["training"].get("patience", 10)
    patience_counter = 0

    # Training loop
    print(f"\nTraining {config['model']['name']} for {config['training']['epochs']} epochs")
    print(f"Train: {len(train_loader.dataset)} samples | Val: {len(val_loader.dataset) if val_loader else 0} samples\n")

    for epoch in range(start_epoch, config["training"]["epochs"]):
        t0 = time.time()

        train_metrics = train_one_epoch(
            model, train_loader, criterion, optimizer, device, scaler, is_temporal
        )
        scheduler.step()

        val_metrics = {}
        if val_loader:
            val_metrics = evaluate(model, val_loader, criterion, device, is_temporal)

        elapsed = time.time() - t0
        val_loss = val_metrics.get("loss", float("inf"))
        val_acc = val_metrics.get("accuracy", 0)

        print(
            f"Epoch {epoch+1:3d}/{config['training']['epochs']} | "
            f"Train loss: {train_metrics['loss']:.4f} acc: {train_metrics['accuracy']:.4f} | "
            f"Val loss: {val_loss:.4f} acc: {val_acc:.4f} | "
            f"{elapsed:.1f}s"
        )

        # Save best
        if val_loss < best_val_loss:
            best_val_loss = val_loss
            patience_counter = 0
            torch.save(
                {
                    "epoch": epoch,
                    "model_state_dict": model.state_dict(),
                    "optimizer_state_dict": optimizer.state_dict(),
                    "best_val_loss": best_val_loss,
                    "config": config,
                },
                output_dir / f"{config['model']['name']}_best.pt",
            )
            print(f"  ↑ New best val loss: {best_val_loss:.4f}")
        else:
            patience_counter += 1
            if patience_counter >= patience:
                print(f"  Early stopping after {patience} epochs without improvement.")
                break

    # Save final weights for deployment
    torch.save(
        model.state_dict(),
        output_dir / f"{config['model']['name']}.pt",
    )

    # Compute weights hash for manifest
    weights_bytes = (output_dir / f"{config['model']['name']}.pt").read_bytes()
    weights_sha256 = hashlib.sha256(weights_bytes).hexdigest()
    print(f"\nFinal weights SHA-256: {weights_sha256}")
    print(f"Saved to: {output_dir / f'{config[\"model\"][\"name\"]}.pt'}")


if __name__ == "__main__":
    main()
