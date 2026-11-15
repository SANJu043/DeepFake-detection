"""
End-to-end GPU training pipeline for all 3 models on RTX 3050.
Trains on the expanded diverse dataset (21,500+ images and 280+ video sequences).
"""

import os
import sys
import time
import hashlib
from pathlib import Path
import numpy as np
import torch
import torch.nn as nn
from torch.amp import autocast, GradScaler
from torch.optim import AdamW
from torch.optim.lr_scheduler import CosineAnnealingLR
from torch.utils.data import DataLoader
from torchvision import transforms
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from ml.datasets.loaders import FrameDataset, create_sequence_loaders
from ml.models.frequency_cnn import FrequencyCNN
from ml.models.efficientnet_b4 import EfficientNetB4Detector
from ml.models.temporal_bigru import TemporalBiGRU

device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
print("=" * 65)
print(f"  GPU ACCELERATED DEEPFAKE RETRAINING PIPELINE")
print(f"  Target Device: {device} ({torch.cuda.get_device_name(0) if device.type == 'cuda' else 'CPU'})")
print("=" * 65, flush=True)

WEIGHTS_DIR = ROOT / "weights"
WEIGHTS_DIR.mkdir(parents=True, exist_ok=True)
CHECKPOINTS_DIR = ROOT / "checkpoints"
CHECKPOINTS_DIR.mkdir(parents=True, exist_ok=True)

# ---------------------------------------------------------------------------
# 1. Train FrequencyCNN (Model 2)
# ---------------------------------------------------------------------------
def train_frequency_model(epochs=6, batch_size=32):
    print("\n" + "=" * 65)
    print(" [STAGE 1/4] Training Model 2: FrequencyCNN (DCT Domain)")
    print("=" * 65, flush=True)

    train_ds = FrameDataset(ROOT / "data" / "frames" / "train", max_frames_per_video=10, split="train")
    val_ds = FrameDataset(ROOT / "data" / "frames" / "val", max_frames_per_video=10, split="val")

    train_loader = DataLoader(train_ds, batch_size=batch_size, shuffle=True, num_workers=0, pin_memory=True)
    val_loader = DataLoader(val_ds, batch_size=batch_size, shuffle=False, num_workers=0, pin_memory=True)

    print(f"Train samples: {len(train_ds)} | Val samples: {len(val_ds)}")

    model = FrequencyCNN(dropout=0.3).to(device)
    optimizer = AdamW(model.parameters(), lr=0.0004, weight_decay=1e-4)
    scheduler = CosineAnnealingLR(optimizer, T_max=epochs, eta_min=1e-6)
    criterion = nn.BCELoss()
    scaler = GradScaler("cuda") if device.type == "cuda" else None

    best_val_loss = float("inf")
    best_weights = None

    for epoch in range(1, epochs + 1):
        t0 = time.time()
        model.train()
        train_loss, train_corr, train_tot = 0.0, 0, 0
        for x, y in train_loader:
            x, y = x.to(device), y.float().to(device)
            optimizer.zero_grad()
            if scaler:
                with autocast("cuda"):
                    preds = model(x)
                loss = nn.functional.binary_cross_entropy(preds.float().clamp(1e-7, 1.0 - 1e-7), y)
                scaler.scale(loss).backward()
                scaler.step(optimizer)
                scaler.update()
            else:
                preds = model(x)
                loss = nn.functional.binary_cross_entropy(preds.clamp(1e-7, 1.0 - 1e-7), y)
                loss.backward()
                optimizer.step()

            train_loss += loss.item() * len(y)
            train_corr += ((preds > 0.5) == y).sum().item()
            train_tot += len(y)
        scheduler.step()

        model.eval()
        val_loss, val_corr, val_tot = 0.0, 0, 0
        with torch.no_grad():
            for x, y in val_loader:
                x, y = x.to(device), y.float().to(device)
                if scaler:
                    with autocast("cuda"):
                        preds = model(x)
                else:
                    preds = model(x)
                loss = nn.functional.binary_cross_entropy(preds.float().clamp(1e-7, 1.0 - 1e-7), y)
                val_loss += loss.item() * len(y)
                val_corr += ((preds > 0.5) == y).sum().item()
                val_tot += len(y)

        elapsed = time.time() - t0
        tr_l, tr_a = train_loss / train_tot, train_corr / train_tot
        v_l, v_a = val_loss / val_tot, val_corr / val_tot
        print(f"Epoch {epoch:2d}/{epochs} | Train loss: {tr_l:.4f} acc: {tr_a:.4f} | Val loss: {v_l:.4f} acc: {v_a:.4f} | {elapsed:.1f}s", flush=True)

        if v_l < best_val_loss:
            best_val_loss = v_l
            best_weights = model.state_dict().copy()

    # Save to weights/frequency.pt
    out_path = WEIGHTS_DIR / "frequency.pt"
    torch.save(best_weights or model.state_dict(), out_path)
    print(f"-> FrequencyCNN weights saved to {out_path} (Val loss: {best_val_loss:.4f})")

# ---------------------------------------------------------------------------
# 2. Train EfficientNet-B4 (Model 1)
# ---------------------------------------------------------------------------
def train_spatial_model(epochs=4, batch_size=16):
    print("\n" + "=" * 65)
    print(" [STAGE 2/4] Training Model 1: EfficientNet-B4 (Spatial Domain)")
    print("=" * 65, flush=True)

    train_ds = FrameDataset(ROOT / "data" / "frames" / "train", max_frames_per_video=8, split="train")
    val_ds = FrameDataset(ROOT / "data" / "frames" / "val", max_frames_per_video=8, split="val")

    train_loader = DataLoader(train_ds, batch_size=batch_size, shuffle=True, num_workers=0, pin_memory=True)
    val_loader = DataLoader(val_ds, batch_size=batch_size, shuffle=False, num_workers=0, pin_memory=True)

    print(f"Train samples: {len(train_ds)} | Val samples: {len(val_ds)}")

    model = EfficientNetB4Detector(pretrained=True, dropout=0.35).to(device)
    optimizer = AdamW(model.parameters(), lr=0.0001, weight_decay=1e-4)
    scheduler = CosineAnnealingLR(optimizer, T_max=epochs, eta_min=1e-6)
    criterion = nn.BCELoss()
    scaler = GradScaler("cuda") if device.type == "cuda" else None

    best_val_loss = float("inf")
    best_weights = None

    for epoch in range(1, epochs + 1):
        t0 = time.time()
        model.train()
        train_loss, train_corr, train_tot = 0.0, 0, 0
        for x, y in train_loader:
            x, y = x.to(device), y.float().to(device)
            optimizer.zero_grad()
            if scaler:
                with autocast("cuda"):
                    preds = model(x)
                loss = nn.functional.binary_cross_entropy(preds.float().clamp(1e-7, 1.0 - 1e-7), y)
                scaler.scale(loss).backward()
                scaler.step(optimizer)
                scaler.update()
            else:
                preds = model(x)
                loss = nn.functional.binary_cross_entropy(preds.clamp(1e-7, 1.0 - 1e-7), y)
                loss.backward()
                optimizer.step()

            train_loss += loss.item() * len(y)
            train_corr += ((preds > 0.5) == y).sum().item()
            train_tot += len(y)
        scheduler.step()

        model.eval()
        val_loss, val_corr, val_tot = 0.0, 0, 0
        with torch.no_grad():
            for x, y in val_loader:
                x, y = x.to(device), y.float().to(device)
                if scaler:
                    with autocast("cuda"):
                        preds = model(x)
                else:
                    preds = model(x)
                loss = nn.functional.binary_cross_entropy(preds.float().clamp(1e-7, 1.0 - 1e-7), y)
                val_loss += loss.item() * len(y)
                val_corr += ((preds > 0.5) == y).sum().item()
                val_tot += len(y)

        elapsed = time.time() - t0
        tr_l, tr_a = train_loss / train_tot, train_corr / train_tot
        v_l, v_a = val_loss / val_tot, val_corr / val_tot
        print(f"Epoch {epoch:2d}/{epochs} | Train loss: {tr_l:.4f} acc: {tr_a:.4f} | Val loss: {v_l:.4f} acc: {v_a:.4f} | {elapsed:.1f}s", flush=True)

        if v_l < best_val_loss:
            best_val_loss = v_l
            best_weights = model.state_dict().copy()

    # Save to weights/spatial.pt
    out_path = WEIGHTS_DIR / "spatial.pt"
    torch.save(best_weights or model.state_dict(), out_path)
    print(f"-> EfficientNet-B4 weights saved to {out_path} (Val loss: {best_val_loss:.4f})")

# ---------------------------------------------------------------------------
# 3. Extract Video Features with new EfficientNet-B4
# ---------------------------------------------------------------------------
def extract_all_video_features():
    print("\n" + "=" * 65)
    print(" [STAGE 3/4] Extracting Video Sequence Features on GPU")
    print("=" * 65, flush=True)

    spatial_weights = WEIGHTS_DIR / "spatial.pt"
    model = EfficientNetB4Detector(pretrained=False).to(device)
    model.load_state_dict(torch.load(spatial_weights, map_location=device))
    model.eval()

    transform = transforms.Compose([
        transforms.ToTensor(),
        transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
    ])

    vf_dir = ROOT / "data" / "video_frames"
    feat_dir = ROOT / "data" / "features"

    total = 0
    t0 = time.time()
    for split in ["train", "val", "test"]:
        for label_name in ["real", "fake"]:
            s_dir = vf_dir / split / label_name
            if not s_dir.exists():
                continue
            o_dir = feat_dir / split / label_name
            o_dir.mkdir(parents=True, exist_ok=True)

            video_folders = sorted([d for d in s_dir.iterdir() if d.is_dir()])
            for vf in video_folders:
                frames = sorted(list(vf.glob("*.jpg")) + list(vf.glob("*.png")))
                if not frames:
                    continue
                imgs = [transform(Image.open(fp).convert("RGB")) for fp in frames]
                batch = torch.stack(imgs).to(device)
                with torch.no_grad():
                    feats = model.features(batch)
                    pooled = model.avgpool(feats).flatten(1).cpu() # (T, 1792)
                torch.save(pooled, o_dir / f"{vf.name}.pt")
                total += 1

    print(f"Extracted {total} video feature sequences in {time.time()-t0:.1f}s.")

# ---------------------------------------------------------------------------
# 4. Train Temporal BiGRU (Model 3)
# ---------------------------------------------------------------------------
def train_temporal_model(epochs=25, batch_size=16):
    print("\n" + "=" * 65)
    print(" [STAGE 4/4] Training Model 3: Temporal BiGRU (Sequence Motion)")
    print("=" * 65, flush=True)

    loaders = create_sequence_loaders(ROOT / "data" / "features", batch_size=batch_size, num_workers=0)
    train_loader = loaders["train"]
    val_loader = loaders["val"]

    print(f"Train sequences: {len(train_loader.dataset)} | Val sequences: {len(val_loader.dataset)}")

    model = TemporalBiGRU(input_size=1792, hidden_size=128, num_layers=1, dropout=0.35).to(device)
    optimizer = AdamW(model.parameters(), lr=0.0005, weight_decay=3e-3)
    scheduler = CosineAnnealingLR(optimizer, T_max=epochs, eta_min=1e-6)
    criterion = nn.BCELoss()

    best_val_loss = float("inf")
    best_weights = None

    for epoch in range(1, epochs + 1):
        t0 = time.time()
        model.train()
        train_loss, train_corr, train_tot = 0.0, 0, 0
        for x, y, lengths in train_loader:
            x, y, lengths = x.to(device), y.float().to(device), lengths.to(device)
            optimizer.zero_grad()
            preds = model(x, lengths)
            loss = criterion(preds, y)
            loss.backward()
            optimizer.step()

            train_loss += loss.item() * len(y)
            train_corr += ((preds > 0.5) == y).sum().item()
            train_tot += len(y)
        scheduler.step()

        model.eval()
        val_loss, val_corr, val_tot = 0.0, 0, 0
        with torch.no_grad():
            for x, y, lengths in val_loader:
                x, y, lengths = x.to(device), y.float().to(device), lengths.to(device)
                preds = model(x, lengths)
                loss = criterion(preds, y)
                val_loss += loss.item() * len(y)
                val_corr += ((preds > 0.5) == y).sum().item()
                val_tot += len(y)

        elapsed = time.time() - t0
        tr_l, tr_a = train_loss / max(train_tot, 1), train_corr / max(train_tot, 1)
        v_l, v_a = val_loss / max(val_tot, 1), val_corr / max(val_tot, 1)
        if epoch % 5 == 0 or epoch == epochs or v_l < best_val_loss:
            print(f"Epoch {epoch:2d}/{epochs} | Train loss: {tr_l:.4f} acc: {tr_a:.4f} | Val loss: {v_l:.4f} acc: {v_a:.4f} | {elapsed:.1f}s", flush=True)

        if v_l < best_val_loss:
            best_val_loss = v_l
            best_weights = model.state_dict().copy()

    # Save to weights/temporal.pt
    out_path = WEIGHTS_DIR / "temporal.pt"
    torch.save(best_weights or model.state_dict(), out_path)
    print(f"-> Temporal BiGRU weights saved to {out_path} (Val loss: {best_val_loss:.4f})")

if __name__ == "__main__":
    t_start = time.time()
    train_frequency_model(epochs=5, batch_size=32)
    train_spatial_model(epochs=3, batch_size=16)
    extract_all_video_features()
    train_temporal_model(epochs=20, batch_size=16)
    print(f"\n{'='*65}\n ALL 3 MODELS RETRAINED ON GPU IN {time.time()-t_start:.1f}s ({(time.time()-t_start)/60:.1f} min)!\n{'='*65}\n")
