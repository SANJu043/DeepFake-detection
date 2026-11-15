"""
Download Celeb-DF v2 videos and extract consecutive face-crop frames.
Runs concurrently while Model 2 trains so no time is wasted.
"""

from pathlib import Path
import cv2
from huggingface_hub import hf_hub_download, list_repo_tree

ROOT = Path(__file__).resolve().parent.parent
FRAMES_DIR = ROOT / "data" / "video_frames"
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
        crop = frame[y1:y1+side, x1:x1+side]

    return cv2.resize(crop, target_size)

def main():
    num_train = 25
    num_val = 5
    num_test = 5
    total_needed = num_train + num_val + num_test
    max_frames = 20

    print(f"Listing videos from {REPO_ID}...")
    fake_items = [f.rfilename for f in list_repo_tree(REPO_ID, repo_type="dataset", path_in_repo="dataset/fake") if f.rfilename.endswith(".mp4")]
    real_items = [f.rfilename for f in list_repo_tree(REPO_ID, repo_type="dataset", path_in_repo="dataset/real") if f.rfilename.endswith(".mp4")]

    print(f"Found {len(fake_items)} fake and {len(real_items)} real videos.")
    fake_selected = fake_items[:total_needed]
    real_selected = real_items[:total_needed]

    splits = [
        ("train", fake_selected[:num_train], real_selected[:num_train]),
        ("val", fake_selected[num_train:num_train+num_val], real_selected[num_train:num_train+num_val]),
        ("test", fake_selected[num_train+num_val:], real_selected[num_train+num_val:]),
    ]

    total_downloaded = 0
    for split_name, fakes, reals in splits:
        print(f"\n==========================================")
        print(f"Processing split: {split_name} ({len(reals)} real, {len(fakes)} fake)")
        print(f"==========================================")
        for label_name, vid_list in [("real", reals), ("fake", fakes)]:
            for idx, rel_path in enumerate(vid_list):
                vid_id = f"video_{idx:03d}"
                out_dir = FRAMES_DIR / split_name / label_name / vid_id
                out_dir.mkdir(parents=True, exist_ok=True)

                # Check if already extracted
                existing_frames = list(out_dir.glob("*.jpg"))
                if len(existing_frames) >= max_frames:
                    print(f"  [{split_name}/{label_name}] {vid_id}: already has {len(existing_frames)} frames.")
                    continue

                local_path = hf_hub_download(repo_id=REPO_ID, filename=rel_path, repo_type="dataset")

                cap = cv2.VideoCapture(local_path)
                frame_count = 0
                saved = 0
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
                total_downloaded += 1
                print(f"  [{split_name}/{label_name}] {vid_id} ({Path(rel_path).name[:30]}...): saved {saved} frames.")

    print(f"\nAll done! Downloaded and processed {total_downloaded} videos.")

if __name__ == "__main__":
    main()

