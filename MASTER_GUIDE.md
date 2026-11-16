# DeepAuth — The Complete Master Guide

> **Who this is for:** Anyone. No background in AI, security, or programming required.
> Every concept is explained from scratch. Every component has: **what it is → why it exists → what it does → its role in the project**.

---

## Table of Contents

1. [The Problem: Why Does This Project Exist?](#1-the-problem-why-does-this-project-exist)
2. [The Solution in One Page](#2-the-solution-in-one-page)
3. [The Complete Flow — From Upload to Certificate](#3-the-complete-flow--from-upload-to-certificate)
4. [Layer 1: Detecting Deepfakes (The AI Brain)](#4-layer-1-detecting-deepfakes-the-ai-brain)
   - [What is a Deepfake?](#what-is-a-deepfake)
   - [Model 1 — EfficientNet-B4 (The Eye)](#model-1--efficientnet-b4-the-eye)
   - [Model 2 — FrequencyCNN (The Ear for Noise)](#model-2--frequencycnn-the-ear-for-noise)
   - [Model 3 — TemporalBiGRU (The Motion Detective)](#model-3--temporalbigru-the-motion-detective)
   - [The Ensemble — The Jury of Three](#the-ensemble--the-jury-of-three)
   - [The Policy Engine — The Judge](#the-policy-engine--the-judge)
5. [Layer 2: Proving It Cryptographically (The Notary)](#5-layer-2-proving-it-cryptographically-the-notary)
   - [Hashing — The Video's Fingerprint](#hashing--the-videos-fingerprint)
   - [Digital Signature (Ed25519) — The Official Stamp](#digital-signature-ed25519--the-official-stamp)
   - [RFC 3161 Timestamp — Proof of When](#rfc-3161-timestamp--proof-of-when)
   - [Merkle Tree — The Public Audit Log](#merkle-tree--the-public-audit-log)
   - [The Attestation — The Final Certificate](#the-attestation--the-final-certificate)
   - [Verification — Anyone Can Check](#verification--anyone-can-check)
6. [Layer 3: The Web Application (The Interface)](#6-layer-3-the-web-application-the-interface)
   - [Backend API (FastAPI)](#backend-api-fastapi)
   - [Database (PostgreSQL / SQLite)](#database-postgresql--sqlite)
   - [Job Queue (Celery + Redis)](#job-queue-celery--redis)
   - [File Storage (MinIO)](#file-storage-minio)
   - [Frontend (React)](#frontend-react)
7. [Security Guards — Protecting the System](#7-security-guards--protecting-the-system)
8. [Every File, Explained](#8-every-file-explained)
9. [How It's Built & Run](#9-how-its-built--run)
10. [What This System Cannot Do (Honest Limits)](#10-what-this-system-cannot-do-honest-limits)
11. [Glossary — Every Term, Simply](#11-glossary--every-term-simply)

---

## 1. The Problem: Why Does This Project Exist?

### The world has a deepfake crisis

A **deepfake** is a video where someone's face has been synthetically replaced or animated by AI. Modern deepfakes are so convincing that the human eye genuinely cannot tell the difference.

This creates serious real-world dangers:

| Scenario | Why it's dangerous |
|---|---|
| A politician's face swapped onto a fake speech | Voters believe false statements were made |
| A person's face in a fake crime video | Fabricated evidence in court |
| A CEO's face in a fake announcement | Stock market manipulation |
| A person in a fake adult video | Reputation destruction, blackmail |

### The two problems that exist today

**Problem A — Detection is hard and inconsistent:**
No single AI tool reliably detects all deepfakes. Different fakes leave different kinds of traces, and no one detector catches everything.

**Problem B — Even if detection works, you can't trust the result:**
Imagine an AI tool says "this video is fake." How do you know:
- The AI analyzed *this exact video* (not a different one)?
- The result hasn't been changed after the fact?
- The analysis happened *when* they claim (not backdated)?
- It really came from *this* system (not fabricated)?

Without answers to these questions, the AI verdict is just an unverifiable claim.

### What DeepAuth solves

DeepAuth combines **two things nobody else combines**:

```
   AI Detection          +        Cryptographic Proof
   ─────────────                 ───────────────────────
   "This video is                "And here is a tamper-proof
    87% likely fake"              certificate proving we said this,
                                  about this exact video,
                                  at this exact time"
```

The AI gives an opinion. The cryptography makes it **verifiable and unforgeable**.

---

## 2. The Solution in One Page

Here's the entire system explained in one visual:

```
                        YOU
                         │
              Upload a video file
                         │
                         ▼
        ┌────────────────────────────────────┐
        │          STEP 1: INTAKE            │
        │  • Check file is a real video      │
        │  • Compute SHA-256 fingerprint     │
        │  • Store file securely             │
        │  • Queue analysis job              │
        └────────────────┬───────────────────┘
                         │
                         ▼
        ┌────────────────────────────────────┐
        │       STEP 2: FACE EXTRACTION      │
        │  • Extract frames from the video   │
        │  • Detect and crop human faces     │
        │  • Track one face consistently     │
        └────────────────┬───────────────────┘
                         │
                         ▼
        ┌────────────────────────────────────┐
        │       STEP 3: AI ANALYSIS          │
        │                                    │
        │  ┌──────────┐  ┌──────────┐  ┌──────────┐
        │  │ Model 1  │  │ Model 2  │  │ Model 3  │
        │  │ Spatial  │  │Frequency │  │ Temporal │
        │  │  "Eye"   │  │  "Ear"   │  │"Motion"  │
        │  └────┬─────┘  └────┬─────┘  └────┬─────┘
        │       └─────────────┼──────────────┘
        │                     ▼
        │            ┌──────────────┐
        │            │   ENSEMBLE   │  ← Weighted combination
        │            │  Score: 0.87 │    of all three opinions
        │            └──────┬───────┘
        │                   ▼
        │            ┌──────────────┐
        │            │    POLICY    │  ← Convert score to verdict
        │            │   ENGINE     │
        │            └──────┬───────┘
        └───────────────────┼────────────────────┘
                            │
                    "LIKELY_MANIPULATED (87%)"
                            │
                            ▼
        ┌────────────────────────────────────┐
        │     STEP 4: CRYPTOGRAPHIC PROOF    │
        │                                    │
        │  Build Manifest (the document):    │
        │  - SHA-256 of video                │
        │  - Score, verdict, models used     │
        │  - Timestamps, user info           │
        │                                    │
        │  Sign it (Ed25519 digital stamp)   │
        │  Add timestamp (RFC 3161)          │
        │  Add to public log (Merkle tree)   │
        └────────────────┬───────────────────┘
                         │
                         ▼
        ┌────────────────────────────────────┐
        │     STEP 5: ATTESTATION STORED     │
        │  Anyone can verify it:             │
        │  • Was it this exact video?    ✅  │
        │  • Is signature valid?         ✅  │
        │  • Is timestamp authentic?     ✅  │
        │  • Is it in the public log?    ✅  │
        └────────────────────────────────────┘
```

---

## 3. The Complete Flow — From Upload to Certificate

Let's walk through the life of one video submission, step by step, in plain English.

---

### Step 0 — A user logs in

The user creates an account with an email and password. The password is hashed (scrambled mathematically) and stored. When they log in, they receive a **JWT token** — a small signed pass that proves "this is me" on every subsequent request.

> **Why JWT?** The server doesn't need to look up a session in the database every time. The JWT itself contains who you are, cryptographically signed by the server. If it verifies, you're authenticated.

---

### Step 1 — Video upload

The user drags a video file into the browser. The frontend:
1. Validates the file type and size (MP4, WebM, MOV; max 200 MB)
2. Sends it to the backend API over HTTPS

The backend:
1. Reads the file's "magic bytes" (first few bytes) to verify it's really a video — not a renamed `.exe`
2. Computes the **SHA-256 fingerprint** of the raw video bytes
3. Stores the file in MinIO (like a private S3 bucket)
4. Creates a database record with status `PENDING`
5. Pushes a job to the **Celery queue** (a task waiting room)

---

### Step 2 — Frame extraction & face detection

A background **worker** picks up the job and:

1. Extracts video frames using FFmpeg (every Nth frame, up to 300 frames)
2. Runs a face detector (Haar cascade) on each frame to find faces
3. If no face is found in any frame → verdict is immediately `INCONCLUSIVE: NO_FACE_DETECTED`
4. If a face is found, it uses **centroid tracking**: in frame 0, pick the biggest face. In every subsequent frame, follow the face closest to where the previous face was. This prevents "identity jumping" in multi-person videos.
5. Crops and resizes each face to 380×380 pixels (the input size EfficientNet expects)

---

### Step 3 — AI analysis (three models)

The ensemble runs all three models on the extracted face crops:

**Model 1 (EfficientNet-B4)** analyzes each frame independently for spatial artifacts.
**Model 2 (FrequencyCNN)** analyzes each frame's frequency spectrum.
**Model 3 (TemporalBiGRU)** analyzes the *sequence* of frame features over time.

Each model outputs a score from 0.0 (definitely real) to 1.0 (definitely fake).

The ensemble combines them with calibrated weights into one final score. The policy engine maps that score to a verdict:
- Score < 0.38 → `NO_MANIPULATION_DETECTED`
- Score 0.38–0.58 → `INCONCLUSIVE`
- Score > 0.58 → `LIKELY_MANIPULATED`

---

### Step 4 — Build the manifest

The system builds a **manifest** — a structured JSON document containing:
- The SHA-256 of the video
- The perceptual hash of the faces
- Each model's individual score
- The ensemble score and verdict
- Which model weights were used (and their SHA-256 hashes)
- Who submitted the video and when
- Policy thresholds used

This document is **canonicalized** (formatted in a single standard way, removing all spaces, sorting all keys) so the signature always covers exactly the same bytes.

---

### Step 5 — Cryptographic sealing

Three things happen in sequence:

1. **Ed25519 signature** — the manifest is signed with the system's private key. The signature proves the manifest is genuine and unchanged.
2. **RFC 3161 timestamp** — the signature hash is sent to a Time Stamping Authority, which returns a signed token proving "this signature existed at this exact time."
3. **Merkle inclusion** — the manifest hash is appended to an immutable Merkle tree. An inclusion proof is generated that proves "this entry is in the log."

All three are attached to the manifest, forming the **attestation certificate**.

---

### Step 6 — Stored and viewable

The attestation is stored in the database and shown on the frontend. The user can:
- View the full manifest, scores, verdict, and signature
- Download the full attestation package (manifest + signature + timestamp token)
- Share it with a one-time public link

---

### Step 7 — Anyone verifies

Any third party can:
1. Enter the attestation ID on the public `/verify` page
2. Optionally re-upload the same video

The system runs 7 checks:
1. Load manifest from database ✅
2. Recompute SHA-256 of claimed video bytes → must match ✅
3. Verify Ed25519 signature using stored public key → must be valid ✅
4. Check certificate validity period → must be current ✅
5. Check revocation list → must not be revoked ✅
6. Verify RFC 3161 timestamp token → must be consistent ✅
7. Verify Merkle inclusion proof → must be in the log ✅

If all 7 pass: **the attestation is genuine, the result was produced by this system, about this exact video, at the claimed time, and nothing has changed since.**

---

## 4. Layer 1: Detecting Deepfakes (The AI Brain)

### What is a Deepfake?

A deepfake is created by training an AI "generator" on thousands of videos of a real person. The generator learns to synthesize a face so convincingly that it can replace any face in any video.

**The cat-and-mouse game:** Deepfake generators keep improving. Detectors need to find the "tells" generators leave behind — tiny clues invisible to humans but detectable by AI. This project uses three detectors because each specializes in a different kind of tell.

---

### Model 1 — EfficientNet-B4 (The Eye)

**File:** `ml/models/efficientnet_b4.py` | **Weights:** `weights/spatial.pt` (~68 MB)

#### What it is
EfficientNet-B4 is an image classification neural network created by Google in 2019. It was originally trained to recognize everyday objects (cats, cars, chairs) in photos. Here, it's **fine-tuned** — its final layer is replaced and it's retrained to classify faces as real or fake.

#### Why this model specifically
- EfficientNet-B4 has 32 million learned parameters — large enough to be powerful
- It achieves the best accuracy-per-computation tradeoff of all standard classifiers
- Pre-training on ImageNet gives it a head start: it already understands textures, edges, and shapes

#### What it looks for (Spatial artifacts)
- Blurring or smearing at the face's edges (hairline, jaw, ears)
- Skin texture that's too smooth or too uniform (AI generators often miss natural skin pores)
- Unnatural eye reflections (the shape of light reflected in both eyes should be consistent; deepfakes often aren't)
- Warping artifacts around the nose and mouth from the face-swap decoder

#### How it works, step by step
1. A face crop (380×380 pixels, 3 color channels) is fed into the network
2. The image passes through ~32 million mathematical operations (multiply, add, apply activation function) across the network's layers
3. The final layer outputs one number: probability this face is fake (0.0 to 1.0)
4. This is repeated for each extracted frame; the per-frame scores are averaged

#### Analogy
> A forensic art expert examining a painting under a magnifying glass for brush-stroke inconsistencies — looking at the visual canvas frame by frame.

---

### Model 2 — FrequencyCNN (The Ear for Noise)

**File:** `ml/models/frequency_cnn.py` | **Weights:** `weights/frequency.pt` (~6 MB)

#### What it is
A custom-built Convolutional Neural Network (CNN) that operates on the **frequency domain** of images rather than the pixel domain.

#### Background: What is frequency in an image?
Every digital image can be mathematically decomposed into "frequency components" — patterns of variation from slow (smooth gradients) to fast (sharp edges, fine textures). This is done using the **DCT (Discrete Cosine Transform)** — the same math used in JPEG compression.

**Key insight:** Real cameras produce natural, characteristic noise patterns in the high-frequency range. AI deepfake generators synthesize images at the pixel level, which creates artificial repeating patterns in the frequency domain — invisible to the eye but mathematically distinct.

#### Why this model exists
Some deepfakes are spatially perfect — they fool Model 1 entirely. But even a perfect-looking deepfake still has frequency artifacts from the generator's upsampling layers (a mathematical side effect). This model catches what the eye model misses.

#### How it works
1. Face crop is converted to grayscale
2. DCT is applied to 8×8 blocks (like JPEG encoding, but no compression)
3. The resulting frequency map (which parts are "loud" vs. "quiet") is fed into a 5-layer CNN
4. The CNN outputs one number: probability this face is fake

#### Analogy
> A musician who can hear that a recording was digitally processed or auto-tuned, even when it sounds perfect to a non-expert ear. They hear patterns the casual listener can't.

---

### Model 3 — TemporalBiGRU (The Motion Detective)

**File:** `ml/models/temporal_bigru.py` | **Weights:** `weights/temporal.pt` (~11.5 MB)

#### What it is
A **Recurrent Neural Network (RNN)** — specifically a Bidirectional GRU (Gated Recurrent Unit) — that analyzes sequences of frames over time, rather than individual frames.

#### Breaking down the name
| Part | Meaning |
|---|---|
| **Temporal** | Deals with time — analyzes frames in sequence |
| **Bi** | Bidirectional — reads the sequence forwards AND backwards |
| **GRU** | Gated Recurrent Unit — a type of "memory" that retains important information across the sequence |

#### Why this model exists
A deepfake might look perfect in every individual frame. But across frames, the AI generator can't always maintain perfect consistency. Inter-frame flickering, unnatural blinking, inconsistent lighting, and mouth-movement jitter (especially in lip-sync fakes like Wav2Lip) create temporal inconsistencies that only appear when you look at multiple frames together.

#### How it works
1. For each frame, the EfficientNet-B4 backbone extracts a **feature vector** — a list of 1792 numbers that describes the face (a "compressed representation" of the visual information)
2. All frame feature vectors are fed as a sequence into the BiGRU
3. The BiGRU reads forwards AND backwards through time (bidirectional), building an understanding of "what changed between this frame and all others"
4. An **attention mechanism** highlights which frames were most suspicious (which ones contributed most to the final score)
5. Output: one probability score for the whole video sequence

#### Why bidirectional?
If frame 47 has a subtle facial flicker, it looks suspicious in context of both frame 46 AND frame 48. Reading in both directions catches the anomaly from both sides.

#### Analogy
> A film editor who notices that the main actor's face looks subtly different between cuts — a kind of inconsistency that only becomes obvious when you play the whole sequence, not when you pause on any single frame.

---

### The Ensemble — The Jury of Three

**File:** `ml/models/ensemble.py`

#### What it is
A thin "meta-model" that runs all three models and combines their outputs into one final score using calibrated weights.

#### Why not just use one model?
Each model has blind spots:
- A deepfake that perfectly fools the spatial model might still have frequency artifacts
- A static deepfake image (no motion) trivially bypasses the temporal model
- An ensemble is harder to fool — you'd need to simultaneously beat all three detectors

#### How the combining works

The ensemble uses a **conditional weighting formula** based on what each model found:

```
If temporal model detects strong motion anomaly (T > 0.50):
    Final = 50% Temporal + 25% Spatial-top-frames + 25% Frequency-top-frames

If spatial model sees severe visual manipulation (S > 0.50):
    Final = 45% Spatial + 30% Spatial-top-frames + 25% Frequency

If all models suggest authentic footage (S < 0.36 and T < 0.25):
    Final = 40% Temporal + 40% Spatial + 20% Frequency

Otherwise (balanced case):
    Final = 40% Spatial + 35% Temporal + 25% Frequency
```

The "top frames" scores are the averages from the worst one-third of frames — the most suspicious moments in the video.

#### Fallback
If the temporal model can't run (fewer than 3 faces detected, video too short), the ensemble falls back to a 50/50 average of Spatial and Frequency.

#### Analogy
> A panel of three judges: a visual art expert, a sound engineer, and a film historian. Each gives a score. A wise moderator combines their opinions, giving more weight to whoever's area is most relevant to the specific evidence in front of them.

---

### The Policy Engine — The Judge

**File:** `backend/app/services/policy.py`

#### What it is
A simple function that converts the ensemble's raw score (0.0–1.0) into a human-readable verdict.

#### The three verdicts

| Score range | Verdict | Meaning |
|---|---|---|
| Score < 0.38 | `NO_MANIPULATION_DETECTED` | Strong evidence of authenticity — the AI found no manipulation signals |
| 0.38 ≤ Score ≤ 0.58 | `INCONCLUSIVE` | The AI is uncertain — human review recommended |
| Score > 0.58 | `LIKELY_MANIPULATED` | Strong evidence of manipulation |

#### Special cases
- **No face detected** → Always `INCONCLUSIVE: NO_FACE_DETECTED` (can't analyze what isn't there)
- **Video under 2 seconds** → Always `INCONCLUSIVE: TOO_SHORT` (not enough data)

#### Why a gray zone?
A score of 0.5 is genuine uncertainty. It would be dishonest to call that either "clean" or "fake." The 20-point gray zone forces honest uncertainty — if the models disagree or are unsure, say so explicitly.

#### Why "LIKELY" in the verdict?
The system is intentionally humble. It says "likely manipulated," not "definitely manipulated." An AI detector gives a probabilistic opinion, not a legal verdict. This distinction is critical.

---

## 5. Layer 2: Proving It Cryptographically (The Notary)

### Why This Layer Exists

Imagine a court case where the prosecution says "our AI analyzed the video and said it's fake." The defense asks:
- How do we know your AI analyzed *this* video, not a different one?
- How do we know the result wasn't changed after the fact?
- How do we know the analysis happened when you say it did?

Without cryptographic proof, these questions can't be answered. This layer answers all of them.

---

### Hashing — The Video's Fingerprint

**File:** `backend/app/services/hashing.py`

#### What hashing is
A **hash function** takes any input (a file, text, anything) and produces a fixed-length output called a **digest** or **fingerprint**. The key property: **if even one bit of the input changes, the output completely changes.**

#### SHA-256 specifically
SHA-256 (Secure Hash Algorithm, 256-bit output) produces a 64-character hex string like:
```
a3f5b8c92e4d1f7a6b3c8e9f...
```
It is computationally impossible to find two different files with the same SHA-256 (this is called "collision resistance").

#### How it's used
1. When a video is uploaded, its SHA-256 is computed and stored in the manifest
2. When someone verifies later, they submit the same video and the system recomputes its SHA-256
3. If the hashes match → same exact video bytes, nothing changed
4. If they don't match → the video was modified (even a single pixel change fails verification)

#### Perceptual hash (pHash)
Problem: If a video is re-encoded (same content, different compression), its SHA-256 changes. Solution: a **perceptual hash (pHash)** — a "fuzzy fingerprint" that stays similar for visually identical content and differs for visually different content.

The manifest contains both: SHA-256 for exact matching and pHash for fuzzy matching.

#### Analogy
> SHA-256 is like a person's DNA — unique and absolutely exact, one mutation changes everything. pHash is like a physical description — still identifies the same person even after a haircut.

---

### Digital Signature (Ed25519) — The Official Stamp

**File:** `backend/app/services/signer.py`

#### What digital signatures are
A digital signature is a mathematical system using two related numbers:
- **Private key** (secret): used to *create* signatures. Only the system holds this.
- **Public key** (shared): used by anyone to *verify* signatures.

A signature on a document proves:
1. The document was signed by whoever holds the private key
2. The document has not been changed since it was signed (even one character change breaks the signature)

#### Ed25519 specifically
Ed25519 is an elliptic curve signature algorithm. It:
- Uses mathematical operations on a 25519-bit elliptic curve
- Produces 64-byte signatures (compact)
- Is extremely fast (thousands of signatures per second)
- Is resistant to all known attacks

#### How it's used in this project
1. The manifest (the full analysis document) is converted to canonical JSON bytes
2. Ed25519 signs those bytes using the system's private key
3. The signature (64 bytes, stored as hex) is attached to the manifest
4. Anyone with the public key can verify: "these bytes were signed by this system and haven't changed"

#### Key management
The private key is stored in `keys/signing_private.pem` with file permissions `chmod 600` (readable only by the owner). It's in `.gitignore` and never committed to version control. In production, it would be stored in a Hardware Security Module (HSM) or a secrets vault.

#### Analogy
> A wax seal on a medieval letter. Breaking the seal proves tampering. Here, the "seal" is a 64-byte mathematical fingerprint that cannot be faked without the private key.

---

### RFC 3161 Timestamp — Proof of When

**File:** `backend/app/services/timestamp.py`

#### The problem without timestamps
Without a trusted timestamp, someone could:
- Analyze a video today and claim they analyzed it last year
- Backdate analysis results after the fact
- Create attestations about events that haven't happened yet

#### What RFC 3161 is
RFC 3161 is an internet standard (defined in a Request for Comments document, hence "RFC") for trusted timestamping. It works like this:

1. The system sends the **hash of the signature** to a **Time Stamping Authority (TSA)** — a trusted third-party server
2. The TSA records "I received this hash at this exact time" and signs it with its own private key
3. The TSA returns a **timestamp token** — a certificate proving when the hash existed

#### Why send the hash of the signature (not the whole document)?
Privacy and efficiency. The TSA doesn't need to see the actual document — just its fingerprint. This proves "this exact document existed at this time" without revealing what the document says.

#### How it's used
The timestamp token is embedded in the attestation. During verification, the system checks that the token was issued by a known TSA, is validly signed by the TSA, and corresponds to the correct hash.

#### Analogy
> A postal postmark. When you mail a letter, the postmark proves when and where it was mailed — the postal service (a trusted authority) stamped it. You can't forge a postmark after the fact.

---

### Merkle Tree — The Public Audit Log

**File:** `backend/app/services/merkle_log.py`

#### The problem without an audit log
Even with signatures and timestamps, someone could quietly delete an attestation or secretly create a new one with an earlier date. An independent, append-only public log makes this impossible.

#### What a Merkle tree is
A Merkle tree is a data structure where:
- Every **leaf** is the hash of one entry (one manifest)
- Every **internal node** is the hash of its two children
- The **root** is a single hash that summarizes *all* entries

**Critical property:** Changing any entry completely changes the root. And the root is published (signed, timestamped, and distributed) so anyone can detect retroactive changes.

```
                    ROOT
                   /    \
                 N3      N4
                / \      / \
              H1  H2   H3  H4
              │   │    │    │
            M1   M2   M3   M4   ← Manifest hashes (leaves)
```

#### Inclusion proofs
For any entry, the system can generate an **inclusion proof** — the minimal set of hashes needed to verify "this entry is in the tree." Anyone with the manifest hash and the proof can verify inclusion without downloading all other entries.

#### How it's used
1. After signing and timestamping, the manifest hash is appended to the in-memory Merkle tree
2. An inclusion proof is generated and attached to the attestation
3. During verification, the proof is replayed to confirm the manifest is genuinely in the log

#### Real-world analog
This is based on **Certificate Transparency (RFC 6962)** — the standard that makes TLS certificates publicly auditable. This project implements the same concept for analysis attestations.

#### Analogy
> A public notary book. Every notarized document is logged in a sequential book. The book is published and cannot be altered retroactively — adding entry 100 doesn't change entries 1–99. And anyone can prove "my document is in this book" without revealing every other document in the book.

---

### The Attestation — The Final Certificate

**File:** `backend/app/services/manifest.py`

#### What it is
The attestation is the **complete signed certificate** — a JSON document containing every piece of evidence:

```json
{
  "schema_version": "1.0",
  "manifest_id": "uuid...",
  "created_at": "2026-11-15T12:34:56Z",
  
  "content": {
    "sha256": "a3f5b8c9...",        ← Video fingerprint
    "phash": ["hex...", "hex..."],  ← Perceptual fingerprints
    "filename": "video.mp4"
  },
  
  "detection": {
    "verdict": "LIKELY_MANIPULATED",
    "ensemble_score": 0.87,
    "spatial_score": 0.92,
    "frequency_score": 0.39,
    "temporal_score": 1.00,
    "face_count": 42,
    "frames_analyzed": 150
  },
  
  "models": {
    "spatial": {
      "version": "1.0.0",
      "weight_sha256": "..."         ← Hash of the model weights file
    },
    ...
  },
  
  "policy": {
    "manipulated_threshold": 0.58,
    "clean_threshold": 0.38
  },
  
  "signature": {
    "algorithm": "Ed25519",
    "value": "hex...",               ← The digital signature
    "public_key_pem": "..."          ← Anyone can use this to verify
  },
  
  "timestamp": {
    "tsa_response_b64": "..."        ← RFC 3161 token (base64)
  },
  
  "merkle": {
    "leaf_hash": "hex...",
    "proof": ["hex...", "hex..."],   ← Inclusion proof
    "root": "hex..."
  }
}
```

This one document is self-contained. Anyone who downloads it has everything needed to independently verify every claim it makes.

---

### Verification — Anyone Can Check

**File:** `backend/app/services/verifier.py`

The public `/verify` endpoint runs 7 sequential checks:

| Check # | What it does | What it proves |
|---|---|---|
| 1 | Load manifest from database | The attestation exists |
| 2 | Recompute SHA-256 of submitted video | Same exact video was analyzed |
| 3 | Verify Ed25519 signature | Manifest is genuine and unaltered |
| 4 | Check certificate validity period | Certificate hasn't expired |
| 5 | Check revocation list | Certificate hasn't been revoked |
| 6 | Verify RFC 3161 timestamp | Timestamp is authentic |
| 7 | Verify Merkle inclusion proof | Entry is genuinely in the log |

If all 7 pass, verification is complete. The system then returns the verdict: "LIKELY_MANIPULATED at 87%."

**Important disclaimer** (always shown): "This AI gave a probabilistic opinion. The cryptography proves this system made this claim about this exact video at this exact time — not that the AI is correct."

---

## 6. Layer 3: The Web Application (The Interface)

### Backend API (FastAPI)

**Directory:** `backend/app/`

#### What it is
FastAPI is a Python web framework for building APIs — the server-side code that handles requests from the browser and responds with data.

#### Why FastAPI
- Automatically generates interactive API documentation (available at `localhost:8000/docs`)
- Natively async — can handle many simultaneous requests without blocking
- Built-in request validation, authentication helpers, and dependency injection
- Fast: near Node.js speeds due to Python's asyncio

#### Key endpoints

| URL | What it does | Who can call it |
|---|---|---|
| `POST /auth/register` | Create a new account | Anyone |
| `POST /auth/login` | Log in, receive JWT tokens | Anyone |
| `GET /auth/me` | View your own profile | Logged-in users |
| `POST /videos/` | Upload a video | Logged-in users |
| `GET /jobs/{id}` | Check analysis status | Job owner |
| `GET /attestations/{id}` | View attestation certificate | Attestation owner |
| `POST /verify/` | Verify any attestation | Anyone (public) |
| `GET /health` | Is the server up? | Anyone |
| `GET /admin/keys` | View current signing key | Admins only |

---

### Database (PostgreSQL / SQLite)

**Directory:** `alembic/` (migrations) | **Library:** SQLAlchemy

#### What it is
A relational database — data stored in tables with relationships between them. PostgreSQL is used in production; SQLite (file-based) is used in tests.

#### Why a database
The system needs to persist:
- User accounts
- Uploaded video records
- Analysis job states and results
- Attestation certificates and their cryptographic components
- Anomaly events
- Revocation records

#### Database tables (the schema)

| Table | What's stored |
|---|---|
| `users` | email, password hash, role, created_at |
| `videos` | filename, SHA-256, pHash, storage path, uploader |
| `jobs` | video_id, status, started_at, completed_at |
| `job_results` | job_id, all scores, verdict, models used |
| `attestations` | job_id, manifest JSON, signature, timestamp, Merkle proof |
| `anomaly_events` | type, severity, details, timestamp |
| `revocations` | attestation_id, reason, revoked_at, revoked_by |
| `shares` | attestation_id, encrypted share token, expiry |

#### Migrations (Alembic)
When the database schema changes (new column added, table renamed), Alembic generates a **migration file** — a Python script that transforms the database from the old schema to the new one. `alembic upgrade head` applies all pending migrations.

---

### Job Queue (Celery + Redis)

**Workers:** `backend/app/workers/`

#### The problem
Video analysis takes 10–60 seconds. If the HTTP request had to wait that long for a response, the browser connection would time out and the user would see an error.

#### The solution: async job queue
When a video is uploaded:
1. The API immediately returns a **job ID** (HTTP 202 Accepted) — in under 1 second
2. The analysis job is pushed to a **Redis queue** (a fast in-memory list of pending tasks)
3. A **Celery worker** (a separate process) picks up the job and runs the analysis
4. The user polls `GET /jobs/{id}` every 5 seconds until the job is done

#### Components
- **Redis**: An extremely fast in-memory database used as a "message broker" — a waiting room for tasks
- **Celery**: A Python framework that runs tasks in background worker processes, consuming from the Redis queue

#### Analogy
> A restaurant kitchen. When you order (upload video), the waiter immediately says "Order received!" (job ID returned). Your order goes to the kitchen queue. The chef (worker) cooks your food. The waiter checks every few minutes if your order is ready.

---

### File Storage (MinIO)

**Service:** MinIO S3-compatible object store

#### What it is
MinIO is an open-source file storage server that uses Amazon S3's API. It stores large binary files (videos).

#### Why not store videos in the database?
Databases are optimized for structured data (rows and columns), not large binary files. Storing a 200 MB video in a PostgreSQL row would be extremely inefficient and slow. Object stores (MinIO, S3) are purpose-built for large file storage.

#### How it works
- Videos are uploaded → stored in a MinIO "bucket" (like a folder)
- The database stores only the path/URL to the file
- When analysis starts, the worker reads the file from MinIO

---

### Frontend (React)

**Directory:** `frontend/src/`

#### What it is
React is a JavaScript library for building interactive web interfaces. The frontend is the web pages you see in the browser.

#### How it's built
- **React 18**: The core UI library (components, state management)
- **Vite**: The build tool (packages all JS/CSS for production)
- **Tailwind CSS**: Utility-first CSS framework (styling classes like `bg-blue-500`, `flex`, `rounded-lg`)
- **Lucide React**: Icon library

#### Pages

| Page | What you see |
|---|---|
| `Login.jsx` | Email + password form. Stores JWT tokens on success. |
| `Register.jsx` | Account creation form. Auto-logs in after registration. |
| `Dashboard.jsx` | Stats overview: total videos, jobs, attestations + recent jobs table |
| `UploadPage.jsx` | Drag-and-drop video zone, file validation feedback, upload progress bar |
| `Jobs.jsx` | Table of all analysis jobs with live status. Auto-polls every 5 seconds. Click to expand full results. |
| `Attestations.jsx` | Table of all attestations. Click to expand: verdict, scores, full manifest JSON, signature, download button. |
| `Verify.jsx` | Public page — enter attestation ID, see 7-step verification results. No login needed. |

---

## 7. Security Guards — Protecting the System

### Authentication (JWT)

**File:** `backend/app/core/security.py`, `backend/app/core/deps.py`

Every protected API endpoint requires a **JWT (JSON Web Token)** in the Authorization header:
```
Authorization: Bearer eyJhbGc...
```

The JWT contains who you are (your user ID, role, expiry time) and is signed by the server. No database lookup needed to authenticate — if the signature verifies, you're in.

**Argon2id password hashing:** Passwords are never stored in plain text. Argon2id intentionally runs slowly (takes ~300ms) to prevent bulk password cracking. Even if the database is stolen, cracking passwords is computationally infeasible.

---

### Role-Based Access Control (RBAC)

**File:** `backend/app/core/rbac.py`

Two roles:
- **user**: Can upload videos, view their own jobs/attestations, verify any attestation
- **admin**: Everything a user can do, plus: view signing key info, revoke attestations, view anomaly events

Admin-only endpoints return HTTP 403 Forbidden if a regular user tries to access them.

---

### Anomaly Detection

**File:** `backend/app/services/anomaly.py`, `ml/anomaly/train_anomaly.py`

An Isolation Forest model monitors access patterns in real time and flags suspicious behavior:
- More than 5 failed login attempts in 10 minutes → alert
- More than 10 uploads in 1 hour from one user → alert
- More than 100 API calls in 1 minute from one IP → alert

The Isolation Forest is trained on baseline "normal" traffic patterns. When a new access pattern is an outlier (statistically unusual), it triggers an alert.

---

### Attack Simulation (Demo)

**File:** `scripts/simulate_attack.py`

This script demonstrates that the cryptographic system blocks three attack categories:

| Attack type | What an attacker tries | Why it's blocked |
|---|---|---|
| **Replay attack** | Re-submit an old attestation and claim it's fresh | The manifest contains a unique nonce and timestamp; replaying it fails verification |
| **Manifest tampering** | Modify the verdict in a stored manifest | The Ed25519 signature no longer matches → verification fails |
| **Nonce reuse** | Submit two attestations with the same nonce | The system detects duplicate nonces and rejects the second |

Running this script produces output showing "BLOCKED" for all three attacks.

---

## 8. Every File, Explained

### Project Root Files

| File | Role | Why it exists |
|---|---|---|
| `README.md` | Project overview for new developers | First thing anyone reads |
| `PROGRESS.md` | Checklist of all completed features | Tracks what's done |
| `USAGE.md` | Developer how-to guide | How to run and use the system |
| `EXPLAINED.md` | Plain-English component explanation | For non-technical readers |
| `MASTER_GUIDE.md` | ← **This file** | Complete master reference |
| `PROJECT_DOCUMENTATION.md` | Technical benchmark documentation | Shows real test results |
| `docker-compose.yml` | Defines all services and their connections | One command to start everything |
| `alembic.ini` | Alembic configuration | Tells alembic where the DB is |
| `.env.example` | Template for all environment variables | Copy to `.env`, fill in secrets |
| `.gitignore` | Files Git won't commit | Prevents secrets/weights from leaking |

---

### Backend Structure

```
backend/
├── app/
│   ├── main.py          ← Entry point: creates FastAPI app, registers routes
│   ├── config.py        ← All settings: DB URL, JWT secret, thresholds, file limits
│   │                       Reads from .env file so secrets aren't in code
│   ├── core/
│   │   ├── security.py  ← Password hashing (Argon2id) + JWT create/verify
│   │   ├── rbac.py      ← Role definitions and permission checks
│   │   ├── database.py  ← Opens PostgreSQL connection (SQLAlchemy async engine)
│   │   ├── deps.py      ← "get_current_user()" — reads JWT from each request
│   │   └── logging.py   ← Structured JSON logging (every log line is parseable)
│   ├── models/
│   │   └── db_models.py ← SQLAlchemy table definitions (the Python representation
│   │                       of the database schema)
│   ├── api/
│   │   ├── auth.py      ← /auth/* endpoints: register, login, refresh, me
│   │   ├── upload.py    ← /videos/* endpoints: upload, list, delete
│   │   ├── jobs.py      ← /jobs/* endpoints: list, get one job
│   │   ├── attestations.py ← /attestations/* endpoints: list, get, download
│   │   ├── verify.py    ← /verify/ endpoint: 7-step public verification
│   │   ├── admin.py     ← /admin/* endpoints: keys, revoke, anomaly events
│   │   └── shares.py    ← /shares/* endpoints: create/view encrypted shares
│   ├── services/
│   │   ├── hashing.py   ← SHA-256 + pHash computation
│   │   ├── signer.py    ← Ed25519 key loading and signing
│   │   ├── manifest.py  ← Builds and canonicalizes the attestation JSON
│   │   ├── merkle_log.py ← Merkle tree: append, prove, verify
│   │   ├── timestamp.py ← RFC 3161 TSA request + response handling
│   │   ├── verifier.py  ← Runs all 7 verification checks
│   │   ├── policy.py    ← Score → Verdict conversion
│   │   ├── revocation.py ← Signed revocation list management
│   │   ├── sharing.py   ← X25519 key exchange + AES-256-GCM encryption
│   │   ├── anomaly.py   ← Real-time anomaly scoring (Isolation Forest)
│   │   ├── video_io.py  ← Video validation: magic bytes, FFprobe duration
│   │   ├── face.py      ← Face detection wrapper (OpenCV Haar cascade)
│   │   └── detector.py  ← Loads ensemble model and runs inference
│   └── workers/
│       └── tasks.py     ← Celery task: the full analysis pipeline in one function
└── tests/
    ├── test_auth.py             ← Login, register, JWT tests
    ├── test_upload_pipeline.py  ← Video upload and job creation tests
    ├── test_attestation_verification.py ← Signing and verification tests
    ├── test_anomaly_detection.py ← Anomaly scoring tests
    ├── test_merkle_log.py       ← Merkle tree correctness tests
    ├── test_api_endpoints.py    ← 16 API endpoint integration tests
    └── conftest.py              ← Shared fixtures: in-memory DB, test client
```

---

### ML Structure

```
ml/
├── models/
│   ├── efficientnet_b4.py  ← Model 1: Spatial deepfake detector
│   ├── frequency_cnn.py    ← Model 2: Frequency/spectral detector
│   ├── temporal_bigru.py   ← Model 3: Temporal motion sequence detector
│   └── ensemble.py         ← Combines all three models
├── configs/
│   ├── efficientnet_b4.yaml ← Training hyperparameters for Model 1
│   ├── frequency_cnn.yaml   ← Training hyperparameters for Model 2
│   ├── temporal_bigru.yaml  ← Training hyperparameters for Model 3
│   └── ensemble.yaml        ← Ensemble fusion configuration
├── datasets/
│   └── loaders.py          ← PyTorch Dataset: loads FaceForensics++, Celeb-DF, DFDC
├── anomaly/
│   ├── __init__.py
│   └── train_anomaly.py    ← Trains Isolation Forest on access logs
├── train.py                ← Training loop: Adam optimizer, mixed precision, early stopping
├── evaluate.py             ← Test set evaluation: AUC-ROC, F1, threshold sweep
├── export.py               ← Export to ONNX or TorchScript for fast inference
└── gradcam.py              ← GradCAM heatmaps: shows where the model is "looking"
```

---

### Frontend Structure

```
frontend/
├── src/
│   ├── App.jsx             ← Router: maps URLs to pages, defines AppLayout wrapper
│   ├── main.jsx            ← React entry point: mounts App into the HTML
│   ├── pages/
│   │   ├── Login.jsx       ← Login form page
│   │   ├── Register.jsx    ← Registration form page
│   │   ├── Dashboard.jsx   ← Stats overview page
│   │   ├── UploadPage.jsx  ← Video upload page
│   │   ├── Jobs.jsx        ← Jobs list with live polling
│   │   ├── Attestations.jsx ← Attestations list and detail view
│   │   └── Verify.jsx      ← Public verification page
│   ├── contexts/
│   │   └── AuthContext.jsx ← Stores JWT tokens, user info; provides login/logout
│   ├── hooks/
│   │   └── useApi.js       ← Custom React hook: handles API calls with auth headers
│   └── components/         ← Reusable UI pieces (buttons, cards, badges, etc.)
├── index.html              ← The HTML shell (React mounts into this)
├── vite.config.js          ← Build configuration
└── tailwind.config.js      ← Tailwind CSS theme configuration
```

---

### Scripts

| Script | What it does | When to run |
|---|---|---|
| `scripts/seed_keys.py` | Generate Ed25519 keypairs (signing + TSA) with correct permissions | Once, during first setup |
| `scripts/generate_ca.py` | Generate a self-signed demo Certificate Authority | Once, for local development |
| `scripts/download_weights.py` | Download real model weights OR generate mock weights | First setup or after `git clone` |
| `scripts/simulate_attack.py` | Demonstrate all attacks are blocked (replay, tampering, nonce reuse) | Anytime, for demonstration |

---

### Infrastructure

| File | Role |
|---|---|
| `docker-compose.yml` | Defines all 6 services (api, worker, frontend, db, redis, minio) and their connections |
| `deploy/Dockerfile.api` | Build instructions for the FastAPI server Docker image |
| `deploy/Dockerfile.worker` | Build instructions for the Celery worker image (GPU-enabled) |
| `deploy/Dockerfile.frontend` | Builds React app, serves via nginx |
| `deploy/nginx.conf` | Routes `/api/` to FastAPI, everything else to React |
| `alembic/versions/` | Database migration files — how to build the schema from scratch |

---

## 9. How It's Built & Run

### Quick Start (Local Development)

```bash
# 1. Clone and enter the project
cd /Users/apple/Desktop/Acad/Projs/ISC/deepfake-auth

# 2. Activate the backend Python environment
conda activate ISC

# 3. Generate keys (first time only)
python scripts/seed_keys.py --output-dir ./keys

# 4. Generate mock model weights (first time only)
python scripts/download_weights.py --mock

# 5. Create the .env file from template
cp .env.example .env
# Edit .env to fill in your database URL, JWT secret, etc.

# 6. Run all tests
PYTHONPATH=. pytest backend/tests/ -q

# 7. Start the backend server
PYTHONPATH=. uvicorn backend.app.main:app --reload --port 8000

# 8. In another terminal, start the frontend
cd frontend && npm install && npm run dev
# Frontend runs at http://localhost:5173
# API documentation at http://localhost:8000/docs
```

### Docker (Full Stack)

```bash
# Start everything with one command
docker compose up --build

# Services:
# - Frontend:  http://localhost:5173
# - Backend:   http://localhost:8000
# - API Docs:  http://localhost:8000/docs
# - MinIO UI:  http://localhost:9001 (minioadmin/minioadmin)
```

### Environment Variables (`.env`)

| Variable | What it is |
|---|---|
| `DATABASE_URL` | PostgreSQL connection string |
| `JWT_SECRET_KEY` | Random secret for signing JWT tokens |
| `ML_WEIGHTS_DIR` | Path to `weights/` directory |
| `SIGNING_KEY_PATH` | Path to Ed25519 private key PEM file |
| `TSA_URL` | URL of the Time Stamping Authority |
| `MINIO_ENDPOINT` | MinIO server address |
| `REDIS_URL` | Redis connection URL for Celery |

---

## 10. What This System Cannot Do (Honest Limits)

This section is critical to understanding what the project actually claims.

### What the cryptography DOES guarantee ✅

- ✅ **Who made the claim**: The Ed25519 signature proves the analysis was performed by whoever holds the private key
- ✅ **Which video**: The SHA-256 proves the analysis was performed on the exact bytes of this specific video
- ✅ **When it happened**: The RFC 3161 timestamp proves approximately when the analysis was recorded
- ✅ **Nothing changed**: The signature covers the full manifest — any post-signing modification breaks verification
- ✅ **It's in the log**: The Merkle inclusion proof proves the entry wasn't inserted retroactively

### What the cryptography CANNOT guarantee ❌

- ❌ **That the AI is correct**: The system can be wrong. A novel deepfake type may fool all three detectors. A real video may (rarely) score above the threshold.
- ❌ **That the video is "authentic"**: `NO_MANIPULATION_DETECTED` means "we found no signs of manipulation," not "this video is definitely real." The absence of evidence is not evidence of absence.
- ❌ **Future-proofness**: A deepfake trained on 2026-era generators may evade detectors trained on 2024-era generators. This is the "arms race" problem in deepfake detection.
- ❌ **What happened before upload**: The system only analyzes what's given to it. Someone could submit a fake video and receive a "clean" attestation if the fake is convincing enough.

### Why we use hedged language

Every verdict uses hedged language intentionally:
- "LIKELY_MANIPULATED" not "definitely fake"
- "NO_MANIPULATION_DETECTED" not "authentic"
- Verification output always shows the disclaimer: *"This AI gave a probabilistic opinion. Cryptography proves the system made this claim — not that the claim is correct."*

This is not a weakness — it is intellectual honesty. The system does not claim to be a truth machine. It claims to be a **traceable, verifiable, tamper-proof record of a probabilistic AI analysis.**

---

## 11. Glossary — Every Term, Simply

| Term | Simple definition |
|------|-------------------|
| **AES-256-GCM** | A strong symmetric encryption algorithm. AES = the cipher, 256 = key length in bits, GCM = mode that also detects tampering |
| **Alembic** | A Python tool for managing database schema changes over time — like version control for the database structure |
| **API** | Application Programming Interface — a set of URLs the browser can call to make the server do things |
| **Argon2id** | The recommended password hashing algorithm. Intentionally slow and memory-heavy to prevent bulk password cracking |
| **Attestation** | A formal, signed record of an AI analysis result. The main output of this system |
| **Attention mechanism** | A neural network component that learns which parts of an input (frames, pixels) to focus on when making a decision |
| **AUC-ROC** | Area Under the Receiver Operating Characteristic curve — a standard measure of a classifier's overall accuracy (1.0 = perfect, 0.5 = random) |
| **BiGRU** | Bidirectional Gated Recurrent Unit — processes sequences in both directions, capturing context from past AND future |
| **Canonicalization** | Standardizing a document to a single exact representation before signing, so the signature works regardless of formatting |
| **Celery** | A Python framework for running tasks asynchronously in background worker processes |
| **Centroid tracking** | Following a face across frames by tracking the center point (centroid) of the face bounding box |
| **CNN** | Convolutional Neural Network — a neural network architecture designed to recognize patterns in images |
| **Collision resistance** | A property of hash functions: it's computationally impossible to find two different inputs with the same hash output |
| **CORS** | Cross-Origin Resource Sharing — a browser security feature controlling which websites can call your API |
| **DCT** | Discrete Cosine Transform — a mathematical operation that decomposes an image into frequency components |
| **Deepfake** | A synthetic video where a person's face is replaced or animated using AI |
| **Digital signature** | A mathematical proof that a document was created by a specific key holder and hasn't been changed since |
| **Docker** | A system for packaging software into "containers" that run identically on any computer |
| **Domain separation** | Using prefixes (like 0x00/0x01) when hashing leaves vs. nodes in a Merkle tree, preventing certain attacks |
| **Ed25519** | An elliptic curve digital signature algorithm — fast, compact 64-byte signatures, very secure |
| **EfficientNet-B4** | A Google image classification neural network, here fine-tuned for deepfake detection |
| **Ensemble** | Multiple models whose outputs are combined — usually more accurate than any single model |
| **FastAPI** | A modern Python web framework for building APIs with automatic validation and documentation |
| **Feature vector** | A list of numbers that compactly describes what a neural network "sees" in an image — an internal representation |
| **FFmpeg/FFprobe** | Open-source tools for processing video files — extracting frames, converting formats, probing metadata |
| **Fine-tuning** | Taking a pre-trained neural network and retraining its final layers on a new, related task |
| **GradCAM** | Gradient-weighted Class Activation Mapping — creates heatmaps showing where a neural network focused |
| **GRU** | Gated Recurrent Unit — a neural network cell with "memory" that learns patterns in sequences |
| **Hash function** | A mathematical function that maps any input to a fixed-length output; same input always gives same output |
| **HKDF** | HMAC-based Key Derivation Function — derives cryptographic keys of any length from a shared secret |
| **HSM** | Hardware Security Module — a physical device designed to store and use private keys without exposing them |
| **Isolation Forest** | A machine learning algorithm for anomaly detection — isolates unusual data points via random partitioning |
| **JWT** | JSON Web Token — a compact, signed token containing identity claims, used for stateless authentication |
| **Merkle inclusion proof** | The minimal set of hashes needed to verify that a specific entry is in a Merkle tree |
| **Merkle tree** | A data structure where every node is the hash of its children; the root summarizes all entries |
| **MinIO** | An open-source object storage server compatible with Amazon S3's API — stores large files like videos |
| **Neural network** | A mathematical model loosely inspired by the brain, learning patterns from examples via layers of computations |
| **Nonce** | A number used once — a random value included in a protocol to prevent replay attacks |
| **ONNX** | Open Neural Network Exchange — a standard format for exporting ML models to run in any framework |
| **pHash** | Perceptual hash — a "fuzzy fingerprint" that stays similar for visually similar images, unlike cryptographic hashes |
| **Policy engine** | The component that converts a raw probability score into a human-readable verdict label |
| **PostgreSQL** | A powerful open-source relational database — stores structured data in tables with relationships |
| **Private key** | The secret half of a cryptographic key pair — used to create signatures; must never be shared |
| **Public key** | The shareable half of a key pair — anyone can use it to verify signatures made with the corresponding private key |
| **RBAC** | Role-Based Access Control — users have roles, and each API endpoint checks whether your role permits access |
| **React** | A JavaScript library for building interactive web interfaces from reusable components |
| **Redis** | An in-memory database used here as a task queue broker — extremely fast |
| **Replay attack** | An attack where a valid message/attestation is re-submitted to fraudulently claim a fresh result |
| **RFC** | Request for Comments — the document format used to define internet standards |
| **RFC 3161** | The internet standard for trusted timestamping — proves a document existed at a specific time |
| **RFC 6962** | The Certificate Transparency standard — defines Merkle transparency logs for public auditability |
| **RFC 8785** | The JSON Canonicalization Scheme — a standard way to normalize JSON before signing |
| **Revocation** | The act of invalidating a certificate/attestation, marking it as no longer trustworthy |
| **SHA-256** | Secure Hash Algorithm producing a 256-bit (64 character) fingerprint; one-bit change in input changes everything |
| **Signed Tree Head (STH)** | A signed commitment to the current state of a Merkle log — root hash + entry count + timestamp, all signed |
| **SQLAlchemy** | A Python ORM — lets you work with database tables as Python objects instead of raw SQL |
| **Temporal artifacts** | Inconsistencies in a deepfake video that only appear when looking at multiple frames over time |
| **TorchScript** | PyTorch's format for exporting models to run without Python — faster inference in production |
| **TSA** | Time Stamping Authority — a trusted third-party service that issues RFC 3161 timestamps |
| **Uvicorn** | An ASGI web server that runs FastAPI applications |
| **Vite** | A fast build tool for frontend JavaScript — development server + production bundler |
| **Weight SHA-256** | The SHA-256 hash of a model's weights file — proves which exact model version was used for analysis |
| **X25519** | A Diffie-Hellman key exchange algorithm — allows two parties to derive a shared secret without transmitting it |

---

*Last updated: November 2026 | For the AI + Information Security + Cryptography university project track*
*Project location: `/Users/apple/Desktop/Acad/Projs/ISC/deepfake-auth/`*
