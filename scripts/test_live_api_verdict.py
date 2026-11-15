import requests
import time
import uuid

unique_id = uuid.uuid4().hex[:8]
email = f"user_{unique_id}@example.com"
password = "Password123!"

requests.post(
    "http://localhost:8000/auth/register",
    json={"email": email, "display_name": "Tester", "password": password},
)
login_res = requests.post(
    "http://localhost:8000/auth/login",
    json={"email": email, "password": password},
)
token = login_res.json()["access_token"]
headers = {"Authorization": f"Bearer {token}"}

video_path = r"C:\Users\Abhinav Kumar\.gemini\antigravity\brain\3f1d3ec6-f7a8-4886-a170-dcbe09fda3ce\.user_uploaded\media_1794663487348_b0eb3226.mp4"
with open(video_path, "rb") as f:
    files = {"file": ("WIN_20261114_19_07_06_Pro.mp4", f, "video/mp4")}
    up_res = requests.post("http://localhost:8000/videos/", headers=headers, files=files)

job_id = up_res.json()["job_id"]
print("Upload complete! Detection job queued, job_id:", job_id)

for _ in range(30):
    time.sleep(1)
    status_res = requests.get(f"http://localhost:8000/jobs/{job_id}", headers=headers)
    jdata = status_res.json()
    if jdata.get("status") in ("completed", "failed"):
        print("\n=== LIVE JOB STATUS IN UI/BACKEND ===")
        print("Status:", jdata.get("status"))
        res = jdata.get("result_summary", {})
        print("Verdict:", res.get("verdict"))
        print(f"AI Score: {res.get('fake_probability', 0)*100:.1f}%")
        print(f"Spatial Score: {res.get('spatial_score', 0)*100:.1f}%")
        print(f"Frequency Score: {res.get('frequency_score', 0)*100:.1f}%")
        print(f"Temporal Score: {res.get('temporal_score', 0)*100:.1f}%")
        print("Face Count:", res.get("face_count"))
        print("Frames Analysed:", res.get("frames_analyzed"))
        print("Reason:", res.get("reason"))
        break
