"""
Scale up Celeb-DF v2 dataset to 210 videos (105 real, 105 fake),
extract face frame sequences, compute EfficientNet-B4 embeddings,
and retrain Model 3 (TemporalBiGRU) with robust metrics.
"""

from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
import os
import shutil
import subprocess
import sys
import time

import cv2
from huggingface_hub import hf_hub_download, list_repo_tree
import torch
import torchvision.transforms as transforms
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
PYTHON = ROOT / "venv" / "Scripts" / "python.exe"
FRAMES_DIR = ROOT / "data" / "video_frames"
FEATURES_DIR = ROOT / "data" / "features"
REPO_ID = "angads24/deepfake-video"

cascade = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")

def extract_face_crop(frame, target_size=(380, 380)):
    h, w, _ = frame.shape
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    faces = cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=4, minSize=(60, 60))
    if len(faces) > 0:
        faces = sorted(faces, key=lambda f: f[2] * f[3], reverse=True)
        x, y, fw, fh = faces[0]
        margin_x = int(fw * 0.2)
        margin_y = int(fh * 0.2)
        x1 = max(0, x - margin_x)
        y1 = max(0, y - margin_y)
        x2 = min(w, x + fw + margin_x)
        y2 = min(h, y + fh + margin_y)
        crop = frame[y1:y2, x1:x2]
    else:
        side = min(h, w)
        y1 = (h - side) // 2
        x1 = (w - side) // 2
        crop = frame[y1:y1 + side, x1:x1 + side]
    return cv2.resize(crop, target_size)

def process_single_video(item_rfilename, out_dir, max_frames=20):
    video_stem = Path(item_rfilename).stem
    dest_dir = out_dir / video_stem
    if dest_dir.exists() and len(list(dest_dir.glob("*.jpg"))) >= max_frames:
        return video_stem, True, "already exists"

    try:
        fpath = hf_hub_download(REPO_ID, filename=item_rfilename, repo_type="dataset")
        cap = cv2.VideoCapture(fpath)
        if not cap.isOpened():
            return video_stem, False, "cannot open video"

        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        if total_frames < max_frames:
            step = 1
        else:
            step = max(1, total_frames // max_frames)

        dest_dir.mkdir(parents=True, exist_ok=True)
        saved = 0
        frame_idx = 0
        while cap.isOpened() and saved < max_frames:
            ret, frame = cap.read()
            if not ret:
                break
            if frame_idx % step == 0:
                crop = extract_face_crop(frame)
                out_path = dest_dir / f"frame_{saved:03d}.jpg"
                cv2.imwrite(str(out_path), crop)
                saved += 1
            frame_idx += 1
        cap.release()
        return video_stem, True, f"extracted {saved} frames"
    except Exception as e:
        return video_stem, False, str(e)

def download_and_extract_all():
    print("=" * 60)
    print(" STEP 1: DOWNLOADING CELEB-DF V2 VIDEOS (210 VIDEOS)")
    print("=" * 60)
    fake_items = sorted([f.rfilename for f in list_repo_tree(REPO_ID, repo_type="dataset", path_in_repo="dataset/fake") if f.rfilename.endswith(".mp4")])
    real_items = sorted([f.rfilename for f in list_repo_tree(REPO_ID, repo_type="dataset", path_in_repo="dataset/real") if f.rfilename.endswith(".mp4")])

    print(f"Total available in repo: {len(real_items)} real, {len(fake_items)} fake")
    
    # Target: 75 train, 15 val, 15 test each (total 105 real, 105 fake = 210 videos)
    splits = [
        ("train", "real", real_items[0:75]),
        ("train", "fake", fake_items[0:75]),
        ("val", "real", real_items[75:90]),
        ("val", "fake", fake_items[75:90]),
        ("test", "real", real_items[90:105]),
        ("test", "fake", fake_items[90:105]),
    ]

    tasks = []
    with ThreadPoolExecutor(max_workers=6) as executor:
        for split, label, items in splits:
            out_dir = FRAMES_DIR / split / label
            out_dir.mkdir(parents=True, exist_ok=True)
            for item in items:
                tasks.append(executor.submit(process_single_video, item, out_dir))

        done = 0
        for fut in as_completed(tasks):
            done += 1
            name, ok, msg = fut.result()
            if done % 15 == 0 or not ok:
                print(f"[{done}/{len(tasks)}] {name}: {'OK' if ok else 'FAIL'} ({msg})")

    print("\nDataset download and frame extraction complete!")

def extract_features():
    print("\n" + "=" * 60)
    print(" STEP 2: EXTRACTING EFFICIENTNET-B4 EMBEDDINGS (T, 1792)")
    print("=" * 60)
    from ml.models.efficientnet_b4 import EfficientNetB4Detector
    weights_path = ROOT / "checkpoints" / "efficientnet_b4_best.pt"
    device = "cpu"

    model = EfficientNetB4Detector(pretrained=False).to(device)
    ckpt = torch.load(weights_path, map_location=device, weights_only=False)
    state = ckpt["model_state_dict"] if "model_state_dict" in ckpt else ckpt
    model.load_state_dict(state)
    model.eval()

    transform = transforms.Compose([
        transforms.ToTensor(),
        transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
    ])

    total = 0
    for split in ["train", "val", "test"]:
        for label_name in ["real", "fake"]:
            split_dir = FRAMES_DIR / split / label_name
            out_dir = FEATURES_DIR / split / label_name
            out_dir.mkdir(parents=True, exist_ok=True)
            video_dirs = sorted([d for d in split_dir.iterdir() if d.is_dir()])
            print(f"Extracting features: {split}/{label_name} ({len(video_dirs)} videos)...")
            for vdir in video_dirs:
                out_path = out_dir / f"{vdir.name}.pt"
                if out_path.exists():
                    total += 1
                    continue
                frame_paths = sorted(list(vdir.glob("*.jpg")))
                if not frame_paths:
                    continue
                imgs = [transform(Image.open(fp).convert("RGB")) for fp in frame_paths]
                batch = torch.stack(imgs).to(device)
                with torch.no_grad():
                    feats = model.features(batch)
                    pooled = model.avgpool(feats).flatten(1)
                torch.save(pooled.cpu(), out_path)
                total += 1

    print(f"Feature extraction done! {total} video sequences saved to {FEATURES_DIR}")

def train_and_evaluate():
    print("\n" + "=" * 60)
    print(" STEP 3: RETRAINING MODEL 3 (TEMPORAL BIGRU)")
    print("=" * 60)

    # Update config
    cfg_path = ROOT / "ml" / "configs" / "_train_real_temporal_bigru.yaml"
    cfg_text = """model:
  name: temporal_bigru
  input_size: 1792
  hidden_size: 256
  num_layers: 2
  dropout: 0.3

data:
  root: ./data/features
  num_workers: 0
  max_seq_len: 30

training:
  batch_size: 16
  lr: 0.001
  lr_min: 0.000001
  weight_decay: 0.0001
  epochs: 25
  patience: 8
  amp: false
  output_dir: ./checkpoints
"""
    cfg_path.write_text(cfg_text, encoding="utf-8")

    env = os.environ.copy()
    env["PYTHONPATH"] = f"{ROOT};{ROOT / 'backend'}"

    # Run training
    cmd = [str(PYTHON), "-m", "ml.train", "--config", str(cfg_path), "--device", "cpu"]
    res = subprocess.run(cmd, cwd=ROOT, env=env)
    if res.returncode != 0:
        print("Training failed!")
        sys.exit(res.returncode)

    # Evaluate
    print("\n" + "=" * 60)
    print(" STEP 4: EVALUATING RETRAINED TEMPORAL BIGRU ON TEST SET")
    print("=" * 60)
    eval_cmd = [
        str(PYTHON), "-m", "ml.evaluate",
        "--config", str(cfg_path),
        "--weights", "checkpoints/temporal_bigru_best.pt",
        "--device", "cpu",
        "--output", "checkpoints/eval_real_temporal_bigru.json"
    ]
    res = subprocess.run(eval_cmd, cwd=ROOT, env=env)
    if res.returncode != 0:
        print("Evaluation failed!")
        sys.exit(res.returncode)

    # Export to TorchScript
    print("\n" + "=" * 60)
    print(" STEP 5: EXPORTING TORCHSCRIPT WEIGHTS")
    print("=" * 60)
    export_cmd = [
        str(PYTHON), "-m", "ml.export",
        "--model", "temporal",
        "--weights", "checkpoints/temporal_bigru_best.pt",
        "--format", "torchscript",
        "--output", "checkpoints/temporal_scripted.pt",
        "--device", "cpu"
    ]
    subprocess.run(export_cmd, cwd=ROOT, env=env, check=True)

    # Copy to weights/
    shutil.copy("checkpoints/temporal_bigru_best.pt", "weights/temporal.pt")
    print("Copied updated weights to weights/temporal.pt")

if __name__ == "__main__":
    t_start = time.time()
    download_and_extract_all()
    extract_features()
    train_and_evaluate()
    print(f"\nALL DONE IN {time.time() - t_start:.1f}s!")

