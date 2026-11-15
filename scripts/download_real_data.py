"""
Download real deepfake vs real face images from HuggingFace.
Dataset: Hemg/deepfake-and-real-images (~190k images, free, no login)
  - label 0 = real face
  - label 1 = deepfake / AI-generated

Saves into project structure:
  data/frames/{train,val,test}/{real,fake}/videoNNNN/frame_*.jpg

Usage:
  python scripts/download_real_data.py --max-per-class 3000
"""

from __future__ import annotations

import argparse
import os
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data" / "frames"

# Suppress the symlink warning on Windows
os.environ["HF_HUB_DISABLE_SYMLINKS_WARNING"] = "1"


def download_and_prepare(
    max_per_class: int = 3000,
    train_ratio: float = 0.80,
    val_ratio: float = 0.10,
    frames_per_folder: int = 10,
    target_size: tuple[int, int] = (380, 380),
    dataset_name: str = "Hemg/deepfake-and-real-images",
) -> None:
    try:
        from datasets import load_dataset
        from PIL import Image
    except ImportError:
        print("[ERROR] Run: pip install datasets pillow")
        sys.exit(1)

    print("=" * 60)
    print(f"Dataset : {dataset_name}")
    print(f"Per class: {max_per_class}  (total ~{max_per_class * 2} images)")
    print(f"Output  : {DATA_DIR}")
    print("=" * 60)

    real_images: list = []
    fake_images: list = []

    for attempt in range(3):
        try:
            print(f"\nLoading dataset (attempt {attempt + 1}/3)...")
            ds = load_dataset(dataset_name, split="train", streaming=True)
            break
        except Exception as e:
            print(f"  Warning: {e}")
            if attempt == 2:
                print("[ERROR] Could not connect to HuggingFace after 3 attempts.")
                sys.exit(1)
            import time; time.sleep(5)

    print("Streaming images...")
    errors = 0

    for i, sample in enumerate(ds):
        if len(real_images) >= max_per_class and len(fake_images) >= max_per_class:
            break

        try:
            label = sample.get("label", sample.get("labels", None))
            img = sample.get("image", sample.get("img", None))

            if img is None or label is None:
                continue

            # Ensure PIL Image
            if not hasattr(img, "resize"):
                from PIL import Image as PILImage
                img = PILImage.fromarray(img)

            img = img.convert("RGB").resize(target_size)

            if label == 0 and len(real_images) < max_per_class:
                real_images.append(img)
            elif label == 1 and len(fake_images) < max_per_class:
                fake_images.append(img)

        except Exception as e:
            errors += 1
            if errors < 10:
                print(f"  Sample error: {e}")
            continue

        if (i + 1) % 500 == 0:
            print(f"  Processed {i+1} | Real: {len(real_images)} | Fake: {len(fake_images)}")

    print(f"\nCollected: {len(real_images)} real, {len(fake_images)} fake ({errors} errors skipped)")

    if len(real_images) == 0 or len(fake_images) == 0:
        print("[ERROR] No images collected. Check network connection.")
        sys.exit(1)

    # Shuffle + split
    def split(lst: list) -> tuple[list, list, list]:
        random.shuffle(lst)
        t = int(len(lst) * train_ratio)
        v = int(len(lst) * val_ratio)
        return lst[:t], lst[t:t+v], lst[t+v:]

    real_tr, real_val, real_te = split(real_images)
    fake_tr, fake_val, fake_te = split(fake_images)

    def save_set(images: list, split_name: str, label_name: str) -> int:
        saved = 0
        video_idx = 0
        frame_idx = frames_per_folder  # trigger new folder on first iter

        for img in images:
            if frame_idx >= frames_per_folder:
                video_idx += 1
                frame_idx = 0
                vdir = DATA_DIR / split_name / label_name / f"video{video_idx:04d}"
                vdir.mkdir(parents=True, exist_ok=True)

            img.save(vdir / f"frame_{frame_idx:03d}.jpg", quality=90)
            frame_idx += 1
            saved += 1

        return saved

    print("\nSaving frames to disk...")
    for split_name, real_set, fake_set in [
        ("train", real_tr,  fake_tr),
        ("val",   real_val, fake_val),
        ("test",  real_te,  fake_te),
    ]:
        r = save_set(real_set, split_name, "real")
        f = save_set(fake_set, split_name, "fake")
        print(f"  [{split_name:5s}]  real={r:5d}  fake={f:5d}")

    total = len(real_images) + len(fake_images)
    print(f"\nDone! {total} images saved to {DATA_DIR}")


def main() -> None:
    p = argparse.ArgumentParser(description="Download real deepfake dataset from HuggingFace")
    p.add_argument("--max-per-class", type=int, default=3000,
                   help="Max images per class (real/fake). Default 3000 = 6000 total.")
    p.add_argument("--frames-per-folder", type=int, default=10,
                   help="Images grouped per 'video' folder (mimics frame structure).")
    args = p.parse_args()

    download_and_prepare(
        max_per_class=args.max_per_class,
        frames_per_folder=args.frames_per_folder,
    )


if __name__ == "__main__":
    main()
