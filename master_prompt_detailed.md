# MASTER BUILD PROMPT (DETAILED EDITION)
## AI-Based Fake Identity & Document Screening System — SIH 2026, Problem Statement 26188

This is the complete build specification for an autonomous coding agent (Claude Code or similar). It is written to be self-contained: everything needed to understand *why* each feature exists and *how* to build it is included below. Read it fully before writing code. Do not skip sections. Do not invent requirements not stated here — if something is ambiguous, implement the simplest version consistent with the rest of this document and note the assumption in a comment.

---

## PART A — PROBLEM CONTEXT (read first, this drives every design decision below)

### A.1 Official Problem Statement

- **ID**: 26188
- **Title**: AI-Based Fake Identity & Document Screening System
- **Organization**: Ministry of Home Affairs
- **Department**: Sashastra Seema Bal (SSB), Police II Division
- **Category**: Software
- **Theme**: Blockchain & Cybersecurity

SSB guards the India-Nepal and India-Bhutan borders, which are open borders with high foot traffic and simplified document requirements compared to international airports. This means:

- Volume is very high relative to staffing.
- Documents used are often lower-security-feature IDs (national ID, permits) rather than passports, making forgery easier than at an airport.
- The border regions have ethnically and linguistically diverse populations, which matters directly for the fairness of any face-recognition component (see Part F.6).

### A.2 The Named Problems (from the PS "Background" section) — restated in plain terms

1. **Fake passports and visas** — a document that was never legitimately issued, either a forged blank or a completely fabricated document.
2. **Altered photographs** — a genuine document where the photo has been swapped for a different person's photo.
3. **Modified dates of birth** — a genuine document where the DOB field has been digitally or physically altered (to appear older/younger, e.g. to cross an age threshold or to falsify a match against another record).
4. **Tampered visa stamps** — entry/exit stamps that have been forged or copied to fake a travel history.
5. **Identity impersonation** — a person presenting someone else's genuine document, claiming to be them.
6. **Multiple identities used by the same person** — one individual holds/uses several different documents under different names, to defeat blacklisting or evade tracking.
7. **Expired or blacklisted travel documents** — documents that are technically genuine but no longer valid for entry.
8. **High passenger volume causing delays** — an operational problem, not a fraud problem: manual checks don't scale, and queues build up.

### A.3 Current State (what SSB does today, per the PS)

"Current verification methods rely heavily on human inspection and basic database lookups." This means: an officer visually inspects the document, checks it against whatever local database exists, and makes a judgment call. This is slow, inconsistent between officers, and cannot reliably catch sophisticated digital tampering (compression artifacts, cloned stamp regions, etc. are invisible to the naked eye).

### A.4 Expected Solution — the 4 mandated modules

The PS explicitly asks for exactly these four modules. **These four, and only these four, are the mandatory scope.** Everything else in this document (blockchain, watchlist, duplicate-travel detection, geolocation) is value-add we are choosing to build on top, and must be clearly presented as such — not confused with the mandatory scope when explaining the project.

- **Module 1 — OCR Extraction**: pull structured fields out of a document image (name, document number, nationality, DOB, expiry, gender, and visa-specific fields like visa number/type/validity/stay duration).
- **Module 2 — Document Validation**: check whether the extracted data is internally consistent and conforms to the official standard for that document type (not fraud detection yet — just "is this data well-formed and logical").
- **Module 3 — Tampering Detection**: the PS explicitly calls this "the Core AI Innovation." This is where the actual forensic/computer-vision work happens: detecting photo replacement, text manipulation, stamp forgery, and metadata inconsistencies.
- **Module 4 — Face Verification**: confirm the person standing at the checkpoint is the same person as in the document photo.

### A.5 Expected Impact (from the PS) — use these as the success metrics for the demo

- Reduce document verification time from minutes to seconds.
- Improve detection of forged/tampered documents.
- Standardize screening decisions across checkpoints (removes officer-to-officer inconsistency).
- Enable data-driven risk assessment instead of purely manual inspection.
- Create a digital trail for investigations and intelligence analysis.

Every feature in this build should be traceable back to one of these five outcomes. If a feature doesn't serve one of them, cut it.

### A.6 Why "Blockchain & Cybersecurity" as the theme, when the Expected Solution doesn't mention blockchain

This is a deliberate gap in the PS that we are filling strategically. The "digital trail for investigations" impact goal is the natural hook: a blockchain-style tamper-evident ledger is exactly what "digital trail" implies, and it is also exactly what the PS's stated theme calls for. We are not bolting blockchain on arbitrarily — we are using it to satisfy a requirement (digital trail) that the Expected Solution section left unimplemented. State this explicitly in the pitch: "The PS's theme is Blockchain & Cybersecurity, and its own Expected Impact section calls for a digital trail — we built the one piece of infrastructure that ties those two things together."

---

## PART B — FULL FEATURE LIST (mandatory + value-add, clearly separated)

### B.1 Mandatory (from the PS)
1. Document upload/capture (implied — a screening system needs input).
2. Module 1: OCR Extraction.
3. Module 2: Document Validation.
4. Module 3: Tampering Detection.
5. Module 4: Face Verification.
6. A risk score / decision aid for the officer (implied by "assist border security personnel in making faster and more accurate decisions").

### B.2 Value-add (decided in this planning conversation, layered on top)
7. Live camera capture for both document photo and live face (not just file upload).
8. Real-time streaming pipeline visualization (WebSocket-driven timeline + "thinking log") — this is a presentation/UX choice, not a PS requirement, but it makes the AI's work visible and buildable trust, which supports "data-driven risk assessment" (A.5).
9. Criminal/blacklist watchlist face matching — directly extends Module 4, supports "identity impersonation" (A.2.5) and adds a capability the PS's Module 4 description didn't explicitly ask for but is a natural extension of "face verification."
10. Geolocation + timestamp capture per verification — supports "digital trail for investigations" (A.5) and is required infrastructure for features 11 and 12 below.
11. Duplicate-verification detection (same person + same document re-scanned within a 2-hour window) — supports "multiple identities" and general fraud/loitering detection.
12. Travel-direction consistency check (manual direction entry, checked against a prior record for the same traveler) — supports detecting improbable border-crossing patterns.
13. Impossible-travel detection (Haversine distance ÷ time between two records for the same traveler exceeds a plausible speed) — supports detecting spoofed/duplicated identities being used at two physical locations.
14. Blockchain-style hash-chain audit log — directly satisfies A.6.

When you explain this project (in the PPT or to judges), always present 1-6 as "what the problem statement asked for" and 7-14 as "what we added, and why each addition ties back to the PS's own stated goals." This distinction matters for how judges score PS-adherence vs. innovation separately.

---

## PART C — SYSTEM ARCHITECTURE

### C.1 High-level component diagram (describe this to the frontend as a literal architecture slide too)

```
┌─────────────┐      WebSocket       ┌──────────────────┐
│   React     │ ◄──────────────────► │     FastAPI       │
│  Frontend   │      REST (upload,   │     Backend        │
│             │      admin, verify)  │                    │
└─────────────┘                      └─────────┬──────────┘
                                                │
                     ┌──────────────────────────┼───────────────────────────┐
                     │                          │                           │
             ┌───────▼───────┐         ┌────────▼────────┐         ┌───────▼────────┐
             │  Module        │         │   PostgreSQL     │         │  Hash-Chain     │
             │  Interface     │         │   (+ pgvector)   │         │  Audit Table    │
             │  Layer         │         │                  │         │                 │
             │ (mock now,     │         └──────────────────┘         └─────────────────┘
             │  real later)   │
             └────────────────┘
```

### C.2 Why FastAPI over Django

Django's strengths (admin panel, ORM migrations, batteries-included auth) matter less here than FastAPI's native async support and first-class WebSocket handling, which is the backbone of the live pipeline visualization (feature B.2.8). Use `SQLAlchemy` (async) or `Tortoise ORM` for the database layer, and `Alembic` for migrations if using SQLAlchemy. If an admin panel is wanted quickly, use `SQLAdmin` (works with FastAPI + SQLAlchemy) rather than pulling in Django just for that.

### C.3 Why PostgreSQL + pgvector

- Structured fields (names, dates, doc numbers) fit relational tables naturally.
- `pgvector` lets you store face embeddings as a native column type and run `ORDER BY embedding <-> query_embedding LIMIT k` for nearest-neighbor search directly in SQL — no separate vector database service needed for a 1-day build. If `pgvector` extension isn't available in the environment, fall back to storing embeddings as `float[]` and computing cosine similarity in Python at query time (fine at demo scale — records will number in the dozens, not millions).

### C.4 Why a hash-chain instead of real Hyperledger Fabric

Standing up a permissioned Hyperledger network, writing chaincode, and integrating an SDK is realistically a multi-day task on its own. A hash-chain gives the same core property judges care about — **tamper-evidence**: if any past record is altered, the chain breaks and is detectable — using nothing but a `previous_hash` column and SHA-256. This is a legitimate, real technique (this is literally how the data structure inside a blockchain works — a blockchain is a hash-chain plus a distributed consensus layer on top). Be upfront that we're implementing the data-structure core (hash-chain) without the distributed-consensus layer, and that this is the correct call for both the timeline (real Hyperledger is not a 1-day deployment) and demo needs (govt Systems must be self-hostable — the theme is Blockchain & Cybersecurity, but a lighter tamper-evident ledger is often exactly what real deployments here would use, since a permissioned single-authority ledger doesn't need multi-node consensus at all — SSB is a single authority, not a multi-party network, so consensus adds no real value).

---

## PART D — DATA MODEL (every table, every field, with rationale)

### D.1 `verification_records`

| Field | Type | Purpose |
|---|---|---|
| id | UUID PK | unique record id |
| created_at | timestamptz | when the verification happened |
| doc_type | text | passport / visa / national_id / driving_license / permit |
| doc_number | text | extracted document number (used for duplicate matching) |
| name | text | extracted name |
| dob | date | extracted date of birth |
| nationality | text | extracted nationality |
| expiry_date | date | extracted expiry date |
| ocr_raw_json | jsonb | full Module 1 output, including per-field confidence |
| validation_result_json | jsonb | full Module 2 output (pass/fail + reasons) |
| tampering_score | float | Module 3 output score, 0.0–1.0 |
| tampering_result_json | jsonb | full Module 3 output incl. flagged regions |
| tampering_heatmap_path | text | stored path/URL of heatmap overlay image |
| face_match_score | float | Module 4 similarity score |
| liveness_passed | boolean | Module 4 anti-spoof result |
| live_face_embedding | vector or float[] | embedding of the live-captured face at this checkpoint |
| watchlist_match | boolean | true if matched against `watchlist_faces` |
| watchlist_match_ref | text nullable | reference id/label of matched watchlist entry |
| latitude | float | captured via browser geolocation |
| longitude | float | captured via browser geolocation |
| travel_direction | text | "entering_india" / "entering_nepal" (manual input) |
| duplicate_of_record_id | UUID nullable FK | set if this record matched a prior record within the 2-hour window |
| travel_direction_flag | text | "consistent" / "suspicious" / "not_applicable" (no prior match) |
| impossible_travel_flag | boolean | true if Haversine speed check failed |
| impossible_travel_detail_json | jsonb | distance_km, time_elapsed_minutes, required_speed_kmh |
| risk_score | int | 0–100 composite score |
| risk_level | text | "low" / "medium" / "high" |
| risk_breakdown_json | jsonb | explainable list of {factor, points, reason} |
| officer_decision | text nullable | "approved" / "rejected" / "escalated" |
| decided_at | timestamptz nullable | when officer acted |
| record_hash | text | SHA-256 of this record's canonical data + prev_hash |
| prev_hash | text | hash of the immediately preceding record in the chain |

### D.2 `watchlist_faces`

| Field | Type | Purpose |
|---|---|---|
| id | UUID PK | |
| reference_label | text | e.g. "Case #4471" — never store this as a real accusation without proper legal backing in a real deployment; for demo, use fictional labels |
| embedding | vector or float[] | face embedding for nearest-neighbor search |
| photo_path | text | stored reference photo |
| uploaded_at | timestamptz | |
| uploaded_by | text | admin identifier |

### D.3 `admin_users` (only if the admin panel needs its own auth; otherwise a single hardcoded demo login is acceptable for a 1-day build — do not over-engineer auth)

| Field | Type |
|---|---|
| id | UUID PK |
| username | text unique |
| password_hash | text |

---

## PART E — API AND WEBSOCKET CONTRACT

### E.1 REST endpoints

- `POST /api/verification/start` → creates a new verification session, returns `session_id`. Body: `{travel_direction: str, latitude: float, longitude: float}`.
- `WS /api/verification/{session_id}/stream` → the live pipeline connection (see E.2).
- `POST /api/verification/{session_id}/document` → multipart upload of the document image/PDF. Triggers Modules 1–3 asynchronously, streaming progress over the WebSocket.
- `POST /api/verification/{session_id}/face` → multipart upload of the live-captured face image. Triggers Module 4 + watchlist check.
- `GET /api/verification/{session_id}/result` → final combined result once all modules are done (used as a fallback/poll if WebSocket drops).
- `POST /api/verification/{session_id}/decision` → officer's Approve/Reject/Escalate action; finalizes the hash-chain entry.
- `GET /api/audit/verify-chain` → recomputes the full hash-chain and returns `{valid: bool, first_broken_record_id: str|null}`.
- `POST /api/admin/watchlist` (auth required) → upload a new watchlist face + label.
- `GET /api/admin/watchlist` (auth required) → list current watchlist entries.
- `DELETE /api/admin/watchlist/{id}` (auth required) → remove an entry.

### E.2 WebSocket message schema (server → client)

Every message is JSON with this shape:

```json
{
  "stage": "ocr" | "validation" | "tampering" | "face" | "watchlist" | "duplicate_check" | "risk_score",
  "status": "started" | "progress" | "done" | "error",
  "log": "human-readable line for the thinking-log panel",
  "data": { }
}
```

Guidance for the "thinking log" text — write these as if narrating what the AI is checking, specific enough to feel real, generic enough to not overclaim:

- OCR stage: `"Detecting document type..."` → `"Document type: Passport (IN)"` → `"Locating MRZ zone..."` → `"Extracting MRZ line 1/2..."` → `"Extracting visual fields..."` → `"Field confidence check complete."`
- Validation stage: `"Verifying MRZ checksum..."` → `"Checking expiry date..."` → `"Cross-checking DOB against document type..."` → `"Validation complete: 0 failures."`
- Tampering stage: `"Running error-level analysis..."` → `"Checking sensor noise consistency across regions..."` → `"Scanning for font/spacing anomalies..."` → `"Comparing stamp against reference templates..."` → `"Tampering score: 0.08 (low)."`
- Face stage: `"Detecting face region in document..."` → `"Capturing live face..."` → `"Running liveness check..."` → `"Computing face similarity..."` → `"Match: 94.2%."`
- Watchlist stage: `"Comparing against watchlist database (12 entries)..."` → `"No match found."` or `"⚠️ Match found: [ref]."`
- Duplicate-check stage: `"Searching verification records from the last 2 hours..."` → result line.
- Risk score stage: `"Aggregating module outputs..."` → `"Final risk score: 22 (Low)."`

---

## PART F — MODULE-BY-MODULE DEEP DIVE

### F.1 Module 1 — OCR Extraction

**Purpose (from PS)**: automatically extract all relevant information from identity documents so downstream modules and the officer don't need to manually key in data.

**Inputs**: passport, visa, national ID, driving license, permit images (JPG/PNG/PDF-rasterized).

**Required output fields**:
- Passport: Name, Passport Number, Nationality, Date of Birth, Date of Expiry, Gender (plus, if feasible: Date of Issue, Place of Birth, Issuing Authority, MRZ lines).
- Visa: Visa Number, Visa Type, Entry Validity, Stay Duration.

**Mock implementation for the 1-day build**: return a fixed realistic field set with small randomized variation, plus a per-field confidence score (0.0–1.0), and randomly (e.g. 15% of the time) simulate a "low confidence" field to demonstrate the "flag for officer review" behavior described in the original planning conversation. Always extract and return a `face_crop` (can be a fixed crop region or, for the mock, just pass through a placeholder image) since Module 4 depends on it.

**Contract**: `run_ocr(document_image: bytes) -> dict` (see Part B.2 / master prompt Part 2 for exact schema — reuse the schema already defined there).

### F.2 Module 2 — Document Validation

**Purpose (from PS)**: verify whether the extracted information follows official document standards — this is a rules layer, not a fraud-detection layer. It answers "is this data well-formed and internally consistent," not "was this document altered."

**Checks to implement (can be simple Python rule functions)**:
- Expiry date is not in the past (flags "expired" — directly maps to PS challenge "expired... travel documents").
- Issue date is before expiry date.
- DOB is plausible for the stated document type (e.g. a driving license implies a minimum age).
- Document number matches an expected format/length for its type (use a simple regex; doesn't need to be country-perfect for a demo).
- Gender field is a valid enum value.

**Mock implementation**: run these rule checks against the OCR module's mock output; since the OCR mock generates mostly-valid data, deliberately make it possible to generate a document that fails 1-2 of these checks (e.g. via a demo "sample tampered document" that has an inconsistent expiry date) so the validation stage has something real to show in the demo.

### F.3 Module 3 — Tampering Detection ("Core AI Innovation" per the PS)

**Purpose**: detect digital or physical alteration: photo replacement, text manipulation, stamp forgery, and metadata inconsistency.

**What the real version (teammate's build) would do** — document this so the mock is faithful to what it's standing in for:
- Error Level Analysis (ELA): re-compresses the image and diffs against the original; edited regions show different compression artifacts.
- Noise/PRNU analysis: sensor noise pattern should be uniform across a genuine photo; a spliced-in region has a different "fingerprint."
- Font/spacing anomaly detection: a CNN trained to spot inconsistent character rendering, catching digitally altered text (e.g. modified DOB digits).
- Stamp/seal template matching: compares a detected stamp against a reference database of genuine stamp shapes/colors.
- Copy-move forgery detection (SIFT/ORB keypoint matching): catches a stamp or region duplicated elsewhere in the same image.
- Metadata/EXIF analysis: checks for re-save artifacts or editing-software signatures.

**Mock implementation**: return a `tampering_score` (0.0–1.0) and a list of `flagged_regions` (bounding boxes with a `reason` string drawn from the list above). For the demo, build two clearly distinct sample documents ahead of time: a "genuine" sample (low score, no flagged regions) and a "tampered" sample (high score, 1-2 flagged regions, e.g. around the photo or DOB field) — this is what makes the live green→red demo moment work. Generate a real heatmap-style overlay image (even a simple semi-transparent red rectangle drawn over the flagged region with Pillow/OpenCV is enough — it doesn't need real forensic computation to look convincing in a demo, since the mock is explicitly a stand-in for the teammate's real pipeline).

### F.4 Module 4 — Face Verification

**Purpose (from PS)**: ensure the document owner matches the presented individual.

**Two-part check**:
1. Document photo vs. live-captured face (the PS's literal requirement).
2. Live-captured face vs. watchlist database (our value-add extension).

**Mock implementation**: return a `similarity_score` (0.0–1.0) and `liveness_passed` (boolean). For embeddings, since a real face-recognition model isn't required for the mock, you can either (a) use a lightweight pretrained face-embedding model if one is easily available in the environment (e.g. `face_recognition` library, which wraps dlib), which would actually make this piece "real" rather than mocked with very little extra effort, or (b) if no such library is available, generate a deterministic pseudo-embedding as a hash-derived vector purely for demonstrating the matching *logic* (duplicate-check, watchlist-check) — clearly comment that this fallback does not represent real facial similarity.

**Fairness note (carried over from the earlier critique in this project's planning)**: if a real face-recognition model is used, note in the PPT that accuracy of face-matching models is known to vary across ethnicities (NIST has published studies on this), and that the India-Nepal border region's ethnic diversity (plainsfolk, Nepali-origin, Tibetan-origin communities) means this is a live fairness concern, not a hypothetical one. Mitigations to mention even if not fully implemented in the 1-day build: (1) use a face-recognition model benchmarked on diverse datasets rather than a generic Western-face-heavy dataset, (2) keep the human officer in the loop for all borderline/low-confidence matches rather than auto-rejecting, (3) track false-reject rates by region/demographic in production and retrain/re-threshold accordingly. This shows judges you've thought about the failure mode, which is a stronger answer than pretending the system is unbiased.

### F.5 Watchlist Matching (value-add)

Nearest-neighbor search of the live face embedding against `watchlist_faces.embedding`, using cosine similarity with a fixed threshold (e.g. > 0.85 = match, tune based on whatever embedding method F.4 actually uses). Admin panel lets you add/remove watchlist entries live during the demo — a good live-demo trick is to add the demo presenter's own photo to the watchlist right before the demo and then get "flagged" on stage.

### F.6 Duplicate-Verification, Travel-Direction, and Impossible-Travel Logic (value-add)

**Duplicate check**: query `verification_records` created in the last 2 hours where `doc_number` matches exactly AND cosine similarity of `live_face_embedding` exceeds threshold. Both conditions required (per your decision) — this avoids two failure modes: matching on doc number alone would misfire if two different people happen to share a malformed/misread doc number from OCR noise, and matching on face alone would misfire for identical twins or OCR-independent lookalikes claiming different documents (which is itself suspicious, but a different flag).

**Travel-direction check**: only evaluated if a duplicate match is found. Compare `travel_direction` values of the two records. Opposite values → consistent (a normal entry/exit pair). Same value repeated → flag "suspicious: same direction twice with no recorded opposite leg," since a real traveler cannot enter the same country twice in a row without leaving in between.

**Impossible-travel check**: only evaluated if a duplicate match is found. Compute the Haversine distance between the two records' (lat, long), divide by the time elapsed between their `created_at` timestamps, in hours, to get km/h. Compare against a plausible max threshold — use ~900 km/h (roughly commercial jet cruising speed) as the ceiling for "this could plausibly be the same person traveling by any real means"; anything above that is either a data error, a spoofed location, or two different people being incorrectly matched as one (which itself is useful signal — treat it as "needs officer review," not an automatic hard-reject).

### F.7 Risk Scoring

Composite score, 0–100, built as a simple weighted sum (exact weights are a judgment call — document them clearly in code comments so they can be tuned):

- Validation failures: +10 per failed rule
- Tampering score: `tampering_score * 40` (this should dominate, since it's the PS's "Core AI Innovation")
- Face mismatch: `(1 - similarity_score) * 30` if similarity_score is below a "high confidence" threshold, else 0
- Watchlist match: +100 (should always push to High regardless of anything else)
- Duplicate + suspicious travel direction: +20
- Impossible travel: +25

Cap at 100. Bands: 0–30 = Low, 31–65 = Medium, 66–100 = High.

Always return the `risk_breakdown_json` as an ordered list of `{factor, points, reason}` so the frontend can render an explainable bar chart / list — this is what makes the score trustworthy to an officer instead of a black box, which was explicitly named as a requirement in the original planning conversation.

---

## PART G — FRONTEND SPECIFICATION

### G.1 Pages/routes

- `/` — landing page, "Verify Document" button.
- `/verify/setup` — travel-direction dropdown + geolocation capture (auto-triggered, with a visible "Location captured ✓" confirmation).
- `/verify/capture` — document upload or camera capture.
- `/verify/pipeline/:sessionId` — the live timeline + thinking-log screen, WebSocket-driven.
- `/verify/face/:sessionId` — live camera face capture screen (auto-transitions here once document modules finish).
- `/verify/result/:sessionId` — final risk dashboard with Approve/Reject/Escalate buttons.
- `/audit` — a simple screen showing the hash-chain integrity check result (button: "Verify Audit Trail").
- `/admin/watchlist` — authenticated admin CRUD screen for watchlist photos.

### G.2 Pipeline screen component behavior

- Horizontal stepper: 4 circles/nodes labeled `OCR`, `Validation`, `Tampering`, `Face` (watchlist/duplicate/risk can be a 5th "Finalizing" node, or folded into a "Risk Assessment" 5th step — your call, keep it visually clean, don't cram all 7 backend stages into the visible stepper if it gets cluttered; 4-5 visible stages is the right amount).
- Each node: grey (pending) → animated pulse (active) → green check (passed) or red exclamation (flagged/failed).
- Log panel: monospace or clean sans-serif, auto-scrolling, each new WebSocket `log` line appended with a subtle fade-in/typewriter effect. Keep line delivery paced (even if the backend processes instantly, consider a small artificial delay, e.g. 300-600ms between log lines) purely for demo legibility — judges need to be able to read it, not have it flash by in 200ms total.

### G.3 Result dashboard layout

- Left: original document image with tampering heatmap overlay toggle.
- Right: extracted fields table, validation results, face match %, watchlist result.
- Bottom: risk score gauge/badge (Low=green, Medium=yellow, High=red) + explainable breakdown list.
- Footer: duplicate-check result, travel-direction status, impossible-travel status (only shown if a duplicate was found — otherwise show "No prior record found — first scan for this traveler").
- Action buttons: Approve / Reject / Escalate.

---

## PART H — BUILD SEQUENCING FOR A 1-DAY TIMELINE

Given only one day, sequence work so that at every hour there is *something* demoable, in case time runs out:

1. **Hour 0-1**: Scaffold FastAPI + Postgres + React. Get a "hello world" WebSocket round trip working.
2. **Hour 1-3**: Build all 4 mock module functions + the orchestration that calls them in sequence and streams WebSocket events. This alone gets you the core "wow" pipeline visual.
3. **Hour 3-4**: Build the upload/camera capture screens and wire them to the backend.
4. **Hour 4-5**: Build the result dashboard + risk scoring.
5. **Hour 5-6**: Add watchlist matching + admin panel.
6. **Hour 6-7**: Add geolocation capture + duplicate-check + travel-direction + impossible-travel logic.
7. **Hour 7-8**: Add the hash-chain table + `/verify-chain` endpoint + a simple audit screen.
8. **Remaining time**: polish the log-panel pacing/animation, prepare the two demo sample documents (genuine + tampered), rehearse the live demo script, swap in teammate's real modules if ready (should be a drop-in replacement of the mock functions given the fixed interface contract).

---

## PART I — DEMO SCRIPT (for the actual judge presentation)

1. Open landing page, select "Entering India," show geolocation auto-capture.
2. Upload the pre-prepared **genuine** sample document → walk through the pipeline live, narrate what each log line means → face capture (presenter's own face) → match succeeds → no watchlist hit → no prior record → Low risk, green.
3. Upload the pre-prepared **tampered** sample document → pipeline runs → tampering stage flags the DOB region with a visible heatmap → risk score jumps to High, red, with the explainable breakdown clearly showing "Tampering: 38/40 points."
4. Re-scan the same genuine document/face again within the 2-hour window → duplicate-check fires → show the "already verified" flag, plus travel-direction and impossible-travel results (rehearse this so both directions are demonstrated: one pass, e.g. presenter picks "Entering Nepal" the second time to show a valid pair, and if time allows, a second rehearsed run showing a same-direction/impossible-travel flag).
5. Open `/audit`, click "Verify Audit Trail," show the chain is intact. Optionally, in front of judges, manually edit a row directly in the database to simulate tampering, then re-run the check to show it now fails — this is a strong, concrete demonstration of the tamper-evidence property.
6. Close by mapping each PS challenge bullet back to the module that solved it (use the challenge-to-solution table already built earlier in this project's planning).

---

## PART J — EXPLICIT NON-GOALS (do not build these; time is the constraint)

- Real Hyperledger Fabric / any multi-node consensus system.
- Production-grade authentication, rate-limiting, or security hardening.
- Multi-checkpoint distributed sync or offline-first edge deployment (mentioned only as a roadmap talking point in the pitch, not built).
- Training any custom ML model from scratch — use the mock functions or lightweight pretrained libraries only.
- Native mobile apps — a responsive web app accessed via a mobile browser is sufficient for camera capture.
- Country-perfect document-format validation (e.g. exact regex for every country's passport number format) — a representative, demonstrable subset is sufficient.

---

## PART K — FINAL CHECKLIST BEFORE THE DEMO

- [ ] Upload OR camera-capture a document, both paths tested.
- [ ] Live WebSocket timeline + scrolling thinking-log through all pipeline stages, paced legibly.
- [ ] Live face capture + face-vs-document match working on a real device camera (test on the actual demo laptop/phone beforehand — camera permissions are a common last-minute failure).
- [ ] Watchlist match check demonstrable (presenter's face pre-loaded as a test entry).
- [ ] Geolocation + timestamp captured and stored per verification.
- [ ] Duplicate-check within the 2-hour window (face + doc number both required) works and has been rehearsed with a real repeat scan.
- [ ] Travel-direction consistency check demonstrated in both the "consistent" and "suspicious" states.
- [ ] Impossible-travel (Haversine speed) check demonstrated at least once.
- [ ] Explainable composite risk score dashboard renders correctly for both a Low and a High risk sample.
- [ ] Hash-chain logging + `/verify-chain` integrity check, including the "break it live" demo moment.
- [ ] Module interface layer confirmed clean enough that teammate's real modules can replace the mocks with no other code changes — test this explicitly if his modules are ready in time.
- [ ] Two prepared sample documents (genuine + tampered) tested end-to-end at least twice before presenting.
