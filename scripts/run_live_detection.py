import requests
import json
import time
from pathlib import Path

BASE = "http://localhost:8000"

# 1. Login or register with fresh session
ts = int(time.time())
email = f"user_{ts}@example.com"
password = "Password123!"
reg_res = requests.post(f"{BASE}/auth/register", json={"email": email, "display_name": "Live Tester", "password": password})
login_res = requests.post(f"{BASE}/auth/login", json={"email": email, "password": password})
if login_res.status_code != 200:
    print("Login failed:", login_res.status_code, login_res.text)
    exit(1)

token = login_res.json()["access_token"]
headers = {"Authorization": f"Bearer {token}"}
print(f"[1] Logged in as {email}. Token acquired.")

# 2. Upload user real video
video_path = Path(r"C:\Users\Abhinav Kumar\.gemini\antigravity\brain\3f1d3ec6-f7a8-4886-a170-dcbe09fda3ce\.user_uploaded\media_1794587483682_3c56a9d8.mp4")
print(f"[2] Uploading '{video_path.name}' ({video_path.stat().st_size} bytes) to /videos/ ...")

with open(video_path, "rb") as f:
    files = {"file": ("user_real_video.mp4", f, "video/mp4")}
    upload_res = requests.post(f"{BASE}/videos/", headers=headers, files=files)

if upload_res.status_code not in (200, 201, 202):
    print("Upload failed:", upload_res.status_code, upload_res.text)
    exit(1)

job_data = upload_res.json()
job_id = job_data["job_id"]
print(f"[3] Job created successfully! Job ID: {job_id}")

# 3. Poll job until completion
print("[4] Processing video through 3-model ensemble and cryptographic pipeline...")
for i in range(40):
    time.sleep(1)
    jres = requests.get(f"{BASE}/jobs/{job_id}", headers=headers).json()
    status = jres["status"]
    progress = jres.get("progress", 0)
    print(f"    - Elapsed {i+1}s: Status = {status} (Progress = {progress}%)")
    if status in ["completed", "failed"]:
        break

summary = jres.get("result_summary") or {}
fake_prob = summary.get("fake_probability")
verdict = summary.get("verdict")
att_id = summary.get("attestation_id")

print("\n" + "=" * 65)
print(" PIPELINE EXECUTION COMPLETED")
print("=" * 65)
print(f"Status           : {jres.get('status')}")
print(f"Fake Probability : {fake_prob}")
print(f"Verdict          : {verdict}")
print(f"Attestation ID   : {att_id}")
print(f"Spatial Score    : {summary.get('spatial_score')}")
print(f"Frequency Score  : {summary.get('frequency_score')}")
print(f"Temporal Score   : {summary.get('temporal_score')}")

# 4. Fetch attestation manifest
if att_id:
    att_res = requests.get(f"{BASE}/attestations/{att_id}", headers=headers)
    if att_res.status_code == 200:
        manifest = att_res.json()
        print("\n" + "=" * 65)
        print(" CRYPTOGRAPHIC ATTESTATION MANIFEST")
        print("=" * 65)
        sig_val = manifest.get('signature')
        if isinstance(sig_val, dict):
            sig_val = sig_val.get('value', '')
        print(f"Signature (Ed25519) : {str(sig_val)[:32]}...")
        ts_val = manifest.get('timestamp_token') or manifest.get('timestamp')
        print(f"RFC 3161 Timestamp  : {str(ts_val)[:32]}...")
        print(f"Merkle Leaf Index   : {manifest.get('merkle_leaf_index')}")
        print(f"SHA-256 Video Hash  : {manifest.get('video_hash')}")
print("=" * 65)
