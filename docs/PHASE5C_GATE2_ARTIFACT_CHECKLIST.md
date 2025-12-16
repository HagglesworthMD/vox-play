# Gate 2 — Artifact Checklist (Model B)

**Document Type:** Evidence Requirements Specification  
**Gate:** Gate 2 — Source Recoverability  
**Model Selected:** Model B — External Source Recoverability  
**Status:** APPROVED  
**Date:** 2025-12-16

---

## Purpose

Define the **minimum sufficient evidence set** VoxelMask must produce and retain to support Model B recoverability and audit defensibility.

This checklist feeds **directly into Gate 3 — Audit Completeness**.

---

## 1. Provenance Evidence (Source → Masked)

VoxelMask MUST record, per processing run:

### Instance-level linkage

| Field | Description | Required |
|-------|-------------|----------|
| `source_study_instance_uid` | Original StudyInstanceUID | ✓ |
| `source_series_instance_uid` | Original SeriesInstanceUID | ✓ |
| `source_sop_instance_uid` | Original SOPInstanceUID | ✓ |
| `masked_sop_instance_uid` | Output SOPInstanceUID (may be regenerated) | ✓ |

### Integrity fingerprints (non-reversible)

| Field | Description | Required |
|-------|-------------|----------|
| `source_pixel_hash` | SHA-256 of pixel data, per SOP Instance, pre-mask | ✓ |
| `source_series_hash` | Aggregate hash for quick series integrity check | Optional |
| `source_study_hash` | Aggregate hash for quick study integrity check | Optional |

> ⚠️ Hashes MUST be cryptographic and non-reversible.  
> ⚠️ No pixel data stored.

---

## 2. Detection Evidence (What Was Found)

VoxelMask MUST record **what was detected without persisting PHI**:

### OCR / Detection metadata

| Field | Description | Required |
|-------|-------------|----------|
| `detection_engine` | Engine name (e.g., "PaddleOCR", "Tesseract") | ✓ |
| `detection_engine_version` | Engine version string | ✓ |
| `model_identifier` | Model/ruleset used | ✓ |
| `configuration_hash` | Hash of detection config | ✓ |
| `detection_timestamp` | ISO 8601 UTC timestamp | ✓ |

### Detection results (per finding)

| Field | Description | Required |
|-------|-------------|----------|
| `bounding_box` | Coordinates (x, y, width, height) in pixels or relative | ✓ |
| `region_zone` | Classification (header / footer / body / worksheet) | ✓ |
| `confidence` | Detection confidence (0.0-1.0) or bucket | ✓ |
| `modality_context` | Modality (US / CT / MR / SC, etc.) | ✓ |
| `instance_sop_uid` | Which instance this finding belongs to | ✓ |

> ❌ **MUST NOT** store recovered text strings  
> ✅ Location + confidence only

---

## 3. Action Evidence (What Was Done)

For each detection:

| Field | Description | Required |
|-------|-------------|----------|
| `mask_action_type` | Type: black_box / blur / replace / remove_overlay | ✓ |
| `mask_parameters` | Colour, opacity, kernel size, padding | ✓ |
| `applied_coordinates` | Final mask coordinates applied | ✓ |
| `action_status` | success / skipped / failed | ✓ |
| `skip_reason` | If skipped, why (e.g., user override) | If applicable |

---

## 4. Processing Context

Per run:

| Field | Description | Required |
|-------|-------------|----------|
| `processing_run_id` | UUID for this processing session | ✓ |
| `voxelmask_version` | Application version / build hash | ✓ |
| `compliance_profile` | Profile applied (FOI / patient / research) | ✓ |
| `uid_strategy` | UID regeneration strategy identifier | ✓ |
| `processing_mode` | Mode (copy-out only / clinical correction) | ✓ |
| `operator_id` | Operator identifier (optional, per policy) | Optional |

---

## 5. Verification Support

VoxelMask MUST enable **external verification**, including:

### Stored Evidence

| Artefact | Description | Required |
|----------|-------------|----------|
| `evidence_bundle_hash` | SHA-256 of complete evidence bundle | ✓ |
| `per_artefact_hashes` | Individual hashes for logs, manifests | ✓ |
| `baseline_order_manifest_hash` | Link to Gate 1 evidence | ✓ |

### Provided Tooling (or documented procedure)

VoxelMask MUST provide verification capability that:

1. Re-hashes original PACS instance
2. Compares to stored `source_pixel_hash`
3. Confirms detection evidence alignment
4. Confirms mask actions match evidence

This may be:
- Automated verification script
- Documented manual procedure
- API endpoint for verification

---

## 6. Failure & Limitation States

VoxelMask MUST explicitly record:

| State | Description | Required |
|-------|-------------|----------|
| `source_inaccessible` | Original not available at verification time | ✓ |
| `partial_detection` | Detection confidence below threshold | ✓ |
| `masking_skipped` | Masking skipped and reason | ✓ |
| `verification_status` | verified / unverifiable / failed | ✓ |
| `failure_reason` | If failed, detailed reason | If applicable |

---

## 7. Retention & Scope

| Policy | Description |
|--------|-------------|
| Retention duration | Configurable per compliance profile |
| Evidence classification | Audit metadata, NOT PHI |
| Purge controls | No automatic purge without governance approval |
| FOI defensibility | Evidence retained for FOI response period |

---

## 8. Explicit Non-Artefacts (By Design)

VoxelMask SHALL NOT store:

| Prohibited | Rationale |
|------------|-----------|
| Original pixel data | Model B constraint |
| Reversible pixel deltas | Would enable reconstruction |
| OCR-recovered PHI text | PHI persistence risk |
| Encryption keys for pixel recovery | Would enable reconstruction |

---

## Summary (Why This Works)

This artefact set ensures VoxelMask can say:

> "We did not retain identifiable images.  
> Here is cryptographic proof of what source was processed,  
> here is exactly what we detected and masked,  
> and here is how you can independently verify it against PACS."

That is **Model B done properly**.

---

## Gate 3 Integration

This checklist defines the **"what"** for Gate 3 — Audit Completeness.

Gate 3 will verify:
- All required fields are captured in implementation
- Evidence schema matches this specification
- Verification tooling exists and functions
- No prohibited artefacts are stored

---

**End of Gate 2 Artifact Checklist**
