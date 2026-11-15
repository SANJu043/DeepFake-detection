"""
Train tuned TemporalBiGRU (hidden_size 128, 1 layer, dropout 0.4, weight_decay 5e-3),
save best checkpoints, evaluate on test set, export TorchScript, and update weights/.
"""

import json
from pathlib import Path
import shutil
import sys
import numpy as np
import torch
import torch.nn as nn
from sklearn.metrics import confusion_matrix, precision_recall_fscore_support, roc_auc_score

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from ml.datasets.loaders import create_sequence_loaders
from ml.models.temporal_bigru import TemporalBiGRU

def main():
    print("=" * 60)
    print(" TRAINING TUNED TEMPORAL BIGRU (MODEL 3)")
    print("=" * 60)

    torch.manual_seed(42)
    np.random.seed(42)

    loaders = create_sequence_loaders(ROOT / "data" / "features", batch_size=16, num_workers=0)
    train_loader = loaders["train"]
    val_loader = loaders["val"]
    test_loader = loaders["test"]

    model = TemporalBiGRU(input_size=1792, hidden_size=128, num_layers=1, dropout=0.4)
    optimizer = torch.optim.AdamW(model.parameters(), lr=0.0004, weight_decay=5e-3)
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=25, eta_min=1e-6)
    criterion = nn.BCELoss()

    best_val_loss = float("inf")
    best_state = None
    best_epoch = 0

    for epoch in range(1, 26):
        model.train()
        total_loss, correct, total = 0, 0, 0
        for x, y, lengths in train_loader:
            optimizer.zero_grad()
            preds = model(x, lengths)
            loss = criterion(preds, y.float())
            loss.backward()
            optimizer.step()
            total_loss += loss.item() * len(y)
            correct += ((preds > 0.5) == y).sum().item()
            total += len(y)
        scheduler.step()
        train_acc = correct / total

        model.eval()
        val_loss, val_correct, val_total = 0, 0, 0
        with torch.no_grad():
            for x, y, lengths in val_loader:
                preds = model(x, lengths)
                loss = criterion(preds, y.float())
                val_loss += loss.item() * len(y)
                val_correct += ((preds > 0.5) == y).sum().item()
                val_total += len(y)
        v_loss = val_loss / val_total
        val_acc = val_correct / val_total

        if v_loss < best_val_loss:
            best_val_loss = v_loss
            best_epoch = epoch
            best_state = {k: v.cpu().clone() for k, v in model.state_dict().items()}
            print(f"* Epoch {epoch:2d}/25 | Train Acc: {train_acc:.4f} Loss: {total_loss/total:.4f} | Val Acc: {val_acc:.4f} Loss: {v_loss:.4f} (BEST)")
        else:
            print(f"  Epoch {epoch:2d}/25 | Train Acc: {train_acc:.4f} Loss: {total_loss/total:.4f} | Val Acc: {val_acc:.4f} Loss: {v_loss:.4f}")

    # Save best weights
    ckpt_dir = ROOT / "checkpoints"
    ckpt_dir.mkdir(parents=True, exist_ok=True)
    best_ckpt_path = ckpt_dir / "temporal_bigru_best.pt"
    torch.save(
        {
            "epoch": best_epoch,
            "model_state_dict": best_state,
            "val_loss": best_val_loss,
            "config": {
                "input_size": 1792,
                "hidden_size": 128,
                "num_layers": 1,
                "dropout": 0.4,
            },
        },
        best_ckpt_path,
    )
    torch.save(best_state, ckpt_dir / "temporal_bigru.pt")
    print(f"\nSaved best weights (epoch {best_epoch}, val_loss {best_val_loss:.4f}) to {best_ckpt_path}")

    # Evaluate on test set
    model.load_state_dict(best_state)
    model.eval()
    test_preds, test_targets = [], []
    with torch.no_grad():
        for x, y, lengths in test_loader:
            preds = model(x, lengths)
            test_preds.extend(preds.cpu().tolist())
            test_targets.extend(y.cpu().tolist())

    preds_arr = np.array(test_preds)
    targets_arr = np.array(test_targets)
    binary_preds = (preds_arr > 0.5).astype(int)
    acc = float((binary_preds == targets_arr).mean())
    auc = float(roc_auc_score(targets_arr, preds_arr))
    p, r, f1, _ = precision_recall_fscore_support(targets_arr, binary_preds, average="binary")
    cm = confusion_matrix(targets_arr, binary_preds).tolist()

    results = {
        "model": "temporal_bigru",
        "dataset": "Celeb-DF v2 (210 videos, 4200 frames)",
        "num_samples": len(targets_arr),
        "accuracy": round(acc, 4),
        "auc_roc": round(auc, 4),
        "precision": round(float(p), 4),
        "recall": round(float(r), 4),
        "f1_score": round(float(f1), 4),
        "confusion_matrix": cm,
        "best_epoch": best_epoch,
        "best_val_loss": round(best_val_loss, 4),
        "val_accuracy": round(val_acc, 4),
    }

    print("\n" + "=" * 60)
    print(" MODEL 3 (TEMPORAL BIGRU) TEST RESULTS:")
    print(f"  Test Accuracy:    {acc*100:.2f}%")
    print(f"  AUC-ROC:          {auc:.4f}")
    print(f"  Precision:        {float(p):.4f}")
    print(f"  Recall:           {float(r):.4f}")
    print(f"  F1 Score:         {float(f1):.4f}")
    print(f"  Validation Acc:   {val_acc*100:.2f}%")
    print("=" * 60)

    # Save evaluation results
    for out_name in ["eval_real_temporal_bigru.json", "results_temporal_bigru.json"]:
        (ckpt_dir / out_name).write_text(json.dumps(results, indent=2), encoding="utf-8")

    # Export to TorchScript
    print("\nExporting to TorchScript...")
    example_input = torch.randn(1, 20, 1792)
    example_lengths = torch.tensor([20], dtype=torch.long)
    try:
        scripted = torch.jit.trace(model, (example_input, example_lengths))
    except Exception:
        scripted = torch.jit.script(model)
    script_path = ckpt_dir / "temporal_scripted.pt"
    torch.jit.save(scripted, script_path)
    print(f"Saved TorchScript to {script_path}")

    # Copy to weights/
    weights_dir = ROOT / "weights"
    weights_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy(ckpt_dir / "temporal_bigru.pt", weights_dir / "temporal.pt")
    print("Copied to weights/temporal.pt")

if __name__ == "__main__":
    main()
