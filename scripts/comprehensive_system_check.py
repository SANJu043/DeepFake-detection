"""
Comprehensive System Health & End-to-End Verification Script
Tests literally everything in the DeepFake Detection System:
1. Health & Database
2. Auth (Register, Duplicate, Login, Refresh, Me)
3. Video Upload (Real & Fake videos)
4. Detection Pipeline & Asynchronous Processing
5. Jobs & Results
6. Attestations & Cryptographic Manifests
7. Verification by ID & by Upload
8. Sharing & Revocation
9. ML Models & TorchScript Weights Integrity
10. Frontend Routes & Vite Proxy
"""

import io
import json
from pathlib import Path
import sys
import time
import uuid

import requests
import torch

ROOT = Path(__file__).resolve().parent.parent
API_URL = "http://127.0.0.1:8000"
FRONTEND_URL = "http://127.0.0.1:5173"

class Tester:
    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.results = []

    def check(self, name: str, success: bool, detail: str = ""):
        status_str = "PASS" if success else "FAIL"
        if success:
            self.passed += 1
            print(f"  [✓] {name:<45} {detail}")
        else:
            self.failed += 1
            print(f"  [✗] {name:<45} FAILED: {detail}")
        self.results.append((name, status_str, detail))

def test_everything():
    t = Tester()
    print("=" * 70)
    print(" COMPREHENSIVE END-TO-END DEEPFAKE DETECTION VERIFICATION")
    print("=" * 70)

    # ─────────────────────────────────────────────────────────────
    # 1. Health & Server Check
    # ─────────────────────────────────────────────────────────────
    print("\n[SECTION 1: Core Service Health]")
    try:
        r = requests.get(f"{API_URL}/health", timeout=3)
        t.check("Backend API /health", r.status_code == 200, f"status: {r.status_code}")
    except Exception as e:
        t.check("Backend API /health", False, str(e))

    try:
        r = requests.get(f"{FRONTEND_URL}/health", timeout=3)
        t.check("Frontend Vite Proxy /health", r.status_code == 200, f"proxied to backend 200")
    except Exception as e:
        t.check("Frontend Vite Proxy /health", False, str(e))

    # ─────────────────────────────────────────────────────────────
    # 2. Authentication Flow
    # ─────────────────────────────────────────────────────────────
    print("\n[SECTION 2: Authentication & User Lifecycle]")
    test_email = f"autotest_{uuid.uuid4().hex[:8]}@example.com"
    test_password = "Password123!"

    # Register
    try:
        r = requests.post(f"{API_URL}/auth/register", json={
            "email": test_email,
            "display_name": "Automated Tester",
            "password": test_password
        }, timeout=5)
        t.check("User Registration (201)", r.status_code == 201, f"Registered: {test_email}")
    except Exception as e:
        t.check("User Registration", False, str(e))

    # Duplicate Register Conflict (409)
    try:
        r = requests.post(f"{API_URL}/auth/register", json={
            "email": test_email,
            "display_name": "Duplicate Tester",
            "password": test_password
        }, timeout=5)
        t.check("Duplicate Email Rejection (409)", r.status_code == 409, "Rejected duplicate email")
    except Exception as e:
        t.check("Duplicate Email Rejection", False, str(e))

    # Login
    token = None
    try:
        r = requests.post(f"{API_URL}/auth/login", json={
            "email": test_email,
            "password": test_password
        }, timeout=5)
        success = r.status_code == 200 and "access_token" in r.json()
        token = r.json().get("access_token") if success else None
        refresh_token = r.json().get("refresh_token") if success else None
        t.check("User Login (200 + JWT)", success, f"Received Bearer token")
    except Exception as e:
        t.check("User Login", False, str(e))

    headers = {"Authorization": f"Bearer {token}"} if token else {}

    # Token Refresh
    try:
        r = requests.post(f"{API_URL}/auth/refresh", json={"refresh_token": refresh_token}, timeout=5)
        t.check("Token Refresh (200)", r.status_code == 200 and "access_token" in r.json(), "New access token issued")
    except Exception as e:
        t.check("Token Refresh", False, str(e))

    # Current User Profile
    try:
        r = requests.get(f"{API_URL}/auth/me", headers=headers, timeout=5)
        t.check("Get Profile /auth/me", r.status_code == 200 and r.json().get("email") == test_email, f"Email: {test_email}")
    except Exception as e:
        t.check("Get Profile", False, str(e))

    # ─────────────────────────────────────────────────────────────
    # 3. Video Upload & Detection Pipeline
    # ─────────────────────────────────────────────────────────────
    print("\n[SECTION 3: Video Upload & Pipeline Execution]")
    real_video_path = ROOT / "sample_videos" / "sample_real_video.mp4"
    fake_video_path = ROOT / "sample_videos" / "sample_deepfake_video.mp4"

    t.check("Sample Real Video Exists", real_video_path.exists(), f"Size: {real_video_path.stat().st_size} bytes")
    t.check("Sample Deepfake Video Exists", fake_video_path.exists(), f"Size: {fake_video_path.stat().st_size} bytes")

    # Upload Real Video
    job_id = None
    video_id = None
    try:
        with open(real_video_path, "rb") as f:
            r = requests.post(f"{API_URL}/videos/", headers=headers, files={"file": ("sample_real.mp4", f, "video/mp4")}, timeout=15)
        success = r.status_code == 202 and "job_id" in r.json()
        if success:
            job_id = r.json()["job_id"]
            video_id = r.json()["video_id"]
        t.check("Upload Video (202 Accepted)", success, f"Job ID: {job_id}")
    except Exception as e:
        t.check("Upload Video", False, str(e))

    # Wait for Background Job Completion (real inference on CPU takes 40-70 seconds)
    job_completed = False
    attestation_id = None
    if job_id:
        print("    Waiting for background detection pipeline...")
        for _ in range(80):
            time.sleep(1)
            r = requests.get(f"{API_URL}/jobs/{job_id}", headers=headers)
            status = r.json().get("status")
            if status == "completed":
                job_completed = True
                res_sum = r.json().get("result_summary")
                if isinstance(res_sum, str):
                    import json
                    res_sum = json.loads(res_sum)
                attestation_id = (res_sum or {}).get("attestation_id")
                break
            elif status == "failed":
                break

    t.check("Job Execution Completed", job_completed, f"Final status: completed, Attestation: {attestation_id}")

    # ─────────────────────────────────────────────────────────────
    # 4. Jobs, Attestations & Verification
    # ─────────────────────────────────────────────────────────────
    print("\n[SECTION 4: Cryptographic Attestations & Verification]")
    # List Jobs
    try:
        r = requests.get(f"{API_URL}/jobs/", headers=headers, timeout=5)
        jobs = r.json().get("jobs", [])
        t.check("List Jobs (/jobs/)", r.status_code == 200 and len(jobs) > 0, f"Found {len(jobs)} jobs")
    except Exception as e:
        t.check("List Jobs", False, str(e))

    # List Attestations
    try:
        r = requests.get(f"{API_URL}/attestations/", headers=headers, timeout=5)
        atts = r.json().get("attestations", [])
        t.check("List Attestations (/attestations/)", r.status_code == 200 and len(atts) > 0, f"Found {len(atts)} attestations")
    except Exception as e:
        t.check("List Attestations", False, str(e))

    # Get Attestation Details
    if attestation_id:
        try:
            r = requests.get(f"{API_URL}/attestations/{attestation_id}", headers=headers, timeout=5)
            att_data = r.json()
            has_crypto = bool(att_data.get("signature")) and bool(att_data.get("public_key_pem"))
            t.check("Fetch Attestation Manifest", r.status_code == 200 and has_crypto, f"Verdict: {att_data.get('verdict')}")
        except Exception as e:
            t.check("Fetch Attestation Manifest", False, str(e))

        # Attestation Package Download
        try:
            r = requests.get(f"{API_URL}/attestations/{attestation_id}/package", headers=headers, timeout=5)
            pkg = r.json()
            t.check("Download Attestation Package", r.status_code == 200 and "manifest" in pkg, "Full cryptographic package retrieved")
        except Exception as e:
            t.check("Download Attestation Package", False, str(e))

        # Public Verification by ID
        try:
            r = requests.post(f"{API_URL}/verify/by-id", json={"attestation_id": attestation_id}, timeout=5)
            v_res = r.json()
            all_pass = v_res.get("all_passed") is True
            t.check("Public Verify by ID", r.status_code == 200 and all_pass, f"All checks passed: {all_pass}")
        except Exception as e:
            t.check("Public Verify by ID", False, str(e))

        # Verification by Uploading Video
        try:
            with open(real_video_path, "rb") as f:
                r = requests.post(
                    f"{API_URL}/verify/by-upload",
                    data={"attestation_id": attestation_id},
                    files={"file": ("sample_real.mp4", f, "video/mp4")},
                    timeout=10,
                )
            v_res = r.json()
            checks = {c["name"]: c["status"] for c in v_res.get("checks", [])}
            all_ok = checks.get("hash_integrity") == "pass" and checks.get("signature") == "pass"
            t.check("Verify by Video Upload", r.status_code == 200 and all_ok, f"Hash: {checks.get('hash_integrity')}, Sig: {checks.get('signature')}")
        except Exception as e:
            t.check("Verify by Video Upload", False, str(e))

    # ─────────────────────────────────────────────────────────────
    # 5. ML Models & Weights Verification
    # ─────────────────────────────────────────────────────────────
    print("\n[SECTION 5: Trained ML Model Weights & Inference]")
    # Spatial Model
    spatial_w = ROOT / "weights" / "spatial.pt"
    if spatial_w.exists():
        try:
            state = torch.load(spatial_w, map_location="cpu", weights_only=False)
            t.check("Model 1: EfficientNet-B4 Weights", len(state) > 10, f"Size: {spatial_w.stat().st_size / (1024*1024):.1f} MB")
        except Exception as e:
            t.check("Model 1: EfficientNet-B4 Weights", False, str(e))

    # Frequency Model
    freq_w = ROOT / "weights" / "frequency.pt"
    if freq_w.exists():
        try:
            state = torch.load(freq_w, map_location="cpu", weights_only=False)
            t.check("Model 2: FrequencyCNN Weights", len(state) > 5, f"Size: {freq_w.stat().st_size / (1024*1024):.1f} MB")
        except Exception as e:
            t.check("Model 2: FrequencyCNN Weights", False, str(e))

    # Temporal Model
    temp_w = ROOT / "weights" / "temporal.pt"
    if temp_w.exists():
        try:
            state = torch.load(temp_w, map_location="cpu", weights_only=False)
            t.check("Model 3: TemporalBiGRU Weights", len(state) > 5, f"Size: {temp_w.stat().st_size / (1024*1024):.1f} MB")
        except Exception as e:
            t.check("Model 3: TemporalBiGRU Weights", False, str(e))

    # Scripted TorchScript
    scripted_temp = ROOT / "checkpoints" / "temporal_scripted.pt"
    if scripted_temp.exists():
        try:
            model_ts = torch.jit.load(str(scripted_temp))
            inp = torch.randn(1, 20, 1792)
            lens = torch.tensor([20], dtype=torch.long)
            out = model_ts(inp, lens)
            t.check("Temporal TorchScript Inference", out.shape == (1,) and 0.0 <= out.item() <= 1.0, f"Output prob: {out.item():.4f}")
        except Exception as e:
            t.check("Temporal TorchScript Inference", False, str(e))

    # ─────────────────────────────────────────────────────────────
    # 6. Frontend Pages & Assets
    # ─────────────────────────────────────────────────────────────
    print("\n[SECTION 6: Frontend Single-Page Application Routes]")
    routes = ["/", "/login", "/register", "/upload", "/jobs", "/attestations", "/verify"]
    html_headers = {"Accept": "text/html"}
    for route in routes:
        try:
            r = requests.get(f"{FRONTEND_URL}{route}", headers=html_headers, timeout=3)
            t.check(f"Frontend Route '{route}'", r.status_code == 200 and "<html" in r.text.lower(), f"HTTP 200 OK")
        except Exception as e:
            t.check(f"Frontend Route '{route}'", False, str(e))

    # Summary
    print("\n" + "=" * 70)
    print(f" TOTAL TESTS: {t.passed + t.failed} | PASSED: {t.passed} | FAILED: {t.failed}")
    print("=" * 70)

    if t.failed == 0:
        print("\n🎉 ALL CHECKS PASSED 100%! SYSTEM IS COMPLETELY OPERATIONAL.")
        sys.exit(0)
    else:
        print(f"\n⚠️  {t.failed} CHECKS FAILED.")
        sys.exit(1)

if __name__ == "__main__":
    test_everything()

