# Phase 5C — Gate 2/3 Evidence Bundle Schema (Model B)

**Document Type:** Technical Specification  
**Gate:** Gate 2 — Source Recoverability + Gate 3 — Audit Completeness  
**Model:** Model B — External Source Recoverability  
**Status:** APPROVED  
**Date:** 2025-12-16  
**Schema Version:** `vm_evidence_schema:1.0`

---

## Design Goals

* **Deterministic** — same inputs produce same bundle structure
* **Testable** — schema can be validated programmatically
* **Diffable** — changes between runs are easily identified
* **Non-storing** — no original pixel data, no recovered PHI text
* **Hash-chained** — integrity verifiable at every level
* **Export-friendly** — easy to package as ZIP for FOI/audit

---

## Bundle Root Naming Convention

One processing run = one evidence bundle.

**Directory name format:**
```
EVIDENCE_<processing_run_id>_<YYYYMMDDThhmmssZ>/
```

Where:
- `processing_run_id` = UUID or stable run token
- Timestamp = ISO 8601 UTC format

**Example:**
```
EVIDENCE_f28ba6f8-7a9a-497c-83b8-5f61b5a31107_20251216T095500Z/
```

---

## Canonical Folder Structure

```
EVIDENCE_<run_id>_<timestampZ>/
├── MANIFEST.json
├── MANIFEST.sha256
├── CONFIG/
│   ├── profile.json
│   ├── profile.sha256
│   ├── app_build.json
│   ├── app_build.sha256
│   ├── runtime_env.json
│   └── runtime_env.sha256
├── INPUT/
│   ├── source_index.json
│   ├── source_index.sha256
│   ├── source_hashes.csv
│   └── source_hashes.sha256
├── OUTPUT/
│   ├── masked_index.json
│   ├── masked_index.sha256
│   ├── masked_hashes.csv
│   └── masked_hashes.sha256
├── DECISIONS/
│   ├── detection_results.jsonl
│   ├── detection_results.sha256
│   ├── masking_actions.jsonl
│   ├── masking_actions.sha256
│   ├── decision_log.jsonl
│   └── decision_log.sha256
├── LINKAGE/
│   ├── instance_linkage.csv
│   └── instance_linkage.sha256
├── QA/
│   ├── exceptions.jsonl
│   ├── exceptions.sha256
│   ├── verification_report.json
│   └── verification_report.sha256
└── SIGNATURE/
    ├── bundle_tree.txt
    └── bundle_tree.sha256
```

---

## File Definitions

### Root Level

#### `MANIFEST.json`

**Purpose:** Single source of truth for bundle completeness.

```json
{
  "schema_version": "vm_evidence_schema:1.0",
  "processing_run_id": "f28ba6f8-7a9a-497c-83b8-5f61b5a31107",
  "timestamps": {
    "processing_start": "2025-12-16T09:55:00Z",
    "processing_end": "2025-12-16T09:57:30Z",
    "bundle_generated": "2025-12-16T09:57:35Z"
  },
  "counts": {
    "studies_in": 1,
    "series_in": 3,
    "instances_in": 55,
    "instances_out": 55,
    "detections_total": 127,
    "instances_masked": 50,
    "instances_skipped": 5,
    "failures": 0
  },
  "files": [
    {
      "path": "CONFIG/profile.json",
      "sha256": "abc123...",
      "bytes": 1234
    }
  ],
  "constraints": {
    "stores_original_pixels": false,
    "stores_recovered_phi_text": false,
    "pacs_authoritative": true,
    "escrow_ref": null
  }
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `schema_version` | string | ✓ | Schema identifier |
| `processing_run_id` | string | ✓ | UUID for this run |
| `timestamps` | object | ✓ | Start, end, bundle generation times |
| `counts` | object | ✓ | Summary counts for verification |
| `files` | array | ✓ | List of all bundle files with hashes |
| `constraints` | object | ✓ | Model B constraint flags |

---

### CONFIG Directory

#### `CONFIG/profile.json`

```json
{
  "compliance_profile": "FOI",
  "profile_version": "1.0",
  "modality_zones": {
    "US": {"header_pct": 15, "footer_pct": 10},
    "CT": {"header_pct": 10, "footer_pct": 5}
  },
  "detection_thresholds": {
    "confidence_min": 0.5,
    "box_min_area": 100
  },
  "uid_strategy": "REGENERATE_DETERMINISTIC",
  "retention_policy_ref": "FOI_7_YEARS"
}
```

#### `CONFIG/app_build.json`

```json
{
  "voxelmask_version": "0.5.0",
  "git_commit": "6a64c22e12505bc4e4d84732dc28e5e72a46cdb8",
  "git_tag": "v0.5.0-gate2",
  "build_timestamp": "2025-12-16T08:00:00Z",
  "ocr_engine": "PaddleOCR",
  "ocr_engine_version": "2.7.0",
  "dependency_lock_hash": "sha256:9f8e7d..."
}
```

#### `CONFIG/runtime_env.json`

```json
{
  "python_version": "3.12.0",
  "platform": "Linux-6.1.52",
  "hostname_hash": "sha256:abc...",
  "operator_id": null
}
```

---

### INPUT Directory

#### `INPUT/source_index.json`

Inventory of source objects processed (no pixels):

```json
{
  "study_instance_uid": "1.2.840.113564.9.1.3080839390.85.2.5015705699",
  "study_description": "US Obstetric 3rd Trimester Growth",
  "series": [
    {
      "series_instance_uid": "1.2.392.200036.9116.6.18.17543328...",
      "modality": "US",
      "sop_class_uid": "1.2.840.10008.5.1.4.1.1.6.1",
      "instance_count": 43
    }
  ],
  "total_instances": 55
}
```

#### `INPUT/source_hashes.csv`

One line per SOP Instance:

```csv
source_sop_instance_uid,source_pixel_hash,source_series_uid,instance_number
1.2.392.200036.9116.6.18.17543328.1446...,sha256:67b336...,1.2.392.200036...,1
1.2.392.200036.9116.6.18.17543328.7890...,sha256:5a1293...,1.2.392.200036...,2
```

| Column | Required | Description |
|--------|----------|-------------|
| `source_sop_instance_uid` | ✓ | Original SOPInstanceUID |
| `source_pixel_hash` | ✓ | SHA-256 of pixel data (Model B backbone) |
| `source_series_uid` | ✓ | SeriesInstanceUID |
| `instance_number` | Optional | InstanceNumber if present |

---

### OUTPUT Directory

#### `OUTPUT/masked_index.json`

Inventory of masked outputs:

```json
{
  "study_instance_uid": "2.25.123456789...",
  "series": [
    {
      "series_instance_uid": "2.25.987654321...",
      "modality": "US",
      "instance_count": 43
    }
  ],
  "total_instances": 55
}
```

#### `OUTPUT/masked_hashes.csv`

```csv
masked_sop_instance_uid,masked_pixel_hash,masked_series_uid
2.25.111222333...,sha256:aabbcc...,2.25.987654321...
```

---

### DECISIONS Directory

#### `DECISIONS/detection_results.jsonl`

One JSON object per line, per detection finding:

```jsonl
{"source_sop_uid":"1.2.392...","frame_index":null,"region":"header","bbox":[10,5,200,30],"confidence":0.92,"engine":"PaddleOCR","engine_version":"2.7.0","ruleset_id":"US_HEADER_ZONE","config_hash":"sha256:def..."}
{"source_sop_uid":"1.2.392...","frame_index":null,"region":"footer","bbox":[10,480,150,20],"confidence":0.87,"engine":"PaddleOCR","engine_version":"2.7.0","ruleset_id":"US_FOOTER_ZONE","config_hash":"sha256:def..."}
```

**Explicitly excludes:**
- ❌ Extracted OCR text
- ❌ Screenshots / crops

#### `DECISIONS/masking_actions.jsonl`

One JSON object per line, per applied action:

```jsonl
{"masked_sop_uid":"2.25.111...","frame_index":null,"action_type":"black_box","bbox_applied":[10,5,200,30],"parameters":{"color":[0,0,0],"padding":2},"result":"success","reason":null}
{"masked_sop_uid":"2.25.111...","frame_index":null,"action_type":"black_box","bbox_applied":[10,480,150,20],"parameters":{"color":[0,0,0],"padding":2},"result":"success","reason":null}
```

#### `DECISIONS/decision_log.jsonl`

High-level decision records:

```jsonl
{"timestamp":"2025-12-16T09:55:10Z","decision_type":"MASK","source_sop_uid":"1.2.392...","masked_sop_uid":"2.25.111...","detections_count":3,"actions_count":3,"status":"complete"}
{"timestamp":"2025-12-16T09:55:11Z","decision_type":"SKIP","source_sop_uid":"1.2.392...","masked_sop_uid":null,"detections_count":0,"actions_count":0,"status":"no_phi_detected"}
```

---

### LINKAGE Directory

#### `LINKAGE/instance_linkage.csv`

Hard linkage table for provenance:

```csv
source_study_uid,source_series_uid,source_sop_uid,masked_study_uid,masked_series_uid,masked_sop_uid,uid_strategy,deterministic_salt_id
1.2.840.113564...,1.2.392.200036...,1.2.392.200036...,2.25.123456...,2.25.987654...,2.25.111222...,REGENERATE_DETERMINISTIC,salt_001
```

| Column | Required | Description |
|--------|----------|-------------|
| `source_study_uid` | ✓ | Original StudyInstanceUID |
| `source_series_uid` | ✓ | Original SeriesInstanceUID |
| `source_sop_uid` | ✓ | Original SOPInstanceUID |
| `masked_study_uid` | ✓ | Output StudyInstanceUID |
| `masked_series_uid` | ✓ | Output SeriesInstanceUID |
| `masked_sop_uid` | ✓ | Output SOPInstanceUID |
| `uid_strategy` | ✓ | UID generation strategy used |
| `deterministic_salt_id` | Optional | Salt identifier (NOT the salt value) |

---

### QA Directory

#### `QA/exceptions.jsonl`

Every non-happy-path event:

```jsonl
{"timestamp":"2025-12-16T09:55:15Z","exception_type":"SOURCE_READ_FAILURE","source_sop_uid":"1.2.392...","message":"Corrupted pixel data","severity":"ERROR"}
{"timestamp":"2025-12-16T09:56:00Z","exception_type":"DETECTION_LOW_CONFIDENCE","source_sop_uid":"1.2.392...","message":"Confidence 0.3 below threshold","severity":"WARNING"}
```

#### `QA/verification_report.json`

Summary verification result:

```json
{
  "verification_id": "uuid...",
  "verification_timestamp": "2025-12-16T09:57:35Z",
  "verification_status": "verified",
  "checks": {
    "manifest_integrity": "PASS",
    "file_hashes_valid": "PASS",
    "linkage_complete": "PASS",
    "decision_coverage": "PASS"
  },
  "mismatches": [],
  "tool_version": "0.5.0"
}
```

| Status | Meaning |
|--------|---------|
| `verified` | All checks passed |
| `unverifiable` | Source unavailable for verification |
| `failed` | Integrity or completeness check failed |

---

### SIGNATURE Directory

#### `SIGNATURE/bundle_tree.txt`

Deterministic file listing (sorted, for audit):

```
CONFIG/app_build.json sha256:abc123... 512
CONFIG/app_build.sha256 sha256:def456... 64
CONFIG/profile.json sha256:789xyz... 1024
...
```

---

## Hashing Rules

| Rule | Description |
|------|-------------|
| Every substantive file gets `*.sha256` | Hash file next to content file |
| MANIFEST includes all file hashes | Central integrity reference |
| Hashes are SHA-256 | Cryptographic, non-reversible |
| bundle_tree.txt derived from MANIFEST | Human-readable view |

**Canonical source:** `MANIFEST.json` is authoritative; `bundle_tree.txt` is derived.

---

## Model B Constraint Enforcement

This schema enforces Model B by design:

| Constraint | How Enforced |
|------------|--------------|
| No original pixel data | Only hashes stored (`source_pixel_hash`) |
| No recovered PHI text | Detection results store bbox only, no text |
| PACS authoritative | `pacs_authoritative: true` in MANIFEST |
| Verifiable linkage | `instance_linkage.csv` enables PACS verification |

---

## Gate 3 Integration

Gate 3 "Audit Completeness" validates against this schema:

| Check | Validation |
|-------|------------|
| Coverage completeness | MANIFEST counts match index/linkage row counts |
| Decision completeness | Every masked instance has ≥1 action OR explicit skip |
| Evidence completeness | Every source instance has hash; every output has linkage |
| Config completeness | profile + build + runtime files exist and hash-valid |
| Integrity completeness | All file hashes validate; MANIFEST hash validates |
| Retention completeness | retention_policy_ref present |

---

## Related Documents

* `PHASE5C_GATE2_DECISION_RECORD.md` — Model B selection rationale
* `PHASE5C_GATE2_ARTIFACT_CHECKLIST.md` — Evidence requirements checklist
* `PHASE5C_GATE3_AUDIT_COMPLETENESS.md` — Audit completeness specification

---

**End of Evidence Bundle Schema**
