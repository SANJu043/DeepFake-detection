# Deepfake Detection and Cryptographic Authenticity System

A production-quality system that combines AI-powered deepfake detection with cryptographic provenance verification.

## Overview

This system allows users to:
1. **Upload videos** for deepfake analysis
2. **Detect manipulations** using an ensemble of deep learning models (EfficientNet-B4, Frequency CNN, Temporal BiGRU)
3. **Cryptographically attest** results with Ed25519 signatures, RFC 3161 timestamps, and Merkle transparency logs
4. **Verify provenance** through a public verification endpoint
5. **Share securely** via X25519 key exchange + AES-256-GCM encryption

> **Key honesty point**: Cryptography cannot tell you whether a video is true. It proves _who vouched for what, when_, and that _nothing changed since_. The AI gives a _probabilistic opinion_. Together they provide verified provenance plus an AI assessment, **not absolute truth**.

## Architecture

```
[Web UI: React] --HTTPS--> [API Gateway: FastAPI]
                                     |
              +----------------------+----------------------+
              |                      |                      |
        [Auth service]    [Job queue: Redis+Celery]  [Verify service]
         JWT, RBAC                   |               (stateless, public)
                                     v
                          [Detection worker (GPU)]
                    FFmpeg -> frame sampler -> face detector -> ensemble
                                     |
                                     v
                            [Policy engine]
                                     |
                                     v
                         [Attestation service]
               manifest builder -> signer (KMS) -> TSA client
                                     |
              +----------------------+----------------------+
              v                      v                      v
        [PostgreSQL]          [MinIO/S3]           [Merkle log service]
```

## Quick Start

```bash
# Clone and configure
cp .env.example .env
# Edit .env with your settings

# Start all services
docker-compose up --build

# Download model weights (if not training from scratch)
python scripts/download_weights.py

# Access
# API:     http://localhost:8000/docs
# Web UI:  http://localhost:5173
# MinIO:   http://localhost:9001
```

## Project Structure

```
deepfake-auth/
├── backend/app/           # FastAPI application
│   ├── api/               # Route handlers
│   ├── core/              # Security, RBAC, logging
│   ├── models/            # SQLAlchemy ORM models
│   ├── schemas/           # Pydantic validation schemas
│   ├── services/          # Business logic
│   └── workers/           # Celery tasks
├── ml/                    # Machine learning package
│   ├── datasets/          # Data loaders and splits
│   ├── models/            # Model architectures
│   ├── anomaly/           # Isolation Forest anomaly detector
│   ├── configs/           # Training configurations
│   ├── train.py
│   ├── evaluate.py
│   ├── export.py
│   └── gradcam.py
├── frontend/              # React + Vite + Tailwind
├── deploy/                # Dockerfiles, nginx, vault config
├── docs/                  # Architecture, threat model, API, evaluation
├── scripts/               # CA generation, key seeding, attack simulation
└── tests/                 # pytest test suite
```

## Verdict Labels

| Verdict | Score Range | Meaning |
|---|---|---|
| `NO_MANIPULATION_DETECTED` | < 0.30 | Model found no signs of manipulation |
| `INCONCLUSIVE` | 0.30 – 0.70 | Uncertain; manual review recommended |
| `LIKELY_MANIPULATED` | > 0.70 | Model found strong signs of manipulation |

Special cases: Videos with no detectable face or under 2 seconds → `INCONCLUSIVE` with reason.

## Security Features

- **Ed25519 digital signatures** on attestation manifests
- **RFC 3161 trusted timestamps**
- **Merkle transparency log** (RFC 6962/9162 style)
- **AES-256-GCM encryption** at rest
- **X25519 + HKDF + AES-256-GCM** for secure sharing
- **Isolation Forest anomaly detection** on usage patterns
- **RBAC, JWT auth, rate limiting, CORS, audit logging**

## Limitations (stated honestly)

1. Detectors generalize poorly to unseen generators — this is an arms race
2. A signature proves the claim was made by the signer, not that the claim is true
3. Re-encoding breaks exact hashes; perceptual matching is a weaker guarantee
4. A malicious user could submit a deepfake the detector misses and still receive a valid signature
5. Trust depends on CA and key management
6. Privacy: storing user videos has legal and ethical implications

## License

MIT

## Team

Built as a university project (Multimedia track: AI + Information Security + Cryptography).
