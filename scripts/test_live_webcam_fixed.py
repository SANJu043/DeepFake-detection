import requests
import time
import uuid

unique_id = uuid.uuid4().hex[:8]
email = f"user_{unique_id}@example.com"
password = "Password123!"

# Register & Login
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

# Upload WIN_20261111_18_11_24_Pro.mp4 (0f45e273-790d-49f5-b57a-72907100bf90.mp4)
with open("data/uploads/0f45e273-790d-49f5-b57a-72907100bf90.mp4", "rb") as f:
    files = {"file": ("WIN_20261111_18_11_24_Pro.mp4", f, "video/mp4")}
    up_res = requests.post("http://localhost:8000/videos/", headers=headers, files=files)

job_id = up_res.json()["job_id"]
print("Upload complete! Detection job queued, job_id:", job_id)

for _ in range(25):
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
        break

