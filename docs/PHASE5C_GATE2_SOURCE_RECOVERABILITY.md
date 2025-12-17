# Gate 2 — Source Recoverability

**Document Type:** Governance Gate Specification  
**Status:** EXECUTED — APPROVED FOR IMPLEMENTATION  
**Gate Purpose:** Ensure audit-grade proof of what was detected and changed, without storing recoverable original pixels.  
**Blocks:** All masking/pixel mutation work (along with Gate 1).

---

## Table of Contents

1. [Decision Record](#1-decision-record)
2. [Threat & Governance Framing](#2-threat--governance-framing)
3. [Guiding Principle](#3-guiding-principle)
4. [Artefact Taxonomy](#4-artefact-taxonomy)
5. [Integrity Model](#5-integrity-model)
6. [Ordering & Cine Preservation](#6-ordering--cine-preservation)
7. [Retention & Governance Fields](#7-retention--governance-fields)
8. [Explicit Non-Goals](#8-explicit-non-goals)
9. [Gate 2 Pass Criteria](#9-gate-2-pass-criteria)
10. [Phase Boundary](#10-phase-boundary)

---

## 1. Decision Record

### 1.1 Model Selected

**Model B — External Source Recoverability (Audit-Proof, No Original Pixels)**

VoxelMask will **not** retain recoverable original pixel data or reversible diffs internal to the application. Instead, Gate 2 produces **audit-grade proof artefacts** that demonstrate:

- What was detected
- What was changed
- How to reproduce the decision trail

This model relies on the **External Source (PACS)** being available if full clinical recovery is legally required. VoxelMask provides the *linkage* and *proof*, but not the *pixels*.

### 1.2 Models Considered

| Model | Description | Decision |
|-------|-------------|----------|
| **Model A: Internal Recoverability** | Store original pixels or reversible diffs in a quarantine archive/escrow. | ❌ Rejected |
| **Model B: External Source Recoverability** | No pixels stored. Audit proof via hashes, overlays, decision records. Relies on external PACS. | ✅ **SELECTED** |
| **Model C: Irrecoverable / Destructive** | Anonymize fully, breaking links to source. No audit trail back to specific original instances. | ❌ Rejected |

### 1.3 Rejection Rationale

| Rejected Model | Reason |
|----------------|--------|
| **Model A (Internal)** | Creates a shadow PHI store; increases liability surface; harder to defend in acquisition; turns VoxelMask into a "Vault". |
| **Model C (Destructive)** | Fails FOI/Legal defensibility ("What did you change?"); unsafe for Pilot (cannot investigate issues); creates "orphan" data. |

### 1.4 Selection Rationale

Model B (External Recoverability) is selected because:

- **Vendor-safe:** No PHI escrow means simpler data protection posture.
- **Governance-friendly:** Audit proof without reversibility is defensible.
- **Acquisition-clean:** External reviewers can verify integrity without accessing PHI.
- **Pilot-appropriate:** Reduces risk surface during initial deployment ("Copy-Out Only").

---

## 2. Threat & Governance Framing

### 2.1 Threats Model B Addresses

| Threat | How Model B Mitigates |
|--------|----------------------|
| "What did you mask?" challenge | Hash primitives prove mutation occurred; overlay shows geometry. |
| Decision trail tampering | Signed manifests with Ed25519; append-only logs. |
| Overly broad masking claim | Region-level records show exactly what was flagged. |
| Algorithm version disputes | Config snapshots frozen per-run. |
| Order manipulation claims | Series order table proves sequence preservation. |

### 2.2 Threats Model B Does NOT Address (By Design)

| Threat | Why Not Addressed |
|--------|-------------------|
| "Show me the original pixels" | Explicit non-goal; auditor sees proof, not PHI. Auditor must go to PACS. |
| "Unmask this export" | Cannot unmask; this is a feature, not a limitation. |
| Post-hoc PHI recovery | No PHI stored = no recovery possible by VoxelMask alone. |

### 2.3 Why "External Recoverability" is Safer

| Context | Internal Recovery Risk (Model A) | External Recovery Benefit (Model B) |
|---------|------------------------|------------------------|
| **FOI Legal** | Shadow store may itself become FOI-discoverable. | No shadow store = nothing to discover in VoxelMask. |
| **Pilot** | Recoverable PHI increases breach severity. | No PHI retention = reduced severity. |
| **Acquisition** | Auditors must assess PHI handling practices. | Simpler story: "We don't keep it." |
| **Research** | IRB may require controls on original data. | No original data = no additional IRB burden. |

---

## 3. Guiding Principle

> **No pixel mutation may be enabled unless the system can produce audit-grade proof of what was detected and what was changed, without storing recoverable original content.**

This is about **evidence and defensibility**, not undo functionality.

---

## 4. Artefact Taxonomy

Gate 2 produces the following first-class artefacts per job run:

### 4.1 Job Manifest

**Table:** `gate2_job_manifest`

| Field | Type | Purpose |
|-------|------|---------|
| `job_id` | UUID | Primary identifier |
| `run_id` | UUID | Allows re-runs within job |
| `created_at` | ISO8601 | Timestamp (local + UTC) |
| `operator` | Text | Optional operator identifier |
| `host_fingerprint` | Hash | Machine identification |
| `voxelmask_version` | Text | Git tag + commit |
| `profile_id` | Enum | clinical / research / FOI-patient / FOI-legal |
| `input_source` | Text | Folder path / DICOM AE / "imported zip" |
| `copy_out_only` | Bool | Must be true in pilot |
| `config_snapshot_json` | JSON | Frozen config for this run |
| `dicom_read_summary_json` | JSON | Counts by modality/SOP class |
| `processing_summary_json` | JSON | Flagged/masked/skipped/error counts |
| `overall_status` | Enum | success / partial / fail |
| `signing_hash` | Hash | Integrity reference |

### 4.2 Object Decision Record

**Table:** `gate2_object_record`

One row per SOP Instance processed (or discovered, even if skipped).

#### Identity Fields

| Field | Type | Purpose |
|-------|------|---------|
| `job_id` | UUID | FK to manifest |
| `run_id` | UUID | FK to manifest |
| `study_key` | HMAC | Derived from StudyInstanceUID |
| `series_key` | HMAC | Derived from SeriesInstanceUID |
| `sop_key` | HMAC | Derived from SOPInstanceUID |
| `modality` | Text | DICOM modality |
| `sop_class_uid` | UID | SOP Class |
| `transfer_syntax_uid` | UID | Input transfer syntax |
| `instance_number` | Int | For ordering/cine preservation |

#### Processing Outcome Fields

| Field | Type | Purpose |
|-------|------|---------|
| `action_taken` | Enum | NO_CHANGE / METADATA_ONLY / PIXEL_MASKED / SKIPPED_UNSUPPORTED / FAILED |
| `reason_codes` | Array | e.g., ["BURNED_IN_PHI_DETECTED", "PROFILE_REQUIRES_MASKING"] |
| `error_detail` | Text | Nullable; error message if failed |

#### Metadata Anonymisation Proof

| Field | Type | Purpose |
|-------|------|---------|
| `phi_tags_touched_json` | JSON | List of tags rewritten |
| `uids_regenerated_json` | JSON | Which UIDs changed + method |
| `dates_shifted` | Bool | Whether date shifting applied |
| `shift_strategy_id` | Text | Date shift method identifier |
| `patient_name_strategy_id` | Text | e.g., "hash-pseudonym-v1" |

#### Pixel Masking Proof (No Pixels Stored)

| Field | Type | Purpose |
|-------|------|---------|
| `pixel_changed` | Bool | Whether pixel data was modified |
| `mask_plan_id` | UUID | FK to mask plan |
| `pixel_before_hash` | SHA256 | Hash of input PixelData bytes |
| `pixel_after_hash` | SHA256 | Hash of output PixelData bytes |
| `dataset_before_hash` | SHA256 | Hash of DICOM dataset (excl. PixelData) |
| `dataset_after_hash` | SHA256 | Hash of output dataset (excl. PixelData) |

> These hashes are "courtroom primitives": they prove *something changed* and allow integrity checks without retaining recoverable content.

#### Timing Fields

| Field | Type | Purpose |
|-------|------|---------|
| `processed_at` | ISO8601 | When this instance was processed |
| `processing_time_ms` | Int | Processing duration |

### 4.3 Mask Plan

**Table:** `gate2_mask_plan`

The **replayable instruction set**, not the image.

| Field | Type | Purpose |
|-------|------|---------|
| `mask_plan_id` | UUID | Primary identifier |
| `job_id` | UUID | FK to manifest |
| `run_id` | UUID | FK to manifest |
| `sop_key` | HMAC | FK to object record |
| `engine_id` | Text | tesseract / easyocr / "none" |
| `engine_version` | Text | Engine version string |
| `detection_strength` | Enum | none / low / medium / high |
| `zones_used` | Array | header / footer / body |
| `thresholds_snapshot_json` | JSON | Thresholds applied |
| `regions_json` | JSON | List of regions (see below) |
| `render_strategy` | Enum | black_box / blur / solid_fill |
| `notes` | Text | Optional notes |

#### Region Record Schema (within `regions_json`)

```json
{
  "region_id": "uuid",
  "shape": "RECT | POLY",
  "coords": {"x": 0, "y": 0, "w": 100, "h": 20},
  "label": "NAME | DOB | MRN | UNKNOWN_TEXT",
  "confidence": 0.95,
  "zone": "HEADER | FOOTER | BODY",
  "rule_id": "string"
}
```

### 4.4 Evidence Pack

**Table:** `gate2_evidence_blob`

Index of filesystem blobs containing de-identified evidence.

| Field | Type | Purpose |
|-------|------|---------|
| `evidence_id` | UUID | Primary identifier |
| `job_id` | UUID | FK to manifest |
| `run_id` | UUID | FK to manifest |
| `sop_key` | HMAC | FK to object record |
| `type` | Enum | See below |
| `content_sha256` | Hash | Content integrity |
| `byte_size` | Int | File size |
| `path` | Text | Relative path to blob |
| `redaction_level` | Enum | SAFE_FOR_AUDIT / CONTAINS_PHI |

#### Evidence Types

| Type | Description | PHI Risk |
|------|-------------|----------|
| `DETECTION_OVERLAY_PNG` | Bounding boxes without underlying text | Safe |
| `MASKED_OUTPUT_PREVIEW_PNG` | Preview of masked output | Safe |
| `OCR_TEXT_SNIPPETS_JSON` | Raw OCR text | ⚠️ Contains PHI |
| `DICOM_HEADER_DIFF_JSON` | Tag diffs (old values omitted) | Safe |

**Strong recommendation:** Store only overlays/previews that are already de-identified. Avoid raw OCR text unless PHI-safe.

### 4.5 Signature Record

**Table:** `gate2_signature`

Tamper-evident signed manifest.

| Field | Type | Purpose |
|-------|------|---------|
| `job_id` | UUID | FK to manifest |
| `run_id` | UUID | FK to manifest |
| `manifest_hash_sha256` | Hash | Hash of manifest record |
| `records_merkle_root` | Hash | Optional Merkle root of all records |
| `signed_at` | ISO8601 | Signing timestamp |
| `signing_key_id` | Text | Key version identifier |
| `signature` | Bytes | Ed25519 signature (recommended) |

---

## 5. Integrity Model

### 5.1 Hash Primitives

All integrity checks use **SHA-256**.

| Hash Target | Purpose |
|-------------|---------|
| PixelData bytes (before) | Prove original content existed |
| PixelData bytes (after) | Prove what was written |
| DICOM dataset (excl. pixels) | Prove metadata state |
| Manifest content | Prove run configuration |
| Evidence blobs | Prove evidence integrity |

### 5.2 HMAC-Derived Keys

To keep identifiers stable across reruns while avoiding PHI correlation:

```
study_key  = HMAC_SHA256(secret, StudyInstanceUID)
series_key = HMAC_SHA256(secret, SeriesInstanceUID)
sop_key    = HMAC_SHA256(secret, SOPInstanceUID)
```

> Use **HMAC** (not plain hash) so keys cannot be reversed or correlated outside your environment.

### 5.3 Signing

**Recommended:** Ed25519 digital signatures.

**Minimum:** SHA-256 manifest hash + append-only logs.

Ed25519 signing is a significant acquisition-readiness win.

---

## 6. Ordering & Cine Preservation

### 6.1 Series Order Table

**Table:** `gate2_series_order`

| Field | Type | Purpose |
|-------|------|---------|
| `job_id` | UUID | FK to manifest |
| `run_id` | UUID | FK to manifest |
| `series_key` | HMAC | Series identifier |
| `sort_strategy` | Enum | INSTANCE_NUMBER / ACQ_TIME / ORIGINAL_FILE_ORDER |
| `ordered_sop_keys_json` | JSON Array | Ordered list of sop_keys |
| `notes` | Text | Optional |

### 6.2 Per-Object Order Fields

In `gate2_object_record`:

| Field | Purpose |
|-------|---------|
| `instance_number` | DICOM Instance Number |
| `acquisition_datetime` | Acquisition time (if present) |
| `original_ingest_index` | Order files were read |

This enables reconstruction of scroll order and ensures exports maintain order (Gate 1 ↔ Gate 2 linkage).

---

## 7. Retention & Governance Fields

### 7.1 Manifest Retention Fields

| Field | Type | Purpose |
|-------|------|---------|
| `retention_policy_id` | Text | e.g., "PILOT_30D", "FOI_7Y" |
| `purge_after` | Date | When data may be deleted |
| `contains_phi_evidence` | Bool | Should be false if overlay-only |

### 7.2 Retention Policies (Examples)

| Policy ID | Retention | Use Case |
|-----------|-----------|----------|
| `PILOT_30D` | 30 days | Pilot testing |
| `RESEARCH_1Y` | 1 year | Research projects |
| `FOI_7Y` | 7 years | FOI legal requirements |

### 7.3 Expiry Behaviour

- Expiry must be **logged**, not silent
- Purge operations must be **recorded in audit trail**
- Evidence blobs deleted, but **signature record retained** (proves data existed)

---

## 8. Explicit Non-Goals

Gate 2 (Model B) explicitly does **NOT** provide:

| Non-Goal | Rationale |
|----------|-----------|
| Original pixel recovery | Creates PHI escrow; increases liability |
| Unmasking capability | Governance risk; not a clinical system |
| Live rollback / undo | Not a workflow feature |
| PACS write-back | Explicitly forbidden |
| PHI retention | Violates Model B principle |
| Recovery UI | Not required for audit defensibility |
| Operator self-service recovery | Not required |

**These are features we are choosing NOT to build.**

---

## 9. Gate 2 Pass Criteria

Gate 2 may be marked **PASSED** when:

| # | Criterion | Verification |
|---|-----------|--------------|
| 9.1 | Model B explicitly selected and documented | This document |
| 9.2 | All artefact schemas defined | Sections 4.1–4.5 |
| 9.3 | Integrity model specified (hashes, HMAC, signing) | Section 5 |
| 9.4 | Ordering preservation covered | Section 6 |
| 9.5 | Retention behaviour specified | Section 7 |
| 9.6 | Non-goals explicitly stated | Section 8 |
| 9.7 | Independent reviewer can answer: "Can you prove what was changed?" | Artefacts + hashes |

If any answer is "maybe" → **Gate 2 NOT PASSED**

---

## 10. Phase Boundary

### 10.1 Current Status

| Item | Status |
|------|--------|
| Model decision | ✅ Approved (Model B) |
| Artefact schema | ✅ Approved |
| Integrity model | ✅ Approved |
| Design document | ✅ Persisted |
| Implementation | ✅ **EXECUTED / AUTHORIZED** |

### 10.2 Next Actions

Implementation phase authorized to produce:

1. `schema.sql` — SQLite table definitions
2. Pydantic models — Python dataclasses for each artefact
3. `gate2_write_artefacts()` — Unit-testable function
4. Integration tests — Verify artefact generation

---

## Relationship to Other Gates

| Gate | Dependency |
|------|------------|
| Gate 1 (Series Order) | Must be PASSED before Gate 2 execution |
| Gate 2 (Source Recoverability) | Must be PASSED before masking |
| Gate 3 (Audit Completeness) | Builds on Gate 2 artefacts |

---

**Document Status:** EXECUTED  
**Gate Status:** 🟢 PASSED  
