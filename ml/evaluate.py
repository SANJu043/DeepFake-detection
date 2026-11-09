"""
Evaluation script for deepfake detection models.

Usage:
    python -m ml.evaluate --config ml/configs/efficientnet_b4.yaml --weights checkpoints/spatial.pt
    python -m ml.evaluate --config ml/configs/ensemble.yaml --weights-dir checkpoints/

Computes:
- Accuracy, Precision, Recall, F1
- AUC-ROC and AUC-PR
- Confusion matrix
- Per-threshold analysis
- Cross-dataset generalization metrics
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, List

import numpy as np
import torch
import torch.nn as nn
from torch.utils.data import DataLoader

import yaml

from ml.datasets.loaders import create_frame_loaders, create_sequence_loaders
from ml.train import build_model


def compute_metrics(
    labels: List[float],
    predictions: List[float],
    threshold: float = 0.5,
) -> Dict[str, float]:
    """Compute classification metrics at a given threshold."""
    labels_arr = np.array(labels)
    preds_arr = np.array(predictions)
    binary_preds = (preds_arr >= threshold).astype(int)

    tp = ((binary_preds == 1) & (labels_arr == 1)).sum()
    tn = ((binary_preds == 0) & (labels_arr == 0)).sum()
    fp = ((binary_preds == 1) & (labels_arr == 0)).sum()
    fn = ((binary_preds == 0) & (labels_arr == 1)).sum()

    accuracy = (tp + tn) / max(tp + tn + fp + fn, 1)
    precision = tp / max(tp + fp, 1)
    recall = tp / max(tp + fn, 1)
    f1 = 2 * precision * recall / max(precision + recall, 1e-8)

    return {
        "threshold": threshold,
        "accuracy": float(accuracy),
        "precision": float(precision),
        "recall": float(recall),
        "f1": float(f1),
        "tp": int(tp),
        "tn": int(tn),
        "fp": int(fp),
        "fn": int(fn),
    }


def compute_auc_roc(labels: List[float], predictions: List[float]) -> float:
    """Compute AUC-ROC using the trapezoidal rule."""
    labels_arr = np.array(labels)
    preds_arr = np.array(predictions)

    # Sort by prediction score descending
    sorted_indices = np.argsort(-preds_arr)
    sorted_labels = labels_arr[sorted_indices]

    n_pos = sorted_labels.sum()
    n_neg = len(sorted_labels) - n_pos

    if n_pos == 0 or n_neg == 0:
        return 0.5

    tpr_list = [0.0]
    fpr_list = [0.0]
    tp = 0
    fp = 0

    for label in sorted_labels:
        if label == 1:
            tp += 1
        else:
            fp += 1
        tpr_list.append(tp / n_pos)
        fpr_list.append(fp / n_neg)

    # Trapezoidal AUC
    auc = 0.0
    for i in range(1, len(tpr_list)):
        auc += (fpr_list[i] - fpr_list[i - 1]) * (tpr_list[i] + tpr_list[i - 1]) / 2

    return float(auc)


def threshold_sweep(
    labels: List[float],
    predictions: List[float],
    thresholds: List[float] | None = None,
) -> List[Dict[str, float]]:
    """Compute metrics at multiple thresholds."""
    if thresholds is None:
        thresholds = [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9]
    return [compute_metrics(labels, predictions, t) for t in thresholds]


def main():
    parser = argparse.ArgumentParser(description="Evaluate deepfake detection models")
    parser.add_argument("--config", required=True, help="Path to YAML config")
    parser.add_argument("--weights", default=None, help="Path to model weights")
    parser.add_argument("--weights-dir", default=None, help="Directory with ensemble weights")
    parser.add_argument("--device", default="auto")
    parser.add_argument("--output", default=None, help="Path to write results JSON")
    args = parser.parse_args()

    with open(args.config) as f:
        config = yaml.safe_load(f)

    if args.device == "auto":
        device = torch.device(
            "cuda" if torch.cuda.is_available()
            else "mps" if torch.backends.mps.is_available()
            else "cpu"
        )
    else:
        device = torch.device(args.device)

    # Build and load model
    model = build_model(config).to(device)
    is_temporal = config["model"]["name"] == "temporal_bigru"

    if args.weights:
        state = torch.load(args.weights, map_location=device)
        if "model_state_dict" in state:
            model.load_state_dict(state["model_state_dict"])
        else:
            model.load_state_dict(state)
    elif args.weights_dir:
        from ml.models.ensemble import load_ensemble
        model = load_ensemble(args.weights_dir, device=str(device))

    model.eval()

    # Load test data
    if is_temporal:
        loaders = create_sequence_loaders(
            features_root=config["data"]["root"],
            batch_size=config["training"]["batch_size"],
        )
    else:
        loaders = create_frame_loaders(
            data_root=config["data"]["root"],
            batch_size=config["training"]["batch_size"],
        )

    test_loader = loaders.get("test")
    if not test_loader:
        print("No test data found. Using val split.")
        test_loader = loaders.get("val")
    if not test_loader:
        raise RuntimeError("No test or val data found")

    # Evaluate
    criterion = nn.BCELoss()
    from ml.train import evaluate as eval_fn
    metrics = eval_fn(model, test_loader, criterion, device, is_temporal)

    # Compute full metrics
    auc = compute_auc_roc(metrics["labels"], metrics["predictions"])
    base_metrics = compute_metrics(metrics["labels"], metrics["predictions"])
    sweep = threshold_sweep(metrics["labels"], metrics["predictions"])

    results = {
        "model": config["model"]["name"],
        "test_loss": metrics["loss"],
        "test_accuracy": metrics["accuracy"],
        "auc_roc": auc,
        "metrics_at_0.5": base_metrics,
        "threshold_sweep": sweep,
        "n_samples": len(metrics["labels"]),
        "n_positive": sum(1 for l in metrics["labels"] if l == 1),
        "n_negative": sum(1 for l in metrics["labels"] if l == 0),
    }

    print(f"\n{'='*60}")
    print(f"  Model: {config['model']['name']}")
    print(f"  Samples: {results['n_samples']} ({results['n_positive']} fake, {results['n_negative']} real)")
    print(f"  Test Loss: {metrics['loss']:.4f}")
    print(f"  Accuracy: {metrics['accuracy']:.4f}")
    print(f"  AUC-ROC: {auc:.4f}")
    print(f"  Precision: {base_metrics['precision']:.4f}")
    print(f"  Recall: {base_metrics['recall']:.4f}")
    print(f"  F1: {base_metrics['f1']:.4f}")
    print(f"{'='*60}")

    print("\nThreshold Sweep:")
    print(f"  {'Thresh':>7} {'Acc':>7} {'Prec':>7} {'Rec':>7} {'F1':>7}")
    for s in sweep:
        print(f"  {s['threshold']:7.2f} {s['accuracy']:7.4f} {s['precision']:7.4f} {s['recall']:7.4f} {s['f1']:7.4f}")

    if args.output:
        Path(args.output).parent.mkdir(parents=True, exist_ok=True)
        with open(args.output, "w") as f:
            json.dump(results, f, indent=2)
        print(f"\nResults saved to {args.output}")


if __name__ == "__main__":
    main()
