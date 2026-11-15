"""
Extract feature sequences from genuine Celeb-DF v2 video frames
using the trained EfficientNet-B4 backbone.
Saves to data/features/{split}/{real,fake}/{video_id}.pt
"""

import sys
from pathlib import Path
import torch
import torchvision.transforms as transforms
from PIL import Image
from ml.models.efficientnet_b4 import EfficientNetB4Detector

ROOT = Path(__file__).resolve().parent.parent
FRAMES_DIR = ROOT / "data" / "video_frames"
FEATURES_DIR = ROOT / "data" / "features"

def main(weights_path="checkpoints/efficientnet_b4_best.pt", device="cpu"):
    print(f"Loading EfficientNet-B4 model from {weights_path}...")
    model = EfficientNetB4Detector(pretrained=False).to(device)
    ckpt = torch.load(weights_path, map_location=device, weights_only=False)
    state = ckpt["model_state_dict"] if "model_state_dict" in ckpt else ckpt
    model.load_state_dict(state)
    model.eval()

    transform = transforms.Compose([
        transforms.ToTensor(),
        transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
    ])

    total_extracted = 0
    for split in ["train", "val", "test"]:
        for label_name in ["real", "fake"]:
            split_dir = FRAMES_DIR / split / label_name
            if not split_dir.exists():
                continue

            out_dir = FEATURES_DIR / split / label_name
            out_dir.mkdir(parents=True, exist_ok=True)

            video_dirs = sorted([d for d in split_dir.iterdir() if d.is_dir()])
            print(f"Processing {split}/{label_name}: {len(video_dirs)} videos...")

            for vdir in video_dirs:
                frame_paths = sorted(list(vdir.glob("*.jpg")))
                if not frame_paths:
                    continue

                imgs = []
                for fp in frame_paths:
                    img = Image.open(fp).convert("RGB")
                    imgs.append(transform(img))

                batch = torch.stack(imgs).to(device)  # (T, 3, 380, 380)

                with torch.no_grad():
                    feats = model.features(batch)
                    pooled = model.avgpool(feats).flatten(1)  # (T, 1792)

                out_path = out_dir / f"{vdir.name}.pt"
                torch.save(pooled.cpu(), out_path)
                total_extracted += 1

    print(f"\nFeature extraction complete! Saved {total_extracted} video sequence embeddings to {FEATURES_DIR}")

if __name__ == "__main__":
    weights = sys.argv[1] if len(sys.argv) > 1 else "checkpoints/efficientnet_b4_best.pt"
    main(weights)

