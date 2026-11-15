"""
Create synthetic face-frame training data for smoke-testing the ML pipeline.

Generates randomly coloured JPEG images and pre-extracted feature tensors (.pt)
under the expected directory structure:

    data/frames/{train,val,test}/{real,fake}/videoN/frame_*.jpg
    data/features/{train,val,test}/{real,fake}/videoN.pt

Usage:
    python scripts/create_synthetic_data.py [--output-dir ./data] [--num-videos 20]
"""

from __future__ import annotations

import argparse
import random
import sys
from pathlib import Path

import numpy as np

# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Generate synthetic training data")
    p.add_argument("--output-dir", type=Path, default=Path("./data"))
    p.add_argument("--num-videos", type=int, default=20,
                   help="Number of videos PER split PER class (real/fake)")
    p.add_argument("--frames-per-video", type=int, default=15,
                   help="Number of frames per video")
    p.add_argument("--frame-size", type=int, default=380,
                   help="Size (px) of each frame (square)")
    p.add_argument("--feature-dim", type=int, default=1792,
                   help="Feature vector dimension for BiGRU (.pt files)")
    return p


# ---------------------------------------------------------------------------
# Generators
# ---------------------------------------------------------------------------

def make_frame(label: int, size: int, frame_idx: int) -> np.ndarray:
    """Generate a synthetic face frame.

    Real frames are dominantly green-toned, fake frames are dominantly
    red-toned, with Gaussian noise added.
    """
    img = np.random.randint(50, 200, (size, size, 3), dtype=np.uint8)
    if label == 0:          # real → green-ish
        img[:, :, 1] = np.clip(img[:, :, 1].astype(int) + 60, 0, 255).astype(np.uint8)
    else:                   # fake → red-ish
        img[:, :, 0] = np.clip(img[:, :, 0].astype(int) + 60, 0, 255).astype(np.uint8)
    return img


def save_frame_data(output_dir: Path, num_videos: int, frames_per_video: int, frame_size: int) -> None:
    """Create data/frames/{split}/{class}/videoN/frame_*.jpg"""
    try:
        import cv2
    except ImportError:
        print("[ERROR] opencv-python-headless not installed. Run: pip install opencv-python-headless")
        sys.exit(1)

    frames_root = output_dir / "frames"
    total = 0
    for split in ["train", "val", "test"]:
        # Fewer videos for val/test
        n = num_videos if split == "train" else max(2, num_videos // 4)
        for label_name, label in [("real", 0), ("fake", 1)]:
            for vid_idx in range(n):
                video_dir = frames_root / split / label_name / f"video{vid_idx:03d}"
                video_dir.mkdir(parents=True, exist_ok=True)
                for frame_idx in range(frames_per_video):
                    frame = make_frame(label, frame_size, frame_idx)
                    frame_path = video_dir / f"frame_{frame_idx:03d}.jpg"
                    cv2.imwrite(str(frame_path), cv2.cvtColor(frame, cv2.COLOR_RGB2BGR))
                    total += 1

    print(f"[Frames] Generated {total} frames under {frames_root}/")


def save_feature_data(output_dir: Path, num_videos: int, feature_dim: int) -> None:
    """Create data/features/{split}/{class}/videoN.pt"""
    try:
        import torch
    except ImportError:
        print("[ERROR] torch not installed yet")
        sys.exit(1)

    features_root = output_dir / "features"
    total = 0
    for split in ["train", "val", "test"]:
        n = num_videos if split == "train" else max(2, num_videos // 4)
        for label_name, label in [("real", 0), ("fake", 1)]:
            label_dir = features_root / split / label_name
            label_dir.mkdir(parents=True, exist_ok=True)
            for vid_idx in range(n):
                # Variable-length sequence: 10 to 30 frames of features
                seq_len = random.randint(10, 30)
                # Real: lower mean; fake: higher mean to give the model signal
                mean = 0.1 if label == 0 else 0.6
                features = torch.randn(seq_len, feature_dim) * 0.3 + mean
                feat_path = label_dir / f"video{vid_idx:03d}.pt"
                torch.save(features, feat_path)
                total += 1

    print(f"[Features] Generated {total} .pt feature files under {features_root}/")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    args = build_parser().parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)

    print(f"Generating synthetic data → {args.output_dir.resolve()}")
    print(f"  Videos per split per class : {args.num_videos}")
    print(f"  Frames per video           : {args.frames_per_video}")
    print(f"  Frame size                 : {args.frame_size}×{args.frame_size}")
    print(f"  Feature dim (BiGRU)        : {args.feature_dim}")
    print()

    save_frame_data(args.output_dir, args.num_videos, args.frames_per_video, args.frame_size)
    save_feature_data(args.output_dir, args.num_videos, args.feature_dim)

    print("\nDone. Data ready for training.")


if __name__ == "__main__":
    main()

