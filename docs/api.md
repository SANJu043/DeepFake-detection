# DeepAuth — API Reference

Base URL: `https://<host>/` (all paths below are relative to this root)

---

## Table of Contents

1. [Authentication](#1-authentication)
2. [Rate Limiting](#2-rate-limiting)
3. [Pagination](#3-pagination)
4. [Error Format](#4-error-format)
5. [Endpoints](#5-endpoints)
   - [Auth](#51-auth)
   - [Videos](#52-videos)
   - [Jobs](#53-jobs)
   - [Attestations](#54-attestations)
   - [Verification](#55-verification)
   - [Admin](#56-admin)
   - [Shares](#57-shares)
   - [Health](#58-health)

---

## 1. Authentication

DeepAuth uses **JWT Bearer tokens** (HS256).

### Obtaining tokens

Call `POST /auth/login` with your credentials. You receive:
- `access_token` — short-lived (15 minutes). Pass as `Authorization: Bearer <token>`.
- `refresh_token` — long-lived (7 days). Use `POST /auth/refresh` to rotate.

### Using tokens

```http
GET /videos/ HTTP/1.1
Host: api.deepauth.example
Authorization: Bearer eyJhbGci...
```

### RBAC roles

| Role | Capabilities |
|------|-------------|
| `user` | Upload videos, view own jobs/attestations, verify, share |
| `admin` | All user capabilities + revoke attestations, view all keys, view anomalies |

---

## 2. Rate Limiting

Rate limits are enforced per authenticated user (or per IP for unauthenticated endpoints). Limits are returned in response headers:

| Header | Description |
|--------|-------------|
| `X-RateLimit-Limit` | Maximum requests allowed in the window |
| `X-RateLimit-Remaining` | Requests remaining in current window |
| `X-RateLimit-Reset` | Unix timestamp when the window resets |

When a limit is exceeded, the server returns `429 Too Many Requests`.

| Endpoint Group | Limit |
|----------------|-------|
| `POST /auth/login` | 10 req / min per IP |
| `POST /videos/` | 10 req / hour per user |
| `POST /verify/*` | 60 req / hour per user |
| All other authenticated | 300 req / min per user |

---

## 3. Pagination

List endpoints (`GET /videos/`, `GET /jobs/`, etc.) support cursor-based pagination:

**Query parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `limit` | integer | 20 | Items per page (max 100) |
| `cursor` | string | — | Opaque cursor from previous response |

**Response envelope:**

```json
{
  "items": [ ... ],
  "total": 142,
  "next_cursor": "eyJpZCI6IjEyMyJ9",
  "has_more": true
}
```

Pass `next_cursor` as `cursor` in the next request. When `has_more` is `false`, you have reached the last page.

---

## 4. Error Format

All errors follow RFC 7807 (Problem Details):

```json
{
  "type": "https://deepauth.example/errors/not-found",
  "title": "Not Found",
  "status": 404,
  "detail": "Video with id 'abc-123' does not exist or you do not have access.",
  "instance": "/videos/abc-123"
}
```

### Common HTTP Status Codes

| Code | Meaning |
|------|---------|
| `200` | Success |
| `201` | Resource created |
| `202` | Accepted (async job started) |
| `400` | Bad request / validation error |
| `401` | Missing or invalid JWT |
| `403` | Authenticated but insufficient role |
| `404` | Resource not found (or access denied — intentionally ambiguous) |
| `409` | Conflict (e.g., email already registered) |
| `413` | File too large |
| `422` | Unprocessable entity (Pydantic validation failure) |
| `429` | Rate limit exceeded |
| `500` | Internal server error |

---

## 5. Endpoints

---

### 5.1 Auth

---

#### `POST /auth/register`

Register a new user account.

**Auth required:** No

**Request body:**

```json
{
  "email": "alice@example.com",
  "password": "correct-horse-battery-staple"
}
```

| Field | Type | Required | Constraints |
|-------|------|----------|-------------|
| `email` | string | ✓ | Valid email, max 255 chars, unique |
| `password` | string | ✓ | Min 12 chars |

**Response `201`:**

```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "email": "alice@example.com",
  "role": "user",
  "created_at": "2026-11-09T14:00:00Z"
}
```

**Error codes:** `400` (invalid input), `409` (email taken)

**Example:**

```bash
curl -X POST https://api.deepauth.example/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email":"alice@example.com","password":"correct-horse-battery-staple"}'
```

---

#### `POST /auth/login`

Authenticate and receive JWT tokens.

**Auth required:** No

**Request body:**

```json
{
  "email": "alice@example.com",
  "password": "correct-horse-battery-staple"
}
```

**Response `200`:**

```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer",
  "expires_in": 900
}
```

**Error codes:** `401` (invalid credentials), `429` (rate limited)

**Example:**

```bash
curl -X POST https://api.deepauth.example/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"alice@example.com","password":"correct-horse-battery-staple"}'
```

---

#### `POST /auth/refresh`

Exchange a refresh token for a new access token (and rotated refresh token).

**Auth required:** No (refresh token in body)

**Request body:**

```json
{
  "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
}
```

**Response `200`:** Same schema as `/auth/login`.

**Error codes:** `401` (invalid or expired refresh token)

**Example:**

```bash
curl -X POST https://api.deepauth.example/auth/refresh \
  -H "Content-Type: application/json" \
  -d '{"refresh_token":"<refresh_token>"}'
```

---

#### `GET /auth/me`

Return the current authenticated user's profile.

**Auth required:** Yes (`user` or `admin`)

**Response `200`:**

```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "email": "alice@example.com",
  "role": "user",
  "created_at": "2026-11-09T14:00:00Z"
}
```

**Example:**

```bash
curl https://api.deepauth.example/auth/me \
  -H "Authorization: Bearer <access_token>"
```

---

### 5.2 Videos

---

#### `POST /videos/`

Upload a video for deepfake detection analysis.

**Auth required:** Yes (`user` or `admin`)

**Content-Type:** `multipart/form-data`

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `file` | binary | ✓ | Video file (MP4, AVI, MOV, MKV). Max 500 MB. |

**Response `202`:**

```json
{
  "video_id": "b1b2b3b4-...",
  "job_id": "c1c2c3c4-...",
  "status": "PENDING",
  "message": "Video accepted for analysis. Poll GET /jobs/{job_id} for results."
}
```

**Error codes:** `400` (unsupported format), `413` (file too large), `429` (rate limited)

**Example:**

```bash
curl -X POST https://api.deepauth.example/videos/ \
  -H "Authorization: Bearer <access_token>" \
  -F "file=@/path/to/video.mp4"
```

---

#### `GET /videos/`

List videos uploaded by the current user.

**Auth required:** Yes

**Query parameters:** `limit`, `cursor` (see [Pagination](#3-pagination))

**Response `200`:**

```json
{
  "items": [
    {
      "id": "b1b2b3b4-...",
      "filename": "video.mp4",
      "size_bytes": 10485760,
      "sha256": "a3f1...",
      "status": "COMPLETE",
      "created_at": "2026-11-09T14:00:00Z"
    }
  ],
  "total": 5,
  "next_cursor": null,
  "has_more": false
}
```

**Example:**

```bash
curl "https://api.deepauth.example/videos/?limit=10" \
  -H "Authorization: Bearer <access_token>"
```

---

#### `DELETE /videos/{id}`

Delete a video and its associated job/attestation records.

**Auth required:** Yes (owner only)

**Path parameter:** `id` — video UUID

**Response `204`:** No content.

**Error codes:** `404` (not found or not owned by caller)

**Example:**

```bash
curl -X DELETE https://api.deepauth.example/videos/b1b2b3b4-... \
  -H "Authorization: Bearer <access_token>"
```

---

### 5.3 Jobs

---

#### `GET /jobs/`

List analysis jobs for the current user.

**Auth required:** Yes

**Query parameters:** `limit`, `cursor`

**Response `200`:**

```json
{
  "items": [
    {
      "id": "c1c2c3c4-...",
      "video_id": "b1b2b3b4-...",
      "status": "COMPLETE",
      "score": 0.87,
      "verdict": "LIKELY_MANIPULATED",
      "model_versions": {
        "efficientnet_b4": "v2.1.0",
        "frequency_cnn": "v1.3.0",
        "temporal_bigru": "v1.1.0"
      },
      "created_at": "2026-11-09T14:00:00Z",
      "completed_at": "2026-11-09T14:02:17Z"
    }
  ],
  "total": 3,
  "next_cursor": null,
  "has_more": false
}
```

**Job status values:**

| Status | Description |
|--------|-------------|
| `PENDING` | Enqueued, not yet started |
| `RUNNING` | Actively being processed |
| `COMPLETE` | Analysis finished successfully |
| `FAILED` | Unrecoverable error; see `error_message` |

**Example:**

```bash
curl "https://api.deepauth.example/jobs/" \
  -H "Authorization: Bearer <access_token>"
```

---

#### `GET /jobs/{id}`

Retrieve a specific job by ID.

**Auth required:** Yes (owner only)

**Response `200`:** Same schema as a single item from `GET /jobs/`, plus `error_message` field when `status=FAILED`.

**Example:**

```bash
curl https://api.deepauth.example/jobs/c1c2c3c4-... \
  -H "Authorization: Bearer <access_token>"
```

---

### 5.4 Attestations

---

#### `GET /attestations/`

List attestations for the current user.

**Auth required:** Yes

**Query parameters:** `limit`, `cursor`

**Response `200`:**

```json
{
  "items": [
    {
      "id": "d1d2d3d4-...",
      "job_id": "c1c2c3c4-...",
      "verdict": "LIKELY_MANIPULATED",
      "score": 0.87,
      "is_revoked": false,
      "key_id": "key-fingerprint-hex",
      "created_at": "2026-11-09T14:02:30Z"
    }
  ],
  "total": 1,
  "next_cursor": null,
  "has_more": false
}
```

**Example:**

```bash
curl "https://api.deepauth.example/attestations/" \
  -H "Authorization: Bearer <access_token>"
```

---

#### `GET /attestations/{id}`

Retrieve a specific attestation with its full signed manifest.

**Auth required:** Yes (owner only)

**Response `200`:**

```json
{
  "id": "d1d2d3d4-...",
  "job_id": "c1c2c3c4-...",
  "manifest": {
    "schema_version": "1.0",
    "attestation_id": "d1d2d3d4-...",
    "video_sha256": "a3f1...",
    "model_versions": { "efficientnet_b4": "v2.1.0", "frequency_cnn": "v1.3.0", "temporal_bigru": "v1.1.0" },
    "ensemble_weights": [0.4, 0.3, 0.3],
    "score": 0.87,
    "verdict": "LIKELY_MANIPULATED",
    "analysis_timestamp": "2026-11-09T14:02:00Z",
    "nonce": "deadbeef...",
    "signer_key_id": "key-fingerprint-hex"
  },
  "signature_hex": "aabbcc...",
  "key_id": "key-fingerprint-hex",
  "merkle_leaf_index": 42,
  "merkle_root": "1234ab...",
  "tree_size": 100,
  "is_revoked": false,
  "created_at": "2026-11-09T14:02:30Z"
}
```

**Example:**

```bash
curl https://api.deepauth.example/attestations/d1d2d3d4-... \
  -H "Authorization: Bearer <access_token>"
```

---

#### `GET /attestations/{id}/package`

Download the full verifiable attestation bundle as a JSON archive. Suitable for offline verification.

**Auth required:** Yes (owner only)

**Response `200` (`application/json`):**

```json
{
  "manifest": { ... },
  "signature_hex": "aabbcc...",
  "signer_public_key_der_hex": "302a...",
  "timestamp_token_der_hex": "3082...",
  "merkle_proof": {
    "leaf_index": 42,
    "tree_size": 100,
    "root": "1234ab...",
    "audit_path": ["hash1", "hash2", "hash3"]
  }
}
```

**Example:**

```bash
curl https://api.deepauth.example/attestations/d1d2d3d4-.../package \
  -H "Authorization: Bearer <access_token>" \
  -o attestation_bundle.json
```

---

### 5.5 Verification

Verification endpoints are **publicly accessible** (no auth required) so third parties can verify attestations without an account.

> [!NOTE]
> Verification endpoints are still rate-limited per IP address.

---

#### `POST /verify/by-id`

Verify an existing attestation by its ID.

**Auth required:** No

**Request body:**

```json
{
  "attestation_id": "d1d2d3d4-..."
}
```

**Response `200`:**

```json
{
  "valid": true,
  "attestation_id": "d1d2d3d4-...",
  "verdict": "LIKELY_MANIPULATED",
  "score": 0.87,
  "analysis_timestamp": "2026-11-09T14:02:00Z",
  "checks": {
    "signature_valid": true,
    "not_revoked": true,
    "timestamp_valid": true,
    "merkle_inclusion_valid": true
  },
  "failure_reason": null
}
```

When `valid` is `false`, `failure_reason` contains a human-readable explanation and the failed check(s) in `checks` will be `false`.

**Error codes:** `404` (attestation not found)

**Example:**

```bash
curl -X POST https://api.deepauth.example/verify/by-id \
  -H "Content-Type: application/json" \
  -d '{"attestation_id":"d1d2d3d4-..."}'
```

---

#### `POST /verify/by-upload`

Upload a video and an attestation bundle to verify that the bundle was produced for this exact video.

**Auth required:** No

**Content-Type:** `multipart/form-data`

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `file` | binary | ✓ | The video file to verify against |
| `bundle` | binary / JSON | ✓ | The attestation package JSON (from `GET /attestations/{id}/package`) |

**Response `200`:** Same schema as `/verify/by-id`, plus:

```json
{
  "video_hash_matches": true
}
```

If `video_hash_matches` is `false`, the bundle was not produced for this video.

**Example:**

```bash
curl -X POST https://api.deepauth.example/verify/by-upload \
  -F "file=@/path/to/video.mp4" \
  -F "bundle=@attestation_bundle.json"
```

---

### 5.6 Admin

**All admin endpoints require role `admin`.**

---

#### `POST /admin/revoke`

Revoke an attestation (e.g., due to signing key compromise or discovered error).

**Auth required:** Yes (`admin`)

**Request body:**

```json
{
  "attestation_id": "d1d2d3d4-...",
  "reason": "Signing key compromised; re-analysis required."
}
```

**Response `200`:**

```json
{
  "revoked": true,
  "attestation_id": "d1d2d3d4-...",
  "revoked_at": "2026-11-09T16:00:00Z"
}
```

**Error codes:** `404` (attestation not found), `409` (already revoked)

**Example:**

```bash
curl -X POST https://api.deepauth.example/admin/revoke \
  -H "Authorization: Bearer <admin_token>" \
  -H "Content-Type: application/json" \
  -d '{"attestation_id":"d1d2d3d4-...","reason":"Key compromise."}'
```

---

#### `GET /admin/keys`

List all signing key IDs, their status, and their public keys.

**Auth required:** Yes (`admin`)

**Response `200`:**

```json
{
  "keys": [
    {
      "key_id": "key-fingerprint-hex",
      "algorithm": "Ed25519",
      "public_key_der_hex": "302a...",
      "status": "active",
      "created_at": "2026-01-01T00:00:00Z",
      "revoked_at": null
    }
  ]
}
```

**Example:**

```bash
curl https://api.deepauth.example/admin/keys \
  -H "Authorization: Bearer <admin_token>"
```

---

#### `GET /admin/anomalies`

List unresolved anomaly events detected by the Isolation Forest monitor.

**Auth required:** Yes (`admin`)

**Query parameters:** `limit`, `cursor`, `resolved` (bool, default `false`)

**Response `200`:**

```json
{
  "items": [
    {
      "id": "e1e2e3e4-...",
      "user_id": "550e8400-...",
      "event_type": "UPLOAD_RATE_SPIKE",
      "severity": "HIGH",
      "features": {
        "uploads_last_hour": 48,
        "mean_file_size_mb": 450,
        "distinct_ips": 3
      },
      "resolved": false,
      "created_at": "2026-11-09T15:30:00Z"
    }
  ],
  "total": 2,
  "next_cursor": null,
  "has_more": false
}
```

**Example:**

```bash
curl "https://api.deepauth.example/admin/anomalies?resolved=false" \
  -H "Authorization: Bearer <admin_token>"
```

---

### 5.7 Shares

---

#### `POST /shares/`

Share an attestation with another party using encrypted delivery.

**Auth required:** Yes (owner of the attestation)

**Request body:**

```json
{
  "attestation_id": "d1d2d3d4-...",
  "recipient_public_key_hex": "hex-encoded X25519 public key of recipient",
  "expires_in_hours": 72
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `attestation_id` | UUID | ✓ | Attestation to share |
| `recipient_public_key_hex` | string | ✓ | Recipient's X25519 public key (hex) |
| `expires_in_hours` | integer | ✗ | Expiry in hours (default: 168 = 7 days) |

**Response `201`:**

```json
{
  "share_id": "f1f2f3f4-...",
  "expires_at": "2026-11-12T14:00:00Z",
  "message": "Share created. Provide the share_id to the recipient."
}
```

**Example:**

```bash
curl -X POST https://api.deepauth.example/shares/ \
  -H "Authorization: Bearer <access_token>" \
  -H "Content-Type: application/json" \
  -d '{
    "attestation_id": "d1d2d3d4-...",
    "recipient_public_key_hex": "8f40c5adb68f25624ae5b214ea767a6ec94d829d3d7b5e1ad1ba6f3e2138285f",
    "expires_in_hours": 72
  }'
```

---

#### `GET /shares/`

List shares created by the current user.

**Auth required:** Yes

**Query parameters:** `limit`, `cursor`

**Response `200`:**

```json
{
  "items": [
    {
      "id": "f1f2f3f4-...",
      "attestation_id": "d1d2d3d4-...",
      "expires_at": "2026-11-12T14:00:00Z",
      "created_at": "2026-11-09T14:00:00Z"
    }
  ],
  "total": 1,
  "next_cursor": null,
  "has_more": false
}
```

**Example:**

```bash
curl "https://api.deepauth.example/shares/" \
  -H "Authorization: Bearer <access_token>"
```

---

#### `GET /shares/{id}`

Retrieve an encrypted attestation share. The recipient uses their X25519 private key to decrypt it client-side.

**Auth required:** Yes (share recipient — identified by matching key)

**Response `200`:**

```json
{
  "id": "f1f2f3f4-...",
  "attestation_id": "d1d2d3d4-...",
  "ephemeral_public_key_hex": "7e5f4552091a69125d5dfcb7b8c2659029395bdf",
  "encrypted_blob_hex": "aabbccdd...",
  "nonce_hex": "112233...",
  "expires_at": "2026-11-12T14:00:00Z"
}
```

**Decryption (Python pseudocode):**

```python
from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PrivateKey
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

ephemeral_pub = bytes.fromhex(response["ephemeral_public_key_hex"])
ciphertext    = bytes.fromhex(response["encrypted_blob_hex"])
nonce         = bytes.fromhex(response["nonce_hex"])

shared_secret = recipient_private_key.exchange(
    X25519PublicKey.from_public_bytes(ephemeral_pub)
)
aes_key = HKDF(
    algorithm=hashes.SHA256(), length=32,
    salt=None, info=b"deepauth-share-v1"
).derive(shared_secret)

plaintext = AESGCM(aes_key).decrypt(nonce, ciphertext, None)
bundle = json.loads(plaintext)
```

**Error codes:** `404` (share not found), `410` (share expired)

**Example:**

```bash
curl https://api.deepauth.example/shares/f1f2f3f4-... \
  -H "Authorization: Bearer <access_token>"
```

---

### 5.8 Health

---

#### `GET /health`

Returns the operational status of all system components. No authentication required.

**Response `200`:**

```json
{
  "status": "healthy",
  "version": "1.0.0",
  "components": {
    "database": "ok",
    "redis": "ok",
    "minio": "ok",
    "worker_queue_depth": 3
  },
  "timestamp": "2026-11-09T14:00:00Z"
}
```

When any component is degraded, `status` becomes `"degraded"` and `HTTP 503` is returned — useful for load balancer health checks.

**Example:**

```bash
curl https://api.deepauth.example/health
```
