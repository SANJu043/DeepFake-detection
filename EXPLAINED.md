# DeepAuth — Everything Explained From Scratch

> Written for someone who has never studied ML, cryptography, or backend development.  
> Every concept is explained **before** the technical term is introduced.

---

## Table of Contents

1. [What Problem Does This Project Solve?](#1-what-problem-does-this-project-solve)
2. [The Big Picture — How It All Works Together](#2-the-big-picture--how-it-all-works-together)
3. [Layer 1 — The AI Detection System (ML)](#3-layer-1--the-ai-detection-system-ml)
   - 3a. What is a deepfake?
   - 3b. How does a computer detect a deepfake?
   - 3c. EfficientNet-B4 — the "eye" model
   - 3d. FrequencyCNN — the "noise pattern" model
   - 3e. TemporalBiGRU — the "motion" model
   - 3f. The Ensemble — combining all three opinions
   - 3g. The Policy Engine — turning a number into a verdict
4. [Layer 2 — The Cryptographic Proof System](#4-layer-2--the-cryptographic-proof-system)
   - 4a. Why can't we just trust the AI output?
   - 4b. Hashing — a video's fingerprint
   - 4c. Ed25519 Digital Signature — the official stamp
   - 4d. The Attestation Manifest — the certificate document
   - 4e. RFC 3161 Timestamp — proving when it happened
   - 4f. The Merkle Transparency Log — the public audit trail
   - 4g. Verification — anyone can check the proof
5. [Layer 3 — The Web Application](#5-layer-3--the-web-application)
   - 5a. The Backend API (FastAPI)
   - 5b. The Database (PostgreSQL)
   - 5c. The Job Queue (Redis + Celery)
   - 5d. File Storage (MinIO)
   - 5e. The Frontend (React)
6. [Security Features (The Guards)](#6-security-features-the-guards)
7. [The Complete Flow — Step by Step](#7-the-complete-flow--step-by-step)
8. [File-by-File Explanation](#8-file-by-file-explanation)
9. [The Honest Limitations](#9-the-honest-limitations)
10. [Glossary — All Terms Defined Simply](#10-glossary--all-terms-defined-simply)

---

## 1. What Problem Does This Project Solve?

### The problem in one sentence
> **Anyone can create a fake video today and claim it is real. There is no reliable way to prove who analyzed a video, what they found, or whether the result was tampered with later.**

### Why deepfakes are dangerous
A "deepfake" is a video where someone's face has been synthetically replaced or animated using AI. These can be used to:
- Fabricate things a politician never said
- Create fake evidence in legal disputes
- Spread misinformation about events that never happened

Modern deepfake quality is so good that **the human eye often cannot tell the difference**.

### What DeepAuth does about it
DeepAuth does **two things** that existing tools don't combine:

| What it does | Why it matters |
|---|---|
| **Runs three AI models on your video** to detect signs of manipulation | Faster and more consistent than a human expert |
| **Cryptographically signs and timestamps the result** | Anyone can independently verify: "This system analyzed this exact video on this exact date and produced this result — and nothing has changed since" |

### The key insight (what makes this project unique)
The AI alone is not trustworthy — it can be wrong, and someone could claim it said something it didn't. The cryptography alone doesn't detect deepfakes. **Together, they create verified, tamper-proof provenance** (a word meaning "documented history of origin").

---

## 2. The Big Picture — How It All Works Together

Imagine a document notary, but for AI analysis results on videos.

```
   YOU upload a video
         │
         ▼
   ┌─────────────┐
   │  AI Analysis│  ← Three AI models examine the video
   │  (Detection)│    and produce a "fakeness score" 0.0–1.0
   └──────┬──────┘
          │ score + verdict
          ▼
   ┌─────────────────┐
   │ Policy Engine   │  ← Converts score to plain verdict:
   │                 │    CLEAN / INCONCLUSIVE / MANIPULATED
   └──────┬──────────┘
          │
          ▼
   ┌──────────────────────────────────────┐
   │  Attestation Manifest (Document)     │  ← Writes a formal document containing:
   │  - video fingerprint (hash)          │    video hash, verdict, score, models used,
   │  - verdict + score                   │    who submitted, what thresholds were used
   │  - who submitted, timestamp          │
   └──────┬───────────────────────────────┘
          │
          ▼
   ┌─────────────┐
   │  Ed25519    │  ← Digitally signs the document
   │  Signature  │    (like a wax seal — proves it wasn't altered)
   └──────┬──────┘
          │
          ▼
   ┌─────────────┐
   │  RFC 3161   │  ← Trusted timestamp from a 3rd party
   │  Timestamp  │    (proves WHEN it was signed)
   └──────┬──────┘
          │
          ▼
   ┌─────────────┐
   │  Merkle Log │  ← Adds the document to a public audit log
   │  (Public)   │    (proves it was logged and not inserted retroactively)
   └──────┬──────┘
          │
          ▼
   ┌─────────────┐
   │  DATABASE   │  ← Stores everything
   └─────────────┘
          │
          ▼
   ANYONE can verify:
   - "Is this attestation genuine?" (verify by ID)
   - "Was this exact video analyzed?" (verify by re-upload)
```

---

## 3. Layer 1 — The AI Detection System (ML)

### 3a. What is a deepfake?

A deepfake is created by an AI "generator" that has learned to swap or animate faces convincingly. When you train an AI on thousands of videos of Person A, it can generate new images that look like Person A saying or doing things they never did.

**The cat-and-mouse game:** Deepfake generators keep improving. Deepfake detectors need to find the subtle "tells" the generators leave behind. This project uses **three different detectors** because each looks for different kinds of tells.

---

### 3b. How does a computer detect a deepfake?

A deepfake video, even when it looks perfect to our eyes, leaves behind tiny clues:

| Type of clue | What it means |
|---|---|
| **Spatial artifacts** | Blurring, unnatural skin texture, warped edges around the face |
| **Frequency artifacts** | Deepfake generators repeat certain noise patterns that don't occur in real cameras |
| **Temporal artifacts** | The face in a deepfake flickers or jitters between frames in ways a real face never does |

Each AI model in this project specializes in finding one type of clue.

---

### 3c. EfficientNet-B4 — the "Eye" Model
**File:** `ml/models/efficientnet_b4.py`

**What it is:** A powerful image recognition neural network, originally created by Google to classify objects in photos (cats, cars, etc.). Here it is "fine-tuned" (retrained) to classify faces as real or fake.

**How it works:**
1. Take a cropped face image (380×380 pixels)
2. Pass it through 32 million parameters (mathematical weights that have learned from millions of real/fake faces)
3. Output a single number: the probability that this face is fake

**Why EfficientNet-B4 specifically?** It has the best balance of accuracy vs. computing power among standard image classifiers. The "B4" means it's the 4th size variant — large enough to be powerful, small enough to run on a single GPU.

**What it looks for:** Spatial artifacts — blurring at the hairline, unnatural eye reflections, skin texture that's too smooth or too uniform.

**Analogy:** A forensic art expert looking at a painting under a magnifying glass for brush-stroke inconsistencies.

---

### 3d. FrequencyCNN — the "Noise Pattern" Model
**File:** `ml/models/frequency_cnn.py`

**What it is:** A custom convolutional neural network that works not on pixels but on **frequency information** extracted from the image.

**Background — what is frequency in an image?**  
Every digital image is made of patterns of light and dark. A mathematical operation called the **DCT (Discrete Cosine Transform)** — the same math used in JPEG compression — converts pixel values into frequency components. Think of it like breaking music into bass, mid, and treble. Real photos have a certain characteristic "sound." Deepfake generators produce a subtly different "sound" because they synthesize at the pixel level, leaving patterns in the high-frequency range that real cameras don't produce.

**Why this model exists:** Some deepfakes look perfect spatially (fooling the EfficientNet model) but still have frequency artifacts. This model catches what the eye model misses.

**Analogy:** A musician who can hear that a recording was digitally altered, even if it sounds perfect to a non-expert.

---

### 3e. TemporalBiGRU — the "Motion" Model
**File:** `ml/models/temporal_bigru.py`

**What it is:** A recurrent neural network that processes sequences of frames over time, using a **Bidirectional GRU** (Gated Recurrent Unit).

**Breaking down the name:**
- **Temporal** = deals with time (sequences of frames)
- **Bi** = bidirectional (reads the sequence forwards AND backwards)
- **GRU** = a type of "memory" cell that learns patterns in sequences

**How it works:**
1. The EfficientNet-B4 backbone is used to extract a "feature vector" (a list of 1792 numbers that describes the face) for each frame
2. All these frame descriptions are fed as a sequence into the BiGRU
3. The BiGRU reads forwards and backwards through time to detect unnatural transitions
4. An **attention mechanism** highlights which frames are most suspicious
5. Output: a single probability that the video sequence is fake

**Why bidirectional?** A fake face flickering for one frame looks suspicious both coming from the frame before AND the frame after. Reading in both directions catches subtle inconsistencies a one-directional model might miss.

**What it looks for:** Inter-frame jitter, unnatural blinking patterns, inconsistent lighting across frames, face "swimming" that deepfake generators create.

**Analogy:** A film critic who notices that an actor's face looks slightly different between cuts in a suspicious way.

---

### 3f. The Ensemble — Combining All Three Opinions
**File:** `ml/models/ensemble.py`

**What it is:** A thin wrapper that runs all three models and combines their outputs into one final score.

**Why not just use one model?** Each model has blind spots. A deepfake that perfectly fools the spatial model might still have frequency artifacts. An ensemble is more robust — it's harder to fool all three simultaneously.

**How the combining works:**
- Each model outputs a "fakeness score" between 0.0 (definitely real) and 1.0 (definitely fake)
- Three **learnable weights** (trained after the individual models are frozen) determine how much to trust each model: typically spatial ≈ 40%, frequency ≈ 30%, temporal ≈ 30%
- Final score = `0.40 × spatial_score + 0.30 × frequency_score + 0.30 × temporal_score`
- The weights are automatically optimized to minimize errors on a validation set

**What "learnable weights" means:** During a calibration training phase, the system tries millions of different weight combinations and finds which combination makes the fewest mistakes on videos it has never seen before.

**Fallback:** If the temporal model can't run (video too short, fewer than 8 faces detected), the ensemble automatically falls back to a 2-model average of spatial + frequency.

**Analogy:** A panel of three judges, each specializing in something different. Their final verdict is a weighted vote, where more reliable judges get more influence.

---

### 3g. The Policy Engine — Turning a Number into a Verdict
**File:** `backend/app/services/policy.py`

**What it is:** A simple decision function that converts the ensemble's raw probability score into a human-readable verdict.

**The three verdicts:**

| Score range | Verdict | Meaning |
|---|---|---|
| < 0.30 | `NO_MANIPULATION_DETECTED` | The models found no signs of manipulation |
| 0.30 – 0.70 | `INCONCLUSIVE` | The models are uncertain — manual review recommended |
| > 0.70 | `LIKELY_MANIPULATED` | The models found strong signs of manipulation |

**Special cases that always give INCONCLUSIVE:**
- No human face was detected in the video (can't analyze what isn't there)
- Video is under 2 seconds long (not enough frames to be confident)

**Why these thresholds?** They create a "gray zone" in the middle. It would be dishonest to claim certainty when the AI score is 0.5. The wide inconclusive band forces honest uncertainty rather than false confidence.

**Why the word "LIKELY"?** The system is intentionally honest: it says "likely manipulated," not "definitely manipulated." A detector cannot prove authenticity — it can only raise or lower suspicion.

---

## 4. Layer 2 — The Cryptographic Proof System

### 4a. Why Can't We Just Trust the AI Output?

Imagine a lab test result. The lab runs your blood sample and produces a result. You trust it because:
1. You know the lab ran your blood (not someone else's)
2. The result came directly from the lab (not modified in transit)
3. You know when the test was performed

Without these guarantees, someone could fabricate results. The same problem applies to AI analysis. Without cryptographic proofs, someone could:
- Run the AI on Video A, then claim it was run on Video B
- Modify the result after the fact ("it said 0.9 — I'll change it to 0.1")
- Claim the analysis happened recently when it actually happened months ago

The cryptographic system prevents all three attacks.

---

### 4b. Hashing — a Video's Fingerprint
**File:** `backend/app/services/hashing.py`

**What hashing is:** A mathematical function that takes any file (a video, a document, anything) and produces a fixed-length "fingerprint" — a string like `a3f5b8c9...` (64 characters for SHA-256). The critical property: **if even one bit of the file changes, the fingerprint completely changes.**

**SHA-256:** The specific hashing algorithm used. The "256" means the fingerprint is 256 bits = 64 hexadecimal characters. It is computationally impossible to find two different files with the same SHA-256 (this is called "collision resistance").

**Why it matters:** The manifest (see below) records the SHA-256 of your video at the time of analysis. If you later submit the same video for verification, the system recomputes its SHA-256 and checks it matches. If even one pixel changed, verification fails — proving tampering.

**Perceptual hashing (pHash):** SHA-256 is too strict — if a video is re-encoded (even with the same content), its SHA-256 changes. Perceptual hashing is a "fuzzy fingerprint" that stays the same for visually identical content. Used as a fallback for re-encoded videos.

**Analogy:** SHA-256 is like a person's DNA — unique and exact. pHash is like their physical description — still identifies them even after a haircut.

---

### 4c. Ed25519 Digital Signature — the Official Stamp
**File:** `backend/app/services/signer.py`

**What digital signatures are:** A mathematical system using two related keys:
- **Private key** (kept secret, only the system has it): used to "sign" a document
- **Public key** (shared with everyone): used by anyone to "verify" that signature

When the system signs a document with its private key, anyone can use the public key to confirm: "Yes, this was signed by whoever holds that private key, and the document has not been changed since signing."

**Ed25519 specifically:** A modern, fast, and extremely secure signature algorithm. It uses elliptic curve mathematics over a 25519-bit curve. Each signature is 64 bytes. It is resistant to all known attacks including quantum computing concerns for the near future.

**How it works in this project:**
1. The attestation manifest (the full analysis document) is converted to a canonical (standardized) JSON format
2. Ed25519 signs the canonical bytes using the system's private key
3. The signature (64 bytes, stored as hex) is attached to the manifest
4. Anyone can download the public key and verify the signature — if it verifies, the document is genuine and unaltered

**RFC 8785 canonicalization:** Before signing, the JSON must be "standardized" so that `{"a":1,"b":2}` and `{"b":2,"a":1}` produce the same signature (they're the same document, just different key ordering). RFC 8785 is an international standard for how to do this consistently.

**Key management backends:**
- **Local**: keys stored as PEM files on disk (dev/demo use)
- **SoftHSM**: software Hardware Security Module (more secure local storage)
- **Vault**: HashiCorp Vault (enterprise-grade key management)

**Analogy:** Like a notary's official stamp on a legal document. The stamp proves the notary saw the document and it hasn't been forged since.

---

### 4d. The Attestation Manifest — the Certificate Document
**File:** `backend/app/services/manifest.py`

**What it is:** A structured JSON document that formally records everything about one analysis. Think of it like a lab report or a court-admissible document.

**What it contains:**

```
Manifest (the document that gets signed)
├── spec_version: "deepfake-auth/1.0"
├── attestation_id: unique UUID for this attestation
├── nonce: random number (prevents replay attacks)
├── content:
│   ├── sha256: video's exact fingerprint
│   ├── size_bytes: file size
│   ├── duration_s: video length
│   └── perceptual_hash: fuzzy fingerprint array
├── detection:
│   ├── verdict: "LIKELY_MANIPULATED"
│   ├── fake_probability: 0.87
│   ├── thresholds: {clean_lt: 0.30, manipulated_gt: 0.70}
│   └── model_ensemble: [{name, version, weight}, ...]
├── submitter:
│   ├── user_id: who uploaded it
│   └── display_name: their name
├── signer:
│   ├── key_id: which signing key was used
│   ├── algorithm: "Ed25519"
│   └── cert_fingerprint: fingerprint of the signing certificate
├── signature: "hex-encoded-64-byte-ed25519-signature..."
├── timestamp_token: "base64-rfc3161-timestamp..."
└── log:
    ├── merkle_leaf_index: 42
    └── merkle_root: "hex-encoded-root-hash..."
```

**Why record all this detail?** Each field prevents a specific attack or misunderstanding. The nonce prevents the same manifest being replayed for a different video. The thresholds on record prevent someone from changing thresholds and re-claiming verdicts. The model versions on record show exactly which AI was used.

---

### 4e. RFC 3161 Timestamp — Proving When It Happened
**File:** `backend/app/services/timestamp.py`

**The problem without timestamps:** Even with a valid signature, someone could sign a document today and claim it was signed two years ago. Digital signatures alone don't prove *when*.

**What RFC 3161 is:** An international standard (RFC = "Request for Comments," the format for internet standards) for getting a trusted third party to prove a document existed at a specific time.

**How it works:**
1. The system sends the SHA-256 of the signed manifest to a **Time Stamping Authority (TSA)** — a trusted third party (like a notary specialized in timestamps)
2. The TSA creates a **timestamp token** containing: the hash, the TSA's current time, and the TSA's own digital signature
3. This token is stored with the attestation

**Why trust a third party?** The system itself could lie about the time. A trusted TSA has no reason to lie — it's their entire business model to be trustworthy. For development, a local TSA is used; for production, FreeTSA or similar services are used.

**Analogy:** Mailing yourself a letter with a postmark. The post office's postmark proves the letter existed on that date, and you didn't create it today and backdated it.

---

### 4f. The Merkle Transparency Log — the Public Audit Trail
**File:** `backend/app/services/merkle_log.py`

**The problem without a log:** Even with signatures and timestamps, someone could secretly sign a fraudulent attestation and not tell anyone. If there's no public record of all attestations, how do you know the system hasn't been used fraudulently?

**What a Merkle tree is:**  
Imagine a tournament bracket. 8 teams play → 4 winners → 2 finals → 1 champion. The final score (champion) is computed from all 8 original scores. If you change any one original score, the final score changes completely. This is a Merkle tree.

```
              Root Hash
             /          \
       Node_AB           Node_CD
      /      \           /      \
  Leaf_A   Leaf_B    Leaf_C   Leaf_D
   (att1)  (att2)   (att3)   (att4)
```

Each "leaf" is an attestation. If you tamper with any single attestation, the Root Hash changes — proving tampering.

**Key properties:**
- **Append-only**: you can only add leaves, never remove or modify
- **Inclusion proof**: you can prove attestation #42 is in the log without downloading all attestations — just the path from leaf to root (logarithmic size)
- **Consistency proof**: anyone can verify the log has only grown, never been modified

**Domain separation (the 0x00/0x01 prefixes):**  
Leaves are hashed as `SHA-256(0x00 + data)` and internal nodes as `SHA-256(0x01 + left + right)`. This prevents an attacker from crafting data that looks like both a leaf and an internal node.

**Signed Tree Head (STH):** Periodically, the system signs the current root hash. This creates an auditable commitment: "at this timestamp, the log contained exactly these N entries."

**RFC 6962 / 9162:** The standard this implementation follows — the same technology used in Certificate Transparency (the system browsers use to audit SSL certificates).

**Analogy:** A blockchain-style public ledger where every entry is permanent and verifiable. If you edit any entry, the entire chain breaks.

---

### 4g. Verification — Anyone Can Check the Proof
**File:** `backend/app/services/verifier.py`

**What it is:** A 7-step independent verification algorithm that anyone can run to confirm an attestation is genuine.

**The 7 checks (run in order):**

| Check | What it verifies |
|---|---|
| **1. Hash match** | Recompute SHA-256 of the submitted video — does it match what's recorded? |
| **2. Signature validity** | Use the public key to verify the Ed25519 signature on the manifest |
| **3. Certificate validity** | Is the signing certificate within its validity period? |
| **4. Revocation check** | Has this attestation been revoked by an admin? |
| **5. Timestamp validity** | Is the RFC 3161 timestamp from a trusted authority and consistent with signing time? |
| **6. Merkle inclusion** | Is this attestation provably included in the transparency log? |
| **7. Verdict display** | Show the AI verdict with the honest probabilistic reminder |

**Result format:** Each check returns `pass`, `fail`, `skip`, or `warn` — not just a single binary "valid/invalid." This is intentional: a detailed per-check result is more informative and harder to spoof than a single "all good" response.

**Why is this endpoint public (no login required)?** The whole point of the system is that *anyone* — journalists, courts, fact-checkers — can verify an attestation given only its ID. Making verification require an account would defeat this purpose.

---

## 5. Layer 3 — The Web Application

### 5a. The Backend API (FastAPI)
**Files:** `backend/app/api/`, `backend/app/main.py`

**What FastAPI is:** A Python web framework for building APIs — essentially the "brain" that receives requests from the frontend, processes them, and sends back responses.

**What "API" means:** Application Programming Interface — a set of URL endpoints that the frontend (or any program) calls to do things.

**Endpoints (what you can call):**

| Group | Endpoints | What they do |
|---|---|---|
| **Auth** | `/auth/register`, `/auth/login`, `/auth/refresh`, `/auth/me` | Account management |
| **Videos** | `POST/GET/DELETE /videos/` | Upload and manage videos |
| **Jobs** | `GET /jobs/`, `GET /jobs/{id}` | Check detection job status |
| **Attestations** | `GET /attestations/`, `GET /attestations/{id}`, `GET /attestations/{id}/package` | View and download signed results |
| **Verify** | `POST /verify/by-id`, `POST /verify/by-upload` | Public verification |
| **Admin** | `/admin/keys`, `/admin/revoke`, `/admin/anomalies` | Admin-only management |
| **Shares** | `POST/GET /shares/` | Encrypted sharing between users |
| **Health** | `GET /health` | System status check |

**Swagger UI:** FastAPI automatically generates interactive documentation at `http://localhost:8000/docs` — you can call every endpoint directly in the browser to test it.

---

### 5b. The Database (PostgreSQL)
**Files:** `backend/app/models/models.py`, `alembic/`

**What PostgreSQL is:** A relational database — think of it as a very powerful, structured spreadsheet that stores all persistent data. "Relational" means tables are linked to each other (a job links to a video, which links to a user).

**The 8 tables:**

| Table | What it stores |
|---|---|
| `users` | User accounts (email, hashed password, role, X25519 public key for sharing) |
| `videos` | Uploaded video metadata (filename, size, SHA-256, S3 storage location) |
| `jobs` | Detection job status (pending → running → completed/failed) |
| `attestations` | Signed attestation records (manifest, signature, public key, timestamp token, Merkle proof) |
| `revocations` | List of revoked attestations with reasons |
| `shares` | Encrypted sharing envelopes between users |
| `anomaly_events` | Security alerts from the anomaly detection system |
| `audit_log` | Immutable log of every security-relevant action (login, upload, revoke, etc.) |

**Alembic (database migrations):** When the database structure changes (new column, new table), you need a way to update it without losing existing data. Alembic tracks these changes in version-numbered migration scripts, like version control for the database schema.

**Why async SQLAlchemy?** "Async" means the server doesn't sit idle waiting for the database — it handles other requests while the DB query runs. This allows handling many simultaneous users efficiently.

---

### 5c. The Job Queue (Redis + Celery)
**Files:** `backend/app/workers/`

**The problem:** AI detection takes 10–60 seconds. If the web server waited for the AI to finish before responding to the user, the user would see a frozen loading screen for a minute. Web requests should respond in under 1 second.

**The solution — a job queue:**
1. User uploads video → server immediately creates a "job" record → returns `job_id` to the user (< 1 second)
2. The job is placed in a **queue** (a waiting list)
3. A **worker** process (running separately) picks up jobs from the queue and runs the AI analysis
4. User periodically asks: "Is job `xyz` done yet?" — eventually they get the result

**Redis:** An in-memory data store used as the queue/message broker. Think of it as a very fast message board where jobs are posted and workers pick them up.

**Celery:** A Python framework for distributed task processing. It manages the worker processes, retries failed jobs, and handles concurrency.

**Single-GPU concurrency:** Celery is configured with `prefetch_multiplier=1` — only one detection job runs at a time per GPU, preventing memory overflows.

---

### 5d. File Storage (MinIO)
**What MinIO is:** An open-source object storage server that is API-compatible with Amazon S3. It stores uploaded video files. Think of it as a local version of Google Drive that works programmatically.

**Why not store videos in the database?** Video files are large (100MB+). Databases are optimized for structured data (text, numbers), not large binary files. Object storage is designed exactly for large files, with features like chunked upload, streaming, and content delivery.

**In production:** MinIO would be replaced with AWS S3, Google Cloud Storage, or similar.

---

### 5e. The Frontend (React)
**Files:** `frontend/src/`

**What React is:** A JavaScript library for building interactive web user interfaces. Instead of writing HTML that changes with every click, React lets you define what the UI *should look like* based on the current state, and automatically updates the DOM.

**What Vite is:** The build tool that bundles all the React code into files a browser can load efficiently.

**The 7 pages:**

| Page | URL | What it does |
|---|---|---|
| **Login** | `/login` | Email + password sign-in with JWT token storage |
| **Register** | `/register` | New account creation |
| **Dashboard** | `/` | Stats overview + recent jobs quick-view |
| **Upload** | `/upload` | Drag-and-drop video upload with progress bar |
| **Jobs** | `/jobs` | Live detection job monitor (auto-polls every 5 seconds) |
| **Attestations** | `/attestations` | View signed results, inspect JSON manifest, download verification package |
| **Verify** | `/verify` | Public page — anyone enters an attestation ID to verify it |

**JWT (JSON Web Token):** When you log in, the server issues a JWT — a short-lived signed token that proves your identity. The browser stores it and attaches it to every API request as `Authorization: Bearer <token>`. The server checks the signature on every request without needing to query the database each time.

**axios:** The HTTP library used in `api.js` to make API calls. It automatically attaches the JWT token to every request via "interceptors" (middleware that runs before/after each request).

---

## 6. Security Features (The Guards)

### Authentication & Authorization
- **Argon2id password hashing:** The best password hashing algorithm. Even if the database is stolen, passwords cannot be recovered (it's intentionally slow and memory-intensive to prevent brute-force attacks).
- **JWT access tokens (30 min) + refresh tokens (7 days):** Short-lived access tokens minimize damage if stolen. Refresh tokens allow staying logged in without re-entering your password.
- **RBAC (Role-Based Access Control):** Two roles — `user` (can upload and view own data) and `admin` (can revoke attestations, view anomalies). Each API endpoint checks your role before allowing access.

### Attack Prevention
- **Nonce (number used once):** Every attestation manifest contains a randomly generated nonce. This prevents "replay attacks" — taking a valid attestation from one video and trying to claim it applies to another.
- **Rate limiting:** The API limits how many requests a user can make per minute. Prevents abuse.
- **CORS (Cross-Origin Resource Sharing):** Only the frontend domain is allowed to call the API. Prevents malicious websites from making API calls on behalf of a logged-in user.
- **Constant-time comparison:** When comparing signatures or hashes, the system uses constant-time comparison to prevent "timing attacks" where an attacker could guess the correct value by measuring how long comparisons take.

### Anomaly Detection
**Files:** `backend/app/services/anomaly.py`, `ml/anomaly/train_anomaly.py`

An Isolation Forest model (a type of machine learning specifically for anomaly detection) monitors usage patterns:
- How many uploads per hour from one user?
- How many failed login attempts?
- Are requests coming in at an unusual rate?

If behavior looks abnormal (statistically isolated from normal patterns), it triggers an alert recorded in `anomaly_events` and visible to admins.

**Isolation Forest:** This algorithm works by randomly trying to "isolate" data points. Normal points take many random cuts to isolate (they're in a dense cluster). Anomalous points are isolated quickly (they're outliers). The number of cuts needed is the "anomaly score."

### Encrypted Sharing (X25519 + HKDF + AES-256-GCM)
**File:** `backend/app/services/sharing.py`

This allows one user to securely share an attestation with another user so that:
- Only the intended recipient can read it
- The server cannot read the shared content (end-to-end encrypted)

**How it works:**
1. Each user has an X25519 key pair (a Diffie-Hellman keypair for key exchange)
2. Sender uses recipient's public key + their own private key → derives a shared secret (X25519 key exchange)
3. HKDF "stretches" that shared secret into a proper encryption key
4. AES-256-GCM encrypts the attestation data with that key
5. Only the recipient (with their private key) can reverse the process and decrypt

---

## 7. The Complete Flow — Step by Step

Here is exactly what happens from the moment you open the website to when you get a verified result.

```
STEP 1: You open the website
─────────────────────────────
  Browser loads React app (from Vite build)
  → Checks localStorage for existing JWT token
  → If found, calls GET /auth/me to validate
  → If invalid, redirects to /login

STEP 2: You log in
──────────────────
  You type email + password → frontend calls POST /auth/login
  → Backend fetches your user record from PostgreSQL
  → Verifies your password against the Argon2 hash in the DB
  → Creates JWT access token (30 min) + refresh token (7 days)
  → Stores tokens in browser localStorage
  → Redirects you to the Dashboard

STEP 3: You upload a video
──────────────────────────
  You drag a .mp4 file onto the Upload page
  → Frontend calls POST /videos/ with multipart form data
  → Backend reads the file bytes
  → Validates:
      - Is the file size under 200MB?
      - Is the content-type video/mp4, video/quicktime, or video/webm?
      - Do the first 4 bytes match MP4/WebM magic bytes?
  → Computes SHA-256 fingerprint of the file
  → Creates a Video record in PostgreSQL
  → Creates a Job record (status: "pending") in PostgreSQL
  → Puts the job in the Redis queue
  → Returns job_id and video_id to the frontend IMMEDIATELY (< 1 second)

STEP 4: The Celery worker processes the job
────────────────────────────────────────────
  Worker picks up the job from Redis
  → Updates job status to "running"
  → Downloads the video file from MinIO storage
  → FFmpeg extracts frames at 0.2-second intervals (up to 300 frames)
  → Face detector (RetinaFace/MTCNN) finds and crops faces in each frame
  → If no faces found → verdict: INCONCLUSIVE (NO_FACE_DETECTED)
  → If fewer than 8 valid face frames → temporal model is skipped

STEP 5: The ensemble runs on the face crops
────────────────────────────────────────────
  EfficientNet-B4:
    → Each face crop (380×380 px) → 32M parameters → score_spatial
  
  FrequencyCNN:
    → Apply DCT to face crop → extract frequency features → score_frequency
  
  TemporalBiGRU:
    → Extract 1792-dim feature vectors from all frames
    → Feed sequence to BiGRU → attention pooling → score_temporal
  
  Ensemble:
    → score_final = 0.4×score_spatial + 0.3×score_frequency + 0.3×score_temporal

STEP 6: Policy engine converts score to verdict
─────────────────────────────────────────────────
  score_final = 0.87
  → 0.87 > 0.70 threshold
  → Verdict: LIKELY_MANIPULATED

STEP 7: Attestation manifest is built
──────────────────────────────────────
  Manifest is assembled (JSON) containing:
    - attestation_id: randomly generated UUID
    - nonce: random 256-bit number
    - content.sha256: video fingerprint
    - content.perceptual_hash: fuzzy fingerprint
    - detection.verdict: "LIKELY_MANIPULATED"
    - detection.fake_probability: 0.87
    - detection.model_ensemble: [{name, version, weight}, ...]
    - submitter.user_id: your ID
    - signer.key_id: active signing key ID
    - signer.algorithm: "Ed25519"

STEP 8: The manifest is signed
─────────────────────────────────
  → RFC 8785 canonicalizes the JSON (standardizes key ordering)
  → Ed25519 private key signs the canonical bytes → 64-byte signature
  → Signature is added to the manifest (as hex string)

STEP 9: Trusted timestamp is obtained
──────────────────────────────────────
  → SHA-256 of the signed manifest is computed
  → Sent to TSA (Time Stamping Authority)
  → TSA responds with a timestamp token: "this hash existed at 2026-11-09T14:21:58Z"
  → Token is added to the manifest

STEP 10: Attestation is added to the Merkle log
─────────────────────────────────────────────────
  → Manifest is serialized to bytes
  → Leaf hash computed: SHA-256(0x00 + manifest_bytes)
  → Leaf is appended to the in-memory Merkle tree
  → New root hash is computed
  → Merkle leaf index (position) and root hash added to manifest
  → System periodically signs the tree head

STEP 11: Everything is saved to PostgreSQL
────────────────────────────────────────────
  Attestation record saved containing:
    - Full manifest JSON
    - Ed25519 signature
    - Public key PEM
    - RFC 3161 timestamp token
    - Merkle leaf index
    - Verdict + fake_probability

  Job record updated:
    - status: "completed"
    - result_summary: {verdict, score, face_count, frames_analyzed}

STEP 12: You see the result
─────────────────────────────
  Your Jobs page auto-polls GET /jobs/{id} every 5 seconds
  → Status changes to "completed"
  → Verdict badge appears: "MANIPULATED" in red
  → You can click "Attestations" to see the signed proof

STEP 13: Anyone verifies independently
───────────────────────────────────────
  You share the attestation_id with a journalist/court/fact-checker
  They go to /verify (no login needed)
  They enter the attestation_id
  → System runs 7-step verification:
      1. Loads the manifest from DB
      2. Recomputes SHA-256 of claimed video bytes → match ✅
      3. Verifies Ed25519 signature using stored public key → valid ✅
      4. Checks certificate validity period → current ✅
      5. Checks revocation list → not revoked ✅
      6. Verifies RFC 3161 timestamp → consistent ✅
      7. Verifies Merkle inclusion proof → in log ✅
  → "All 7 checks passed. Verdict: LIKELY_MANIPULATED (87.0%)"
  → Disclaimer: "This AI gave a probabilistic opinion. Cryptography proves
    the system made this claim — not that the claim is correct."
```

---

## 8. File-by-File Explanation

### Backend Core

| File | Plain-English Role |
|------|-------------------|
| `backend/app/config.py` | All configuration in one place — database passwords, JWT secrets, file size limits, detection thresholds. Reads from environment variables so secrets are never hardcoded in source code. |
| `backend/app/main.py` | The entry point — creates the FastAPI app, registers all routes, and sets up startup behavior. Think of it as the "front door" of the server. |
| `backend/app/core/security.py` | Password hashing (Argon2id), JWT creation/verification, and constant-time comparison utilities. |
| `backend/app/core/rbac.py` | Defines what each user role (user/admin) is allowed to do. |
| `backend/app/core/database.py` | Opens the connection to PostgreSQL and provides a "session" (transaction) for each request. |
| `backend/app/core/deps.py` | "Dependencies" that FastAPI injects into route handlers — specifically `get_current_user()` which reads and validates the JWT from every authenticated request. |
| `backend/app/core/logging.py` | Structured JSON logging using `structlog`. Every log line is machine-parseable JSON for log aggregation systems. |

### Backend Services

| File | Plain-English Role |
|------|-------------------|
| `services/hashing.py` | SHA-256 exact fingerprinting + perceptual (fuzzy) hashing. Used to link a manifest to a specific video file. |
| `services/signer.py` | Ed25519 key management and signing. Supports three backends: local PEM files, SoftHSM, or HashiCorp Vault. |
| `services/manifest.py` | Builds the structured JSON "certificate" document and canonicalizes it for signing. |
| `services/merkle_log.py` | The in-memory Merkle tree. Append entries, generate inclusion proofs, sign tree heads. |
| `services/timestamp.py` | Sends hash to a TSA and gets back a time-stamped token. Can use local test TSA or real internet TSA. |
| `services/verifier.py` | Runs all 7 verification checks in sequence. The public verification algorithm. |
| `services/policy.py` | Converts a float score (0.0–1.0) to a verdict label. Single source of truth for threshold logic. |
| `services/revocation.py` | Maintains a signed list of revoked attestation IDs. |
| `services/sharing.py` | X25519 key exchange + HKDF + AES-256-GCM encryption for sharing attestations between users. |
| `services/anomaly.py` | Real-time anomaly detection using Isolation Forest + rule-based triggers (login failures, upload rate). |
| `services/video_io.py` | Video validation: checks magic bytes, file size, MIME type, and uses FFprobe to get video duration. |
| `services/face.py` | Interface for face detection (RetinaFace or MTCNN). Finds and crops faces from frames. |
| `services/detector.py` | Interface that loads the ensemble model and runs it on a list of face crops. |

### Backend API Routes

| File | Endpoints handled |
|------|-------------------|
| `api/auth.py` | Register, Login, Refresh token, Get current user |
| `api/upload.py` | Upload video, List videos, Delete video |
| `api/jobs.py` | List jobs, Get specific job status |
| `api/attestations.py` | List attestations, Get attestation detail, Download attestation package |
| `api/verify.py` | Verify by attestation ID, Verify by re-upload |
| `api/admin.py` | View signing key info, Revoke attestation, List anomaly events |
| `api/shares.py` | Create encrypted share, List shares, Get share detail |

### ML Models

| File | Plain-English Role |
|------|-------------------|
| `ml/models/efficientnet_b4.py` | Google's image classifier adapted to detect spatial deepfake artifacts in face crops. |
| `ml/models/frequency_cnn.py` | Custom CNN that works in the DCT frequency domain to find synthesis artifacts invisible to spatial models. |
| `ml/models/temporal_bigru.py` | Bidirectional RNN with attention that detects inconsistencies across a sequence of frames over time. |
| `ml/models/ensemble.py` | Combines the three models with learnable weights. Handles fallback when temporal model can't run. |
| `ml/train.py` | Training loop: Adam optimizer, AMP (mixed precision), cosine LR scheduling, early stopping, checkpoint saving. |
| `ml/evaluate.py` | Loads a model and runs it on a test set. Reports accuracy, AUC-ROC, precision, recall, F1, threshold sweep. |
| `ml/export.py` | Converts a trained model to ONNX or TorchScript format for deployment (faster inference, no Python overhead). |
| `ml/gradcam.py` | GradCAM (Gradient-weighted Class Activation Mapping) — creates a heatmap showing *which parts of the face* the model focused on when making its prediction. |
| `ml/datasets/loaders.py` | PyTorch Dataset classes for loading face crops and sequence features from FaceForensics++, Celeb-DF, and DFDC datasets. |
| `ml/anomaly/train_anomaly.py` | Trains a scikit-learn Isolation Forest on baseline traffic data for the usage anomaly detector. |

### Frontend Pages

| File | What you see |
|------|-------------|
| `pages/Login.jsx` | Simple email/password form. On success, stores JWT tokens and redirects to dashboard. |
| `pages/Register.jsx` | Account creation form. Auto-logs in after successful registration. |
| `pages/Dashboard.jsx` | 4 stat cards (videos, jobs, attestations, verify link) + recent jobs table. |
| `pages/UploadPage.jsx` | Drag-and-drop zone, file validation feedback, upload progress bar, automatic redirect to jobs on completion. |
| `pages/Jobs.jsx` | Table of all detection jobs with live status badges. Auto-polls every 5s when any job is pending/running. Click to expand full result detail. |
| `pages/Attestations.jsx` | Table of all signed attestations. Click to expand: verdict, stats, manifest JSON, signature, Merkle proof, download package button. |
| `pages/Verify.jsx` | Public page. Enter attestation ID, see 7-step verification result with pass/fail per check. No login required. |

### Infrastructure

| File | Plain-English Role |
|------|-------------------|
| `docker-compose.yml` | Defines all services (api, worker, frontend, db, redis, minio) and how they connect. One command starts everything. |
| `deploy/Dockerfile.api` | Instructions to build the Docker image for the FastAPI server. |
| `deploy/Dockerfile.worker` | Instructions for the Celery detection worker image (includes GPU support). |
| `deploy/Dockerfile.frontend` | Builds the React app and serves it via nginx. |
| `deploy/nginx.conf` | Reverse proxy config — routes `/api/` to FastAPI and everything else to the React app. |
| `alembic/` | Database migration files. Run `alembic upgrade head` to create or update all tables. |
| `.env.example` | Template showing every environment variable the system needs. Copy to `.env` and fill in secrets. |

### Scripts

| File | What it does |
|------|-------------|
| `scripts/seed_keys.py` | Generate Ed25519 keypairs for signing and TSA. Run once during setup. |
| `scripts/generate_ca.py` | Generate a self-signed demo Certificate Authority for local development. |
| `scripts/download_weights.py` | Download real model weights or generate random-initialized "mock" weights for testing. |
| `scripts/simulate_attack.py` | Demonstrate that replay attacks, manifest tampering, and nonce reuse are all blocked by the cryptographic system. |

---

## 9. The Honest Limitations

The system is designed to be honest about what it can and cannot do. This section is important to understand before presenting or using this project.

### What the cryptography DOES guarantee
- ✅ The analysis was performed by this specific system
- ✅ The analysis was performed on the exact video with this SHA-256 fingerprint
- ✅ The result has not been modified since it was signed
- ✅ The result was recorded at approximately this timestamp
- ✅ The result appears in the public Merkle log at this position

### What the cryptography CANNOT guarantee
- ❌ That the AI verdict is correct
- ❌ That the video is "authentic" (the absence of manipulation signals is not proof of authenticity)
- ❌ That a deepfake not seen during training will be detected
- ❌ That someone didn't submit a fake video and receive a "clean" attestation

### The "arms race" problem
Deepfake generators continuously improve. A detector trained on 2024-era deepfakes may not detect 2026-era deepfakes. This project acknowledges this explicitly in the verdicts — "LIKELY_MANIPULATED" and "NO_MANIPULATION_DETECTED" both contain hedging language.

### What INCONCLUSIVE really means
When the system returns INCONCLUSIVE, it means "our confidence is too low to make a claim either way." This is not a failure — it is correct behavior. Forcing a binary answer when confidence is low would produce false information.

---

## 10. Glossary — All Terms Defined Simply

| Term | Simple definition |
|------|-------------------|
| **AES-256-GCM** | A symmetric encryption algorithm. AES = the cipher, 256 = key size in bits (very strong), GCM = mode that also verifies integrity (no silent tampering). |
| **Alembic** | A Python tool for managing database schema changes over time (like version control for database structure). |
| **API** | Application Programming Interface — a set of URLs your code (or the browser) can call to make the server do things. |
| **Argon2id** | The recommended password hashing algorithm. Intentionally slow and memory-intensive to prevent bulk password cracking. |
| **Attestation** | A formal, signed record of an AI analysis result. The main output of this system. |
| **AUC-ROC** | Area Under the Receiver Operating Characteristic curve — a standard measure of a classifier's overall accuracy (1.0 = perfect, 0.5 = random guessing). |
| **BiGRU** | Bidirectional Gated Recurrent Unit — a neural network layer that processes sequences in both directions, capturing context from past AND future elements. |
| **Canonicalization** | Standardizing a document to a single exact representation before signing, so the signature works regardless of formatting differences. |
| **Celery** | A Python framework for running tasks asynchronously in background worker processes. |
| **CORS** | Cross-Origin Resource Sharing — a browser security feature that restricts which websites can call your API. |
| **DCT** | Discrete Cosine Transform — a mathematical operation that breaks a signal (like an image) into frequency components. |
| **Deepfake** | A synthetic video where a person's face is replaced or animated using AI. |
| **Docker** | A system for packaging software and all its dependencies into a "container" that runs identically on any computer. |
| **Domain separation** | Using different prefixes (0x00/0x01) when hashing leaves vs. nodes to prevent an attacker from crafting ambiguous inputs. |
| **Ed25519** | An elliptic curve digital signature algorithm. Fast, small signatures (64 bytes), and secure. |
| **Ensemble** | Multiple models whose outputs are combined, usually more accurate than any individual model. |
| **FFmpeg** | A powerful open-source tool for processing video files — extracting frames, converting formats, probing duration. |
| **FastAPI** | A modern Python web framework for building APIs. Automatically generates documentation. |
| **GradCAM** | A technique that shows *where* in an image a neural network focused when making a prediction, as a colored heatmap. |
| **HKDF** | HMAC-based Key Derivation Function — takes a shared secret and derives cryptographic keys of any desired length. |
| **Isolation Forest** | A machine learning algorithm for anomaly detection. Isolates outliers by randomly partitioning data. |
| **JWT** | JSON Web Token — a compact, signed token containing identity claims. Used for stateless authentication. |
| **Merkle tree** | A binary tree where each node's value is the hash of its children. The root hash summarizes all entries; any change to any entry changes the root. |
| **MinIO** | An open-source object storage server compatible with Amazon S3's API. Stores large binary files (videos). |
| **MTCNN / RetinaFace** | Face detection algorithms that locate and crop faces from video frames with high accuracy. |
| **Neural network** | A mathematical model loosely inspired by the brain, consisting of layers of interconnected "neurons" (mathematical functions). Learns patterns from examples. |
| **ONNX** | Open Neural Network Exchange — a standard format for exporting ML models so they run in any framework, not just PyTorch. |
| **pHash** | Perceptual hash — a "fuzzy fingerprint" that stays similar for visually similar images, unlike cryptographic hashes which change completely. |
| **PostgreSQL** | A powerful open-source relational database. Stores structured data in tables with relationships between them. |
| **Private key** | The secret half of a key pair. Used to create digital signatures. Must never be shared. |
| **Public key** | The shareable half of a key pair. Anyone can use it to verify signatures made with the corresponding private key. |
| **RBAC** | Role-Based Access Control — users have roles (user/admin), and each API endpoint checks whether your role permits access. |
| **React** | A JavaScript library for building user interfaces from reusable "components." |
| **Redis** | An in-memory database used here as a message broker for the Celery job queue. Extremely fast. |
| **RFC** | Request for Comments — the document format used to define internet standards (HTTP, TLS, timestamps, etc.). |
| **RFC 3161** | The internet standard for trusted timestamping — proves a document existed at a specific time. |
| **RFC 6962** | The Certificate Transparency standard that defined Merkle transparency logs. |
| **RFC 8785** | The JSON Canonicalization Scheme — a standard way to normalize JSON before signing. |
| **SHA-256** | Secure Hash Algorithm producing a 256-bit (64 character) fingerprint. Changing one bit of input completely changes the output. |
| **Signed Tree Head (STH)** | A signed commitment to the current state of a Merkle log — the root hash + number of entries + timestamp, all signed. |
| **SQLAlchemy** | A Python ORM (Object-Relational Mapper) — lets you work with database tables as Python objects. |
| **TorchScript** | PyTorch's format for exporting models to run without Python — faster inference in production. |
| **TSA** | Time Stamping Authority — a trusted third-party service that provides RFC 3161 timestamps. |
| **Uvicorn** | An ASGI (Async Server Gateway Interface) web server that runs FastAPI applications. |
| **Vite** | A build tool for frontend JavaScript — fast development server and production bundler. |
| **X25519** | A Diffie-Hellman key exchange algorithm using the Curve25519 elliptic curve. Allows two parties to derive a shared secret without exchanging it directly. |
