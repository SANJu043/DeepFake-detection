# DeepAuth — Developer Usage Guide

> **Project status: ✅ COMPLETE** — 80/80 tests passing, frontend builds clean, all modules implemented.

---

## Table of Contents

1. [Project Overview](#1-project-overview)
2. [Prerequisites](#2-prerequisites)
3. [First-Time Setup](#3-first-time-setup)
4. [Running Locally (without Docker)](#4-running-locally-without-docker)
5. [Running with Docker Compose](#5-running-with-docker-compose)
6. [Running the Test Suite](#6-running-the-test-suite)
7. [Frontend Development](#7-frontend-development)
8. [ML Training & Evaluation](#8-ml-training--evaluation)
9. [Developer Scripts](#9-developer-scripts)
10. [API Quick Reference](#10-api-quick-reference)
11. [Project Layout](#11-project-layout)
12. [Env Variables Cheatsheet](#12-env-variables-cheatsheet)

---

## 1. Project Overview

**DeepAuth** combines three things:

| Component | What it does |
|-----------|-------------|
| **AI Detection** | Ensemble of EfficientNet-B4 (spatial) + FrequencyCNN + TemporalBiGRU classifies video frames as real or fake |
| **Cryptographic Attestation** | Ed25519 signature + RFC 3161 timestamp + Merkle transparency log on every result |
| **Independent Verification** | Anyone with an attestation ID can prove the result was not tampered with |

**Verdict scale:** `NO_MANIPULATION_DETECTED` (score < 0.30) · `INCONCLUSIVE` (0.30–0.70) · `LIKELY_MANIPULATED` (score > 0.70)

---

## 2. Prerequisites

### For the backend / API
| Tool | Version | Install |
|------|---------|---------|
| Python | 3.11+ | [python.org](https://python.org) |
| PostgreSQL | 15+ | `brew install postgresql@16` |
| Redis | 7+ | `brew install redis` |
| FFmpeg | any | `brew install ffmpeg` |

### For the full Docker stack
| Tool | Version |
|------|---------|
| Docker Desktop | 24+ |
| Docker Compose | v2 |

### For ML training
| Tool | Note |
|------|------|
| CUDA GPU | Optional — CPU works for inference, slow for training |
| PyTorch 2.x | Installed via `ml/requirements.txt` |

---

## 3. First-Time Setup

### Step 1 — Clone & configure environment

```bash
cd deepfake-auth

# Copy env template
cp .env.example .env

# Edit secrets — the important ones:
# JWT_SECRET_KEY, MASTER_KEY, POSTGRES_PASSWORD, MINIO_SECRET_KEY
nano .env
```

### Step 2 — Generate development signing keys

```bash
# Creates keys/signing_{private,public}.pem  and  keys/tsa/tsa_{private,public}.pem
python scripts/seed_keys.py --output-dir ./keys
```

You will see fingerprints printed — keep the private keys out of version control (`keys/` is already in `.gitignore`).

### Step 3 — Install Python dependencies

```bash
# Backend
pip install -r backend/requirements.txt

# ML (only needed for training/evaluation)
pip install -r ml/requirements.txt
```

### Step 4 — Download / generate model weights

```bash
# For quick local testing (creates random-init weights — detection will not be meaningful)
python scripts/download_weights.py --mock --output-dir ./weights

# For real training, see Section 8
```

---

## 4. Running Locally (without Docker)

You need PostgreSQL and Redis already running.

### 4a — Apply database migrations

```bash
# From the project root
export POSTGRES_USER=dfauth
export POSTGRES_PASSWORD=changeme
export POSTGRES_HOST=localhost
export POSTGRES_PORT=5432
export POSTGRES_DB=deepfake_auth

alembic upgrade head
```

### 4b — Start the FastAPI server

```bash
# From project root so 'backend' package resolves
PYTHONPATH=. uvicorn backend.app.main:app --reload --port 8000
```

API is now at **http://localhost:8000**  
Interactive docs at **http://localhost:8000/docs**

### 4c — Start the Celery detection worker

```bash
# In a separate terminal
PYTHONPATH=. celery -A backend.app.workers.celery_app worker \
  --loglevel=info --concurrency=1 --queues=deepfake_detection
```

### 4d — Start the React frontend (dev server)

```bash
cd frontend
npm install          # first time only
npm run dev
```

Frontend at **http://localhost:5173**

---

## 5. Running with Docker Compose

The quickest way to get the entire stack up:

```bash
# Build all images and start everything
docker compose up --build

# Or in background
docker compose up --build -d

# Tear down (keep volumes)
docker compose down

# Tear down and wipe all data
docker compose down -v
```

| Service | URL |
|---------|-----|
| Web UI | http://localhost:5173 |
| API + Swagger docs | http://localhost:8000/docs |
| MinIO console | http://localhost:9001 (user: `minioadmin` / `minioadmin`) |
| PostgreSQL | localhost:5432 |
| Redis | localhost:6379 |

> **Note:** The first `docker compose up --build` runs `alembic upgrade head` automatically via the API container's entrypoint.

---

## 6. Running the Test Suite

```bash
# All 80 tests (crypto services + API integration)
PYTHONPATH=. pytest backend/tests/ -v

# Just cryptographic service unit tests (64 tests, no DB needed)
PYTHONPATH=. pytest backend/tests/test_crypto_services.py -v

# Just API integration tests (16 tests, uses in-memory SQLite)
PYTHONPATH=. pytest backend/tests/test_api_endpoints.py -v

# With coverage report
PYTHONPATH=. pytest backend/tests/ --cov=backend/app --cov-report=term-missing
```

Expected output:
```
80 passed, 1 warning in ~4s
```

---

## 7. Frontend Development

```bash
cd frontend

# Development with hot-reload
npm run dev

# Production build (output → frontend/dist/)
npm run build

# Lint check
npm run lint

# Preview production build locally
npm run preview
```

### Pages

| URL | Page | Access |
|-----|------|--------|
| `/login` | Sign in | Public |
| `/register` | Create account | Public |
| `/verify` | Verify an attestation by ID | Public |
| `/` | Dashboard (stats + recent jobs) | Auth required |
| `/upload` | Upload video for analysis | Auth required |
| `/jobs` | Detection job monitor | Auth required |
| `/attestations` | Signed attestation viewer | Auth required |

---

## 8. ML Training & Evaluation

### 8a — Prepare datasets

Expected directory structure for frame-based models:

```
data/frames/
├── train/
│   ├── real/videoName/frame_000.jpg ...
│   └── fake/videoName/frame_000.jpg ...
├── val/
│   ├── real/ ...
│   └── fake/ ...
└── test/
    ├── real/ ...
    └── fake/ ...
```

For the temporal BiGRU, features are pre-extracted tensors:

```
data/features/
├── train/real/videoName.pt
├── train/fake/videoName.pt
├── val/ ...
└── test/ ...
```

### 8b — Train individual models

```bash
# Spatial detector (EfficientNet-B4)
python -m ml.train --config ml/configs/efficientnet_b4.yaml

# Frequency detector
python -m ml.train --config ml/configs/frequency_cnn.yaml

# Temporal detector (requires pre-extracted features)
python -m ml.train --config ml/configs/temporal_bigru.yaml
```

Checkpoints are saved to `./checkpoints/` (or the `output_dir` in the YAML).

### 8c — Calibrate ensemble weights

After all three individual models are trained:

```bash
python -m ml.train --config ml/configs/ensemble.yaml
```

### 8d — Evaluate a model

```bash
# Single model
python -m ml.evaluate \
  --config ml/configs/efficientnet_b4.yaml \
  --weights checkpoints/spatial.pt \
  --output results/spatial_eval.json

# Ensemble
python -m ml.evaluate \
  --config ml/configs/efficientnet_b4.yaml \
  --weights-dir checkpoints/ \
  --output results/ensemble_eval.json
```

### 8e — Export for deployment

```bash
# ONNX (recommended for inference server)
python -m ml.export --model spatial --weights checkpoints/spatial.pt --format onnx

# TorchScript
python -m ml.export --model spatial --weights checkpoints/spatial.pt --format torchscript
```

### 8f — GradCAM visualizations (explainability)

```bash
python -m ml.gradcam \
  --model spatial \
  --weights checkpoints/spatial.pt \
  --image path/to/face_crop.jpg \
  --output gradcam_output.jpg
```

### 8g — Train anomaly detector

```bash
# Generate baseline traffic JSONL, then:
python -m ml.anomaly.train_anomaly \
  --data baseline_traffic.jsonl \
  --output anomaly_model.pkl \
  --contamination 0.05
```

---

## 9. Developer Scripts

### Generate demo CA and signing certificates

```bash
python scripts/generate_ca.py --output-dir ./keys
```

### Regenerate signing keys (dev setup)

```bash
python scripts/seed_keys.py --output-dir ./keys
```

Prints public key fingerprints and writes:
- `keys/signing_private.pem` / `signing_public.pem`
- `keys/tsa/tsa_private.pem` / `tsa_public.pem`

### Simulate attacks (for demos)

```bash
# Run all attack simulations against local crypto stack
python scripts/simulate_attack.py --attack all --key-dir ./keys

# Individual attack types
python scripts/simulate_attack.py --attack replay
python scripts/simulate_attack.py --attack tamper
python scripts/simulate_attack.py --attack nonce
```

Expected output — all three attacks are **blocked and explained**.

### Generate/download model weights

```bash
# Mock weights for local development (no GPU needed)
python scripts/download_weights.py --mock --output-dir ./weights

# Real weights (replace None URLs in WEIGHT_REGISTRY with actual URLs first)
python scripts/download_weights.py --output-dir ./weights
```

---

## 10. API Quick Reference

### Authentication flow

```bash
# 1. Register
curl -X POST http://localhost:8000/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email":"user@example.com","display_name":"Demo User","password":"SecurePass1!"}'

# 2. Login → get tokens
curl -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"user@example.com","password":"SecurePass1!"}'
# → {"access_token":"eyJ...","refresh_token":"eyJ...","expires_in":1800}

# 3. Use token
export TOKEN="eyJ..."
curl -H "Authorization: Bearer $TOKEN" http://localhost:8000/auth/me
```

### Upload a video for analysis

```bash
curl -X POST http://localhost:8000/videos/ \
  -H "Authorization: Bearer $TOKEN" \
  -F "file=@/path/to/video.mp4"
# → {"video_id":"...","job_id":"...","sha256":"..."}
```

### Poll detection job status

```bash
curl -H "Authorization: Bearer $TOKEN" \
  http://localhost:8000/jobs/<JOB_ID>
# → {"status":"completed","result_summary":{"verdict":"LIKELY_MANIPULATED","score":0.87,...}}
```

### View signed attestation

```bash
curl -H "Authorization: Bearer $TOKEN" \
  http://localhost:8000/attestations/<ATTESTATION_ID>
```

### Download verification package (share with anyone)

```bash
curl -H "Authorization: Bearer $TOKEN" \
  http://localhost:8000/attestations/<ATTESTATION_ID>/package \
  -o attestation_package.json
```

### Public independent verification (no login needed)

```bash
curl -X POST http://localhost:8000/verify/by-id \
  -H "Content-Type: application/json" \
  -d '{"attestation_id":"<ATTESTATION_ID>"}'
# → {"all_passed":true,"checks":[...],"ai_verdict":"LIKELY_MANIPULATED","reminder":"..."}
```

### Admin — view active signing key

```bash
curl -H "Authorization: Bearer $ADMIN_TOKEN" \
  http://localhost:8000/admin/keys

# Revoke an attestation
curl -X POST http://localhost:8000/admin/revoke \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"attestation_id":"<ID>","reason":"False positive confirmed"}'
```

---

## 11. Project Layout

```
deepfake-auth/
│
├── backend/                   Python / FastAPI backend
│   ├── app/
│   │   ├── api/               REST route handlers (auth, upload, jobs, attestations, verify, admin, shares)
│   │   ├── core/              Security, RBAC, DB session, structured logging
│   │   ├── models/            SQLAlchemy ORM (8 tables)
│   │   ├── schemas/           Pydantic request/response models
│   │   ├── services/          Business logic (hashing, signing, manifests, Merkle, TSA, verifier, sharing, anomaly)
│   │   └── workers/           Celery tasks (detection pipeline)
│   ├── tests/
│   │   ├── test_crypto_services.py   64 unit tests
│   │   └── test_api_endpoints.py     16 integration tests
│   └── requirements.txt
│
├── ml/                        Machine learning package
│   ├── models/                EfficientNet-B4, FrequencyCNN, TemporalBiGRU, Ensemble
│   ├── datasets/              Data loaders (FF++, Celeb-DF, DFDC)
│   ├── anomaly/               Isolation Forest training
│   ├── configs/               Training YAML configs for all 4 models
│   ├── train.py               Training script (AMP, early stopping)
│   ├── evaluate.py            Evaluation (AUC-ROC, threshold sweep)
│   ├── export.py              ONNX / TorchScript export
│   └── gradcam.py             GradCAM explainability
│
├── frontend/                  React 19 + Vite + Lucide icons
│   └── src/pages/             Dashboard, Upload, Jobs, Attestations, Verify, Login, Register
│
├── alembic/                   DB migrations
│   └── versions/              20261026_0001 — initial schema (8 tables)
│
├── deploy/                    Docker configs
│   ├── Dockerfile.api
│   ├── Dockerfile.worker
│   ├── Dockerfile.frontend
│   └── nginx.conf
│
├── docs/                      Architecture, threat model, API reference, evaluation methodology
├── scripts/                   generate_ca, seed_keys, download_weights, simulate_attack
├── keys/                      (gitignored) Ed25519 signing & TSA keys
├── weights/                   (gitignored) Model checkpoint files
│
├── docker-compose.yml
├── alembic.ini
├── .env.example               → copy to .env and fill in secrets
├── README.md                  Project overview
├── USAGE.md                   This file
└── PROGRESS.md                Implementation checklist (all 100%)
```

---

## 12. Env Variables Cheatsheet

Copy `.env.example` to `.env` and set these values before running:

| Variable | Default | Required | Notes |
|----------|---------|----------|-------|
| `SECRET_KEY` | `change-me` | ✅ | Random 32-byte hex |
| `JWT_SECRET_KEY` | `change-me-jwt` | ✅ | Random 32-byte hex |
| `MASTER_KEY` | `000...` (64 hex) | ✅ | 256-bit AES key for video encryption |
| `POSTGRES_PASSWORD` | `changeme` | ✅ | DB password |
| `POSTGRES_HOST` | `localhost` | — | Use `db` inside Docker |
| `REDIS_URL` | `redis://localhost:6379/0` | — | Use `redis://redis:6379/0` inside Docker |
| `MINIO_ENDPOINT` | `localhost:9000` | — | Use `minio:9000` inside Docker |
| `MINIO_SECRET_KEY` | `minioadmin` | ✅ prod | Change in production |
| `SIGNER_BACKEND` | `local` | — | `local` / `softhsm` / `vault` |
| `SIGNING_KEY_DIR` | `./keys` | — | Path to Ed25519 key directory |
| `TSA_BACKEND` | `local` | — | `local` / `freetsa` / `custom` |
| `DEBUG` | `true` | — | Set `false` in production |

Generate secure keys:

```bash
python -c "import secrets; print(secrets.token_hex(32))"   # SECRET_KEY / JWT_SECRET_KEY
python -c "import secrets; print(secrets.token_hex(32))"   # MASTER_KEY (64 hex chars)
```

---

## ⚠️ Honest Limitations

Before presenting this project, understand what it **does not** guarantee:

1. **A valid signature proves the system made this claim — not that the claim is correct.** A deepfake that fools the AI will receive a valid attestation saying "no manipulation detected."
2. **Models generalize poorly to unseen generators.** Training on FF++ does not mean the model catches newer GAN/diffusion deepfakes.
3. **Re-encoding breaks exact SHA-256 hashes.** Verification of re-compressed videos falls back to perceptual hashing (weaker).
4. **The anomaly detector needs baseline traffic data.** Mock weights shipped here do not provide meaningful security.
5. **Privacy**: Storing user videos has legal implications. The system is designed for a controlled/academic setting.

These are stated explicitly in `README.md` and `docs/threat_model.md`.

