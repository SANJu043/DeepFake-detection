"""
Massive dataset downloader and preprocessor:
1. Hemg/deepfake-and-real-images (~10,000 images total, 5k real + 5k fake).
2. angads24/deepfake-video (100 real videos + 100 fake videos, face-cropped).
3. Real phone/webcam face frames integration.
"""

from pathlib import Path
import os
import sys
import cv2
import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

FRAMES_DIR = ROOT / "data" / "frames"
VIDEO_FRAMES_DIR = ROOT / "data" / "video_frames"

cascade = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")

def extract_face_crop(frame, target_size=(380, 380)):
    h, w = frame.shape[:2]
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    faces = cascade.detectMultiScale(gray, scaleFactor=1.15, minNeighbors=4, minSize=(60, 60))
    if len(faces) > 0:
        faces = sorted(faces, key=lambda f: f[2] * f[3], reverse=True)
        x, y, fw, fh = faces[0]
        mx, my = int(fw * 0.2), int(fh * 0.2)
        crop = frame[max(0, y - my):min(h, y + fh + my), max(0, x - mx):min(w, x + fw + mx)]
    else:
        s = min(h, w)
        crop = frame[(h - s) // 2:(h + s) // 2, (w - s) // 2:(w + s) // 2]
    return cv2.resize(crop, target_size)

def download_hemg_dataset(max_per_class=4000):
    from datasets import load_dataset
    print(f"\n[1/3] Downloading {max_per_class*2} images from Hemg/deepfake-and-real-images...", flush=True)
    ds = load_dataset("Hemg/deepfake-and-real-images", split="train", streaming=True)
    
    real_count = 0
    fake_count = 0
    
    # Save into data/frames/{train,val,test}
    for item in ds:
        label = item.get("label") # 0 = real, 1 = fake
        img = item.get("image")
        if img is None:
            continue
        
        if label == 0 and real_count < max_per_class:
            split = "train" if real_count < int(max_per_class * 0.8) else ("val" if real_count < int(max_per_class * 0.9) else "test")
            folder_idx = real_count // 10
            v_dir = FRAMES_DIR / split / "real" / f"hemg_real_{folder_idx:04d}"
            v_dir.mkdir(parents=True, exist_ok=True)
            img_resized = img.resize((380, 380), Image.Resampling.LANCZOS)
            img_resized.save(v_dir / f"frame_{real_count % 10:02d}.jpg", quality=95)
            real_count += 1
            if real_count % 200 == 0:
                print(f"  Hemg Real: {real_count}/{max_per_class}", flush=True)

        elif label == 1 and fake_count < max_per_class:
            split = "train" if fake_count < int(max_per_class * 0.8) else ("val" if fake_count < int(max_per_class * 0.9) else "test")
            folder_idx = fake_count // 10
            v_dir = FRAMES_DIR / split / "fake" / f"hemg_fake_{folder_idx:04d}"
            v_dir.mkdir(parents=True, exist_ok=True)
            img_resized = img.resize((380, 380), Image.Resampling.LANCZOS)
            img_resized.save(v_dir / f"frame_{fake_count % 10:02d}.jpg", quality=95)
            fake_count += 1
            if fake_count % 200 == 0:
                print(f"  Hemg Fake: {fake_count}/{max_per_class}", flush=True)

        if real_count >= max_per_class and fake_count >= max_per_class:
            break

    print(f"Finished Hemg: {real_count} real, {fake_count} fake saved.", flush=True)

def download_more_videos(num_videos=80):
    from huggingface_hub import hf_hub_download, list_repo_tree
    print(f"\n[2/3] Downloading {num_videos*2} videos from angads24/deepfake-video...")
    items = list(list_repo_tree("angads24/deepfake-video", repo_type="dataset", recursive=True))
    paths = [x.path for x in items if hasattr(x, 'path') and x.path.endswith('.mp4')]
    
    fake_vids = [p for p in paths if "dataset/fake/" in p][:num_videos]
    real_vids = [p for p in paths if "dataset/real/" in p][:num_videos]
    
    tmp_dir = ROOT / "data" / "tmp_vids"
    tmp_dir.mkdir(parents=True, exist_ok=True)
    
    def process_video_list(vid_list, label_name):
        processed = 0
        for v_path in vid_list:
            fname = Path(v_path).name
            try:
                local_path = hf_hub_download(
                    repo_id="angads24/deepfake-video",
                    filename=v_path,
                    repo_type="dataset",
                    local_dir=tmp_dir,
                )
                cap = cv2.VideoCapture(str(local_path))
                total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
                if total < 10:
                    cap.release()
                    continue
                
                step = max(1, total // 15)
                crops = []
                idx = 0
                while cap.isOpened() and len(crops) < 15:
                    ret, frame = cap.read()
                    if not ret:
                        break
                    if idx % step == 0:
                        crop = extract_face_crop(frame)
                        crops.append(crop)
                    idx += 1
                cap.release()
                
                if len(crops) >= 8:
                    split = "train" if processed < int(num_videos * 0.75) else ("val" if processed < int(num_videos * 0.9) else "test")
                    out_dir = VIDEO_FRAMES_DIR / split / label_name / Path(fname).stem
                    out_dir.mkdir(parents=True, exist_ok=True)
                    for i, c in enumerate(crops):
                        cv2.imwrite(str(out_dir / f"frame_{i:02d}.jpg"), c)
                    processed += 1
                    if processed % 10 == 0:
                        print(f"  Processed {label_name} videos: {processed}/{num_videos}")
                
                if Path(local_path).exists():
                    try:
                        os.remove(local_path)
                    except:
                        pass
            except Exception as e:
                print(f"  Skipping {v_path}: {e}")

        print(f"Finished {label_name} videos: {processed} saved.")

    process_video_list(real_vids, "real")
    process_video_list(fake_vids, "fake")

def add_user_real_video_frames():
    print("\n[3/3] Incorporating user real video frames...")
    user_vids = [
        ROOT / "sample_videos" / "sample_real_video.mp4",
        Path(r"C:\Users\Abhinav Kumar\.gemini\antigravity\brain\3f1d3ec6-f7a8-4886-a170-dcbe09fda3ce\.user_uploaded\media_1794587483682_3c56a9d8.mp4"),
    ]
    added = 0
    for v_idx, uv in enumerate(user_vids):
        if not uv.exists():
            continue
        cap = cv2.VideoCapture(str(uv))
        total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        step = max(1, total // 25)
        crops = []
        idx = 0
        while cap.isOpened() and len(crops) < 25:
            ret, frame = cap.read()
            if not ret:
                break
            if idx % step == 0:
                crop = extract_face_crop(frame)
                crops.append(crop)
            idx += 1
        cap.release()
        
        # Save into train, val, and test real
        for split in ["train", "val"]:
            v_dir = FRAMES_DIR / split / "real" / f"user_real_{v_idx:02d}"
            v_dir.mkdir(parents=True, exist_ok=True)
            for i, c in enumerate(crops):
                cv2.imwrite(str(v_dir / f"frame_{i:02d}.jpg"), c)
            
            # Also in video_frames for Temporal model
            vf_dir = VIDEO_FRAMES_DIR / split / "real" / f"user_real_{v_idx:02d}"
            vf_dir.mkdir(parents=True, exist_ok=True)
            for i, c in enumerate(crops):
                cv2.imwrite(str(vf_dir / f"frame_{i:02d}.jpg"), c)
        added += len(crops)
    print(f"Added {added} frames from user real videos across train/val splits.")

if __name__ == "__main__":
    add_user_real_video_frames()
    download_hemg_dataset(max_per_class=3500)
    download_more_videos(num_videos=60)
    print("\nAll dataset preparation complete!")

