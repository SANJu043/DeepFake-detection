import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.app.services.detector import DeepfakeDetector
from backend.app.services.policy import PolicyEngine
from backend.app.config import get_settings

det = DeepfakeDetector()
p = Path(r"C:\Users\Abhinav Kumar\.gemini\antigravity\brain\3f1d3ec6-f7a8-4886-a170-dcbe09fda3ce\.user_uploaded\media_1794663487348_b0eb3226.mp4")
res = det.detect_video_file(p)

settings = get_settings()
policy = PolicyEngine(threshold_clean=settings.threshold_clean, threshold_manipulated=settings.threshold_manipulated)
pol = policy.evaluate(
    fake_probability=res["fake_probability"],
    face_detected=res["has_face"],
    duration_s=res["duration_s"],
    frames_analyzed=res["frames_analyzed"],
)

print("\n================ USER VIDEO RESULT ================")
print("Verdict:", pol.verdict)
print(f"AI Score: {res['fake_probability']*100:.1f}%")
print(f"Spatial Score: {res['model_scores']['spatial']*100:.1f}%")
print(f"Frequency Score: {res['model_scores']['frequency']*100:.1f}%")
print(f"Temporal Score: {res['model_scores']['temporal']*100:.1f}%")
print("Faces Detected:", res["face_count"])
print("Frames Analysed:", res["frames_analyzed"])
print(f"Duration: {res['duration_s']}s")
print("====================================================")
