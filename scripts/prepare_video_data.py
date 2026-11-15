"""
Download real deepfake video clips from Celeb-DF v2 (angads24/deepfake-video on HuggingFace),
extract consecutive face-crop frames, and compute EfficientNet-B4 feature sequences
for TemporalBiGRU training.
"""

import os
import shutil
from pathlib import Path
import cv2
import numpy as np
import torch
import torchvision.transforms as transforms
from PIL import Image
from huggingface_hub import hf_hub_download, list_repo_tree
from ml.models.efficientnet_b4 import EfficientNetB4Detector

ROOT = Path(__file__).resolve().parent.parent
FRAMES_DIR = ROOT / "data" / "video_frames"
FEATURES_DIR = ROOT / "data" / "features"
REPO_ID = "angads24/deepfake-video"

# Face cascade detector
cascade = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")

def extract_face_crop(frame, target_size=(380, 380)):
    """Detect and crop face from frame with margin, fallback to center crop."""
    h, w, _ = frame.shape
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    faces = cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5, minSize=(60, 60))
    
    if len(faces) > 0:
        # Choose the largest detected face
        faces = sorted(faces, key=lambda f: f[2] * f[3], reverse=True)
        x, y, fw, fh = faces[0]
        # Add 20% margin
        margin_x = int(fw * 0.2)
        margin_y = int(fh * 0.2)
        x1 = max(0, x - margin_x)
        y1 = max(0, y - margin_y)
        x2 = min(w, x + fw + margin_x)
        y2 = min(h, y + fh + margin_y)
        crop = frame[y1:y2, x1:x2]
    else:
        # Fallback: center square crop
        side = min(h, w)
        y1 = (h - side) // 2
        x1 = (w - side) // 2
        crop = frame[y1:y1+side, x1:x1+side]

    return cv2.resize(crop, target_size)

def download_and_extract_frames(num_train=20, num_val=5, num_test=5, max_frames=20):
    """Download videos and extract consecutive face-cropped frames."""
    total_needed = num_train + num_val + num_test
    print(f"Downloading {total_needed} real + {total_needed} fake videos from {REPO_ID}...")

    # Fetch list of videos
    fake_items = [f.rfilename for f in list_repo_tree(REPO_ID, repo_type="dataset", path_in_repo="dataset/fake") if f.rfilename.endswith(".mp4")]
    real_items = [f.rfilename for f in list_repo_tree(REPO_ID, repo_type="dataset", path_in_repo="dataset/real") if f.rfilename.endswith(".mp4")]

    fake_selected = fake_items[:total_needed]
    real_selected = real_items[:total_needed]

    splits = (
        [("train", fake_selected[:num_train], real_selected[:num_train])] +
        [("val", fake_selected[num_train:num_train+num_val], real_selected[num_train:num_train+num_val])] +
        [("test", fake_selected[num_train+num_val:], real_selected[num_train+num_val:])]
    )

    for split_name, fakes, reals in splits:
        print(f"\n--- Processing split: {split_name} ({len(reals)} real, {len(fakes)} fake) ---")
        for label_name, vid_list in [("fake", fakes), ("real", reals)]:
            for idx, rel_path in enumerate(vid_list):
                vid_id = f"video_{idx:03d}"
                out_dir = FRAMES_DIR / split_name / label_name / vid_id
                out_dir.mkdir(parents=True, exist_ok=True)

                print(f"  Downloading [{split_name}/{label_name}] {Path(rel_path).name}...", end=" ", flush=True)
                local_path = hf_hub_download(repo_id=REPO_ID, filename=rel_path, repo_type="dataset")

                # Extract frames
                cap = cv2.VideoCapture(local_path)
                frame_count = 0
                saved = 0
                # Stride to sample frames evenly across the clip
                total_video_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT)) or 100
                stride = max(1, total_video_frames // (max_frames * 2))

                while cap.isOpened() and saved < max_frames:
                    ret, frame = cap.read()
                    if not ret:
                        break
                    if frame_count % stride == 0:
                        face_crop = extract_face_crop(frame)
                        cv2.imwrite(str(out_dir / f"frame_{saved:03d}.jpg"), face_crop)
                        saved += 1
                    frame_count += 1
                cap.release()
                print(f"saved {saved} frames.")

def extract_features_with_model(weights_path="checkpoints/efficientnet_b4_best.pt", device="cpu"):
    """Extract feature sequences using the trained EfficientNet-B4 model."""
    print(f"\nExtracting feature sequences using {weights_path} on {device}...")
    model = EfficientNetB4Detector(pretrained=False).to(device)
    ckpt = torch.load(weights_path, map_location=device, weights_only=False)
    if "model_state_dict" in ckpt:
        model.load_state_dict(ckpt["model_state_dict"])
    else:
        model.load_state_dict(ckpt)
    model.eval()

    transform = transforms.Compose([
        transforms.ToTensor(),
        transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
    ])

    for split in ["train", "val", "test"]:
        for label_name in ["real", "fake"]:
            split_dir = FRAMES_DIR / split / label_name
            if not split_dir.exists():
                continue

            out_dir = FEATURES_DIR / split / label_name
            out_dir.mkdir(parents=True, exist_ok=True)

            video_dirs = sorted([d for d in split_dir.iterdir() if d.is_dir()])
            print(f"Extracting {split}/{label_name}: {len(video_dirs)} videos...")

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

                torch.save(pooled.cpu(), out_dir / f"{vdir.name}.pt")

    print("All feature extraction complete!")

if __name__ == "__main__":
    download_and_extract_frames()
    extract_features_with_model()

