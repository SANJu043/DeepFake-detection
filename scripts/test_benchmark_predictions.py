import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import torch
from backend.app.services.detector import DeepfakeDetector

device = "cuda" if torch.cuda.is_available() else "cpu"
print(f"Running benchmark on device: {device}")
detector = DeepfakeDetector(weights_dir="./weights", device=device)

test_videos = [
    ("F1 Roast YouTube Fa6cdce7LYc", ROOT / "data" / "uploads" / "ce96ba90-a45b-4102-95d9-9d877e16f0a1.mp4"),
    ("Windows Camera Video (Short 9f)", ROOT / "data" / "uploads" / "d92829d9-47e7-40d7-8fa8-e6e786fbedad.mp4"),
    ("User Real Phone Video (WhatsApp 19.57.41)", r"C:\Users\Abhinav Kumar\.gemini\antigravity\brain\3f1d3ec6-f7a8-4886-a170-dcbe09fda3ce\.user_uploaded\media_1794587483682_3c56a9d8.mp4"),
    ("Maggi Cooking Video (Non-face)", r"C:\Users\Abhinav Kumar\.gemini\antigravity\brain\3f1d3ec6-f7a8-4886-a170-dcbe09fda3ce\.user_uploaded\media_1794476737736_94f6a00b.mp4"),
    ("Sample Real Celeb Video", ROOT / "sample_videos" / "sample_real_video.mp4"),
    ("Sample Deepfake Video", ROOT / "sample_videos" / "sample_deepfake_video.mp4"),
    ("Alia Bhatt Deepfake Reel", ROOT / "data" / "uploads" / "9892d5f3-eb80-4df0-8fc0-8004a4acb691.mp4"),
]

print("=" * 70)
for name, vpath in test_videos:
    p = Path(vpath)
    if not p.exists():
        print(f"[{name}] File NOT found at {p}")
        continue
    res = detector.detect_video_file(p)
    fp = res["fake_probability"]
    hf = res["has_face"]
    if not hf:
        verdict = "INCONCLUSIVE (NO FACE DETECTED)"
    elif fp < 0.38:
        verdict = "NO_MANIPULATION_DETECTED (CLEAN / REAL)"
    elif fp >= 0.50:
        verdict = "LIKELY_MANIPULATED (DEEPFAKE)"
    else:
        verdict = "SUSPICIOUS"

    print(f"[{name}]")
    print(f"  VERDICT    : {verdict}")
    print(f"  Probability: {fp:.4f} (has_face={hf}, face_count={res.get('face_count')}, frames_analyzed={res.get('frames_analyzed')})")
    print(f"  Breakdown  : Spatial={res['model_scores']['spatial']:.4f}, Frequency={res['model_scores']['frequency']:.4f}, Temporal={res['model_scores']['temporal']:.4f}")
    print("-" * 70)
print("=" * 70)
