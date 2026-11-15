"""
Extract feature sequences from real frames for TemporalBiGRU training.
Uses EfficientNet-B4 backbone (features + avgpool) to turn each folder of frames (videoXXXX)
into a .pt tensor of shape (T, 1792).
"""

from pathlib import Path
import torch
import torchvision.transforms as transforms
from PIL import Image
from tqdm import tqdm
from ml.models.efficientnet_b4 import EfficientNetB4Detector

ROOT = Path(__file__).resolve().parent.parent
FRAMES_DIR = ROOT / "data" / "frames"
FEATURES_DIR = ROOT / "data" / "features"

transform = transforms.Compose([
    transforms.Resize((380, 380)),
    transforms.ToTensor(),
    transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
])

def extract_features(device="cpu"):
    print(f"Extracting features using EfficientNet-B4 on {device}...")
    model = EfficientNetB4Detector(pretrained=True).to(device)
    model.eval()

    # Features extractor is model.features + model.avgpool
    for split in ["train", "val", "test"]:
        for label_name in ["real", "fake"]:
            split_dir = FRAMES_DIR / split / label_name
            if not split_dir.exists():
                continue
            
            out_label_dir = FEATURES_DIR / split / label_name
            out_label_dir.mkdir(parents=True, exist_ok=True)

            video_dirs = sorted([d for d in split_dir.iterdir() if d.is_dir()])
            print(f"Processing {split}/{label_name}: {len(video_dirs)} videos...")

            for vdir in video_dirs:
                frame_paths = sorted(list(vdir.glob("*.jpg")) + list(vdir.glob("*.png")))
                if not frame_paths:
                    continue

                imgs = []
                for fp in frame_paths:
                    img = Image.open(fp).convert("RGB")
                    imgs.append(transform(img))

                batch = torch.stack(imgs).to(device) # (T, 3, 380, 380)

                with torch.no_grad():
                    feats = model.features(batch)
                    pooled = model.avgpool(feats).flatten(1) # (T, 1792)

                out_path = out_label_dir / f"{vdir.name}.pt"
                torch.save(pooled.cpu(), out_path)

    print("Feature extraction complete!")

if __name__ == "__main__":
    extract_features()

