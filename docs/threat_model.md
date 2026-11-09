# DeepAuth — Threat Model

> This document describes the security threat model for DeepAuth. It identifies trust boundaries, assets, threat actors, and specific threats, and maps each threat to its mitigation. An honest limitations section is included.

---

## Table of Contents

1. [Assets and Trust Boundaries](#1-assets-and-trust-boundaries)
2. [Threat Actors](#2-threat-actors)
3. [STRIDE Analysis](#3-stride-analysis)
4. [Specific Threats and Mitigations](#4-specific-threats-and-mitigations)
5. [Security Properties Table](#5-security-properties-table)
6. [Honest Limitations](#6-honest-limitations)

---

## 1. Assets and Trust Boundaries

### 1.1 Assets

| Asset | Sensitivity | Impact if Compromised |
|-------|-------------|----------------------|
| Ed25519 signing private key | Critical | Attacker can forge attestations for any video |
| User credentials (passwords, JWT tokens) | High | Unauthorized uploads, impersonation |
| Video files | High | Privacy violation; content exposure |
| Attestation records | High | Fake proofs of authenticity; tampered verdicts |
| Merkle tree head | Medium | Undetectable inclusion of forged attestations |
| ML model weights | Medium | IP theft; enables adversarial attack crafting |
| Audit log | Medium | Evidence destruction, covering tracks |
| PostgreSQL connection string | High | Full database access |
| Redis connection string | Medium | Queue poisoning, DoS |
| MinIO credentials | High | Video exfiltration or deletion |

### 1.2 Trust Boundaries

```
┌─────────────────────────────────────────────────────────────────────┐
│  INTERNET (untrusted)                                                │
│                                                                      │
│  ┌────────────────────────────────────────────────────────────────┐ │
│  │  TLS BOUNDARY (Nginx terminates TLS)                           │ │
│  │                                                                │ │
│  │  ┌──────────────────────────────────────────────────────────┐ │ │
│  │  │  APPLICATION BOUNDARY (FastAPI, Celery workers)          │ │ │
│  │  │                                                          │ │ │
│  │  │  ┌────────────────────────────────────────────────────┐ │ │ │
│  │  │  │  DATA BOUNDARY (PostgreSQL, Redis, MinIO)          │ │ │ │
│  │  │  │                                                    │ │ │ │
│  │  │  │  ┌──────────────────────────────────────────────┐ │ │ │ │
│  │  │  │  │  KEY MANAGEMENT BOUNDARY (Vault / SoftHSM)  │ │ │ │ │
│  │  │  │  └──────────────────────────────────────────────┘ │ │ │ │
│  │  │  └────────────────────────────────────────────────────┘ │ │ │
│  │  └──────────────────────────────────────────────────────────┘ │ │
│  └────────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────┘
```

Each boundary crossing requires explicit authentication and authorisation:
- **Internet → TLS boundary:** TLS 1.3 mutual or server-side certificate.
- **TLS → Application:** JWT bearer token; every request validated.
- **Application → Data:** Credentials in environment variables; network-policy restricted.
- **Application → Key Mgmt:** Vault AppRole / PKCS#11 PIN; never exposed to API layer.

---

## 2. Threat Actors

| Actor | Capabilities | Goals |
|-------|-------------|-------|
| **External attacker** | Unauthenticated internet access; standard web attack toolkit | Exfiltrate videos, forge attestations, disrupt service |
| **Malicious registered user** | Valid JWT, can upload and retrieve own content | Obtain false `NO_MANIPULATION_DETECTED` verdict for a deepfake; abuse storage/compute |
| **Compromised insider** | Access to production infrastructure or source code | Forge attestations, suppress audit events, steal signing key |
| **State-level / well-resourced attacker** | Cryptanalysis, side-channel attacks, vendor compromise | Long-term key compromise, undermine trust in entire log |
| **Adversarial ML attacker** | Can craft specially prepared video inputs | Fool the classifier into emitting a benign verdict for a manipulated video |

---

## 3. STRIDE Analysis

### 3.1 API Gateway (FastAPI)

| STRIDE | Threat | Mitigation |
|--------|--------|-----------|
| **S**poofing | Stolen JWT used to impersonate a user | Short access token lifetime (15 min); refresh token rotation; revocation on logout |
| **T**ampering | Attacker modifies request body in transit | TLS 1.3 in transit; Pydantic validation rejects malformed inputs |
| **R**epudiation | User denies uploading a video | `audit_log` records IP, user-agent, timestamp for every upload |
| **I**nformation Disclosure | Error messages leak internal paths or SQL | Generic 500 responses; structured logging kept server-side only |
| **D**oS | Flood of upload requests exhausts workers | Redis-backed rate limiting; file size cap; Celery queue depth monitoring |
| **E**levation of Privilege | Regular user calls `/admin/*` endpoints | RBAC `Depends` guard; role encoded in JWT; verified server-side |

### 3.2 Detection Worker (Celery)

| STRIDE | Threat | Mitigation |
|--------|--------|-----------|
| **S**poofing | Rogue worker impersonates legitimate worker | Redis auth + network-policy; workers share no JWT surface |
| **T**ampering | Attacker injects malicious task into Redis queue | Redis `requirepass`; network-ACL restricts producer to API instances only |
| **R**epudiation | Worker silently drops task | Celery retry policy; job status transitions written to PostgreSQL |
| **I**nformation Disclosure | Video file exposed in worker temp directory | Workers run in isolated containers; temp files deleted after inference |
| **D**oS | Adversarial video exhausts GPU memory | File size limit enforced before enqueue; timeout per task |
| **E**levation of Privilege | Worker escapes container | Container runs as non-root; read-only filesystem where possible |

### 3.3 Attestation Service

| STRIDE | Threat | Mitigation |
|--------|--------|-----------|
| **S**poofing | Attacker claims an attestation was produced by DeepAuth | Ed25519 signature over manifest; public key pinned in `/admin/keys` |
| **T**ampering | Attestation record modified in database | Signature covers full manifest; any change invalidates signature |
| **R**epudiation | Operator denies having signed a specific result | Merkle inclusion proof links manifest hash to published tree head |
| **I**nformation Disclosure | Manifest leaks sensitive metadata | Manifests contain only hashes and verdicts; no PII |
| **D**oS | Flood of verify requests | Rate limiting on `/verify/*`; verification is CPU-cheap |
| **E**levation of Privilege | Attacker gains access to signing key | Key stored in Vault / SoftHSM; signing API accepts hash only |

### 3.4 Database (PostgreSQL)

| STRIDE | Threat | Mitigation |
|--------|--------|-----------|
| **S**poofing | Attacker connects with stolen DB credentials | Credentials rotated via Vault dynamic secrets; network-policy restricts access |
| **T**ampering | Direct SQL manipulation of attestation records | Principle of least privilege: app user has no DDL rights; audit log is append-only |
| **R**epudiation | DBA deletes audit rows | `audit_log` table: `INSERT`-only privileges for app role; no `DELETE` or `UPDATE` |
| **I**nformation Disclosure | SQL injection extracts data | Parameterised queries via SQLAlchemy ORM; no raw string formatting |
| **D**oS | Long-running queries starve connection pool | Statement timeout (`statement_timeout = 10s`); connection pool cap |
| **E**levation of Privilege | App user escalates to superuser | App role has no `CREATEROLE` or `SUPERUSER`; audited by pg_audit extension |

---

## 4. Specific Threats and Mitigations

### 4.1 Replay Attacks

**Threat:** An attacker replays a previously captured legitimate attestation, claiming it applies to a different (manipulated) video.

**Mitigation:**
- The signed manifest includes `video_sha256` (SHA-256 of the exact video bytes), `nonce` (32-byte random value), and `analysis_timestamp`.
- Reusing a manifest for a different video requires producing a valid Ed25519 signature — computationally infeasible without the private key.
- The verifier checks that `video_sha256` matches the submitted content before accepting the attestation as valid.

---

### 4.2 Key Compromise

**Threat:** The Ed25519 signing private key is exfiltrated, allowing an attacker to sign arbitrary fake attestations.

**Mitigation:**
- **Hardware boundary:** In production, the key never exists in process memory; signing is delegated to Vault Transit or a PKCS#11 HSM.
- **Revocation:** Compromised keys are added to the revocation list (`POST /admin/revoke`). All attestations signed by the revoked key are flagged.
- **Key rotation:** New key pair is generated; old public key is archived for historical verification. New attestations use the new key.
- **Monitoring:** Anomalous signing volume triggers an `anomaly_events` alert.

---

### 4.3 Adversarial Inputs (AI Evasion)

**Threat:** A sophisticated attacker crafts a deepfake video specifically designed to fool the ensemble detector (e.g., adversarial perturbations, GAN-based camouflage).

**Mitigation (partial):**
- Three complementary detectors operating in different feature spaces (spatial, frequency, temporal) raise the bar for a successful evasion attack that must fool all three simultaneously.
- The `INCONCLUSIVE` verdict band (0.30–0.70) acknowledges uncertainty rather than forcing a binary decision.

> [!CAUTION]
> **This is a known and stated limitation.** The system does not guarantee detection of adversarially optimised deepfakes. See [Section 6](#6-honest-limitations).

---

### 4.4 Upload Abuse / Resource Exhaustion

**Threat:** A user uploads a large volume of large videos to exhaust GPU compute, storage, or database resources.

**Mitigation:**
- Per-user rate limit on `POST /videos/` (configurable; default: 10 uploads/hour).
- Maximum file size enforced at the gateway before the file touches MinIO.
- Celery queue depth monitoring; backpressure signals surface in `GET /health`.
- Isolation Forest anomaly detection flags users with anomalous upload patterns for admin review.
- Storage quota per user enforced at the application layer.

---

### 4.5 Signature Forgery

**Threat:** Attacker crafts a fake Ed25519 signature without access to the private key.

**Mitigation:**
- Ed25519 provides 128-bit security against existential forgery; no known practical attacks.
- All verification paths check the signature cryptographically before trusting any manifest field.

---

### 4.6 Timestamp Manipulation

**Threat:** Attacker falsifies the analysis time to claim an attestation was produced before a certain event (e.g., before a known deepfake was published).

**Mitigation:**
- RFC 3161 Trusted Timestamp Authority (TSA) signs a hash of the manifest with its own private key and includes a certified time from its clock.
- The TSA is an independent third party; DeepAuth cannot modify the timestamp token after issuance.
- Verifiers can independently validate the TSA signature using the TSA's public certificate.

---

### 4.7 Merkle Log Manipulation

**Threat:** Attacker retroactively removes or modifies a leaf in the Merkle log to erase or alter an attestation.

**Mitigation:**
- The Merkle tree is **append-only**: new leaves are added, existing leaves are never modified.
- Changing any leaf changes the root hash; published tree heads are compared by monitors.
- Consistency proofs (RFC 6962 §2.1.4) can prove the log has only grown, never changed.
- Future work: submit tree heads to an external public log service (e.g., Sigstore Rekor).

---

### 4.8 JWT Compromise

**Threat:** A stolen or leaked JWT allows an attacker to act as the victim user.

**Mitigation:**
- **Short expiry:** Access tokens expire in 15 minutes.
- **Refresh token rotation:** Each `POST /auth/refresh` issues a new refresh token and invalidates the old one.
- **Revocation on logout:** Refresh token is deleted from the database on logout.
- **HTTPS only:** `Secure` and `HttpOnly` cookie attributes enforced if cookies are used; `Authorization: Bearer` header over TLS otherwise.
- **Anomaly detection:** Multiple logins from different IP addresses within a short window generates an `anomaly_event`.

---

### 4.9 SQL Injection

**Threat:** Attacker injects SQL via user-controlled input fields to read or modify database rows.

**Mitigation:**
- All database access uses SQLAlchemy's ORM with parameterised queries. No raw string interpolation into SQL.
- Pydantic v2 validates and coerces all input types before they reach the ORM layer.
- Application database user has no DDL privileges.

---

### 4.10 Cross-Origin Attacks (CORS / CSRF)

**Threat:** Malicious website tricks an authenticated user's browser into making requests to DeepAuth.

**Mitigation:**
- CORS policy allows only the configured frontend origin (`CORS_ORIGINS` env var); no wildcard.
- API uses `Authorization: Bearer` header (not cookies by default), which cannot be sent cross-origin by a third-party page.
- For cookie-based flows: `SameSite=Strict` and CSRF double-submit token.

---

### 4.11 Insecure Direct Object Reference (IDOR)

**Threat:** User A accesses video or attestation belonging to User B by guessing a UUID.

**Mitigation:**
- All resource queries include `WHERE owner_id = :current_user_id` or equivalent ownership check.
- UUIDs are random (v4); not enumerable.
- `GET /attestations/{id}` returns 404 (not 403) for resources the user does not own, to avoid confirming existence.

---

## 5. Security Properties Table

### What DeepAuth DOES Guarantee

| Property | Mechanism |
|----------|-----------|
| **Integrity:** An attestation record has not been modified since issuance | Ed25519 signature over full manifest |
| **Authenticity:** The attestation was produced by this DeepAuth instance | Verifiable against published public key |
| **Non-repudiation:** The signer cannot deny having produced the attestation | Merkle inclusion proof + RFC 3161 timestamp |
| **Revocability:** Compromised keys and fraudulent attestations can be invalidated | Revocation list checked on every verification |
| **Confidentiality of shared attestations:** Only the intended recipient can decrypt | X25519 + HKDF + AES-256-GCM |
| **Auditability:** All privileged actions leave a tamper-evident trail | Append-only `audit_log` table |
| **Password security:** Stored passwords resist offline brute-force | Argon2id with tuned time/memory cost |

### What DeepAuth Does NOT Guarantee

| Non-Guarantee | Explanation |
|---------------|-------------|
| **Detection of all deepfakes** | ML models have false-negative rates; adversarial inputs may evade detection |
| **Detection of future deepfake methods** | Models trained on current datasets may not generalise to novel generation techniques |
| **Chain-of-custody of the original video** | The system verifies the video submitted to it; it cannot verify how the video was obtained or whether it has been edited before upload |
| **Absolute key security without HSM** | In `local` key backend mode, key material is on disk and must be protected by OS-level controls |
| **Real-time detection** | Processing time varies (seconds to minutes) depending on video length and worker load |
| **Legal admissibility** | A cryptographic attestation is technical evidence; its legal weight depends on jurisdiction and context |

---

## 6. Honest Limitations

1. **Adversarial robustness:** The ensemble is not adversarially trained by default. A motivated attacker with white-box access to the model architecture can craft evasion inputs. Adversarial training (e.g., PGD-AT) would improve robustness at the cost of accuracy on natural inputs.

2. **Dataset shift:** Models trained on FaceForensics++, DFDC, and Celeb-DF may not generalise to new generation pipelines (e.g., diffusion-based face swap methods released after the training cut-off).

3. **Non-face deepfakes:** The pipeline is optimised for face-swap deepfakes. Lip-sync manipulation, body puppetry, or background synthesis are not specifically targeted.

4. **Audio deepfakes:** The system analyses video frames only; audio manipulation is out of scope.

5. **Compressed videos:** Severe lossy compression can destroy frequency-domain artefacts that FrequencyCNN relies on, increasing false-negative rates.

6. **Single-signer trust model:** The security of attestations depends entirely on DeepAuth's signing key not being compromised. There is no multi-party signing or threshold scheme in this version.

7. **TSA dependency:** The RFC 3161 timestamp relies on the availability and honesty of the third-party TSA. If the TSA is compromised or unavailable, timestamp tokens cannot be issued (attestations are still signed, but lack certified timestamps).

8. **University deployment:** This system is a research/educational prototype. It has not undergone a formal third-party security audit. **It should not be used for high-stakes legal or forensic purposes without further independent review.**
