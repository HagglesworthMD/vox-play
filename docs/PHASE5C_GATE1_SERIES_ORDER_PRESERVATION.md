# Gate 1 — Series Order Preservation

**Document Type:** Governance Gate Specification  
**Status:** DESIGN COMPLETE — Ready for Execution  
**Gate Purpose:** Ensure exported studies are faithful, ordered representations of source studies  
**Blocks:** All masking/pixel mutation work

---

## Table of Contents

1. [Satisfaction Plan](#1-satisfaction-plan)
2. [Canonical Definition of Series Order](#2-canonical-definition-of-series-order)
3. [Audit Artefact Schema](#3-audit-artefact-schema)
4. [Test Dataset Specifications](#4-test-dataset-specifications)
5. [Automated Assertions](#5-automated-assertions)
6. [Evidence Checklist (Operator-Facing)](#6-evidence-checklist-operator-facing)
7. [Gate Sign-Off](#7-gate-sign-off)

---

## 1. Satisfaction Plan

### 1.1 What "Passing Gate 1" Means (Precisely)

Gate 1 is satisfied **only if all of the following are true**:

1. Exported images preserve **source frame order**
2. Any excluded frames are:
   - Explicitly documented
   - Positionally traceable
3. Multi-frame (cine) content remains:
   - Ordered
   - Playable
4. The system can **prove** the above with artefacts, not assurances

Gate 1 does **not** care whether masking exists.  
It must be satisfiable with **zero pixel mutation**.

### 1.2 Required System Behaviours

#### Source Order Capture (Pre-Export)

Before any export action:
- The system captures a **Source Order Manifest** containing:
  - SOPInstanceUID
  - Instance Number
  - Frame index (if applicable)
  - Original position in series

This manifest is:
- Immutable for the session
- Stored with the ReviewSession
- Referenced by all downstream steps

#### Export Order Enforcement

During export:
- Output sequence **must be generated from the Source Order Manifest**
- Export logic **may not re-sort independently**
- Any frame not exported must:
  - Leave a positional gap
  - Be explicitly logged

**Silent reordering is a HARD FAILURE.**

#### Cine / Multi-Frame Handling

For multi-frame objects:
- Frame index order must be preserved exactly
- Frame count must match source unless explicitly excluded
- Exclusions must identify frame indices and preserve remaining order
- Exported cine must be verifiably playable in a reference viewer

### 1.3 Explicit Non-Acceptable Shortcuts (Fail Conditions)

Gate 1 **fails immediately** if any of the following are true:

- Export relies on filesystem order
- Export re-sorts based on filename
- Frame order differs between UI and export
- Excluded frames are silently dropped
- Cine playback is "mostly correct"
- Order is assumed because no one complained

These are **trust failures**, not bugs.

---

## 2. Canonical Definition of Series Order

### 2.1 Primary Ordering Keys (in precedence order)

1. **Instance Number (0020,0013)**
2. **Frame Number** (for multi-frame objects)
3. **Acquisition Time / Content Time** (tie-break only)
4. **Original ingest sequence** (last-resort fallback, logged)

This definition is:
- Documented (here)
- Fixed
- Used consistently across export, audit, and UI

**Governance boundary:** Ad-hoc or "best available" ordering fails the gate.

---

## 3. Audit Artefact Schema

### 3.1 Source Order Manifest

```python
@dataclass
class SourceOrderManifest:
    """Immutable record of source study order at ingest."""
    
    # Identification
    manifest_id: str              # UUID, generated once
    capture_timestamp: str        # ISO 8601 UTC
    series_instance_uid: str      # Source SeriesInstanceUID
    study_instance_uid: str       # Source StudyInstanceUID
    
    # Ordering Keys
    entries: List[SourceOrderEntry]
    
    # Integrity
    manifest_hash: str            # SHA-256 of serialized entries
    
    # Metadata
    total_count: int              # Total frames/instances
    is_multiframe: bool           # True if contains multi-frame objects
    ordering_method: str          # "INSTANCE_NUMBER" | "FRAME_INDEX" | "FALLBACK_INGEST"


@dataclass
class SourceOrderEntry:
    """Single frame/instance in source order."""
    
    source_index: int             # 1-indexed position in source order
    sop_instance_uid: str         # SOPInstanceUID
    instance_number: Optional[int]  # (0020,0013) - primary key
    frame_number: Optional[int]   # For multi-frame objects (1-indexed)
    acquisition_time: Optional[str]  # Tie-break only
    content_time: Optional[str]   # Tie-break only
    
    # Integrity (optional; presence enhances evidence but not required for Gate 1)
    pixel_hash: Optional[str]     # SHA-256 of pixel data
```

**Immutability Rule:** Once created, a SourceOrderManifest cannot be modified or regenerated for the same session.

### 3.2 Export Order Manifest

```python
@dataclass
class ExportOrderManifest:
    """Record of exported study order with source mapping."""
    
    # Identification
    manifest_id: str              # UUID, generated at export
    export_timestamp: str         # ISO 8601 UTC
    source_manifest_id: str       # Links to SourceOrderManifest
    source_manifest_hash: str     # Integrity check
    
    # Export Mapping
    entries: List[ExportOrderEntry]
    
    # Integrity
    manifest_hash: str            # SHA-256 of serialized entries
    
    # Summary
    total_exported: int           # Count of exported frames
    total_excluded: int           # Count of excluded frames
    order_preserved: bool         # Automated assertion result


@dataclass  
class ExportOrderEntry:
    """Single frame/instance in export order."""
    
    export_index: int             # 1-indexed position in export
    source_index: int             # Corresponding source_index
    sop_instance_uid: str         # SOPInstanceUID (may be remapped)
    original_sop_instance_uid: str  # Original SOPInstanceUID
    instance_number: int          # Preserved from source
    frame_number: Optional[int]   # For multi-frame
    
    # Disposition
    disposition: str              # "EXPORTED" | "EXCLUDED"
    exclusion_reason: Optional[str]  # If excluded, human-readable reason
    
    # Integrity
    pixel_hash: Optional[str]     # SHA-256 of exported pixel data


class ExclusionReasonCode(Enum):
    WORKSHEET_DETECTED = "Worksheet/document detected"
    USER_DESELECTED = "User explicitly deselected"
    PDF_ENCAPSULATED = "Encapsulated PDF excluded per policy"
    CORRUPTED_FRAME = "Frame failed integrity check"
```

### 3.3 Order Verification Record

```python
@dataclass
class OrderVerificationRecord:
    """Automated verification result for Gate 1."""
    
    verification_id: str          # UUID
    verification_timestamp: str   # ISO 8601 UTC
    
    # References
    source_manifest_id: str
    export_manifest_id: str
    
    # Results
    order_preserved: bool         # Primary assertion
    frame_count_match: bool       # No duplication/omission
    hash_integrity_valid: bool    # Pixel hashes match
    
    # Detailed Assertions
    assertions: List[OrderAssertion]
    
    # Manual verification (for cine)
    manual_verification_path: Optional[str]  # Path to screenshot/video
    
    # Overall
    gate_passed: bool             # All assertions true
    failure_reasons: List[str]    # If failed, why


@dataclass
class OrderAssertion:
    """Individual assertion result."""
    
    assertion_name: str           # e.g., "source_export_index_match"
    passed: bool
    expected: str
    actual: str
    message: str                  # Human-readable explanation
```

### 3.4 Artefact Storage Requirements

| Artefact | Format | Storage Location | Retention |
|----------|--------|------------------|-----------|
| Source Order Manifest | JSON | ReviewSession / SQLite | Session lifetime + export |
| Export Order Manifest | JSON | Export package / SQLite | Permanent |
| Order Verification Record | JSON | SQLite | Permanent |
| Human-Readable Summary | TXT | Export package | Permanent |

**Note:** Artefacts must be read-only once collected.

---

## 4. Test Dataset Specifications

### 4.1 Dataset A — Ordered Single-Frame Series (Baseline)

| Property | Value |
|----------|-------|
| Modality | CT (or MR) |
| Series Size | 12 images |
| SOP Class | Standard single-frame image storage |
| Instance Numbers | 1, 2, 3, ..., 12 |
| Exclusions | None |
| Expected outcome | 100% order preservation |

**Purpose:** Prove that a simple, single-frame series exports exactly in source order.

### 4.2 Dataset B — Multi-Frame Cine Object (Critical)

| Property | Value |
|----------|-------|
| Modality | US or XA |
| SOP Class | Multi-frame image storage |
| Frame Count | 20 frames |
| Frame Indices | 1–20 (known, fixed) |
| Content | Visually distinguishable frames (frame index burned into pixels) |
| Exclusions | None |
| Expected outcome | 100% intra-frame order preservation, playable cine |

**Purpose:** Prove that intra-object frame order is preserved and playable.

### 4.3 Dataset C — Ordered Series with Explicit Exclusion (Gap Test)

| Property | Value |
|----------|-------|
| Modality | CT or US |
| Series Size | 10 images |
| Instance Numbers | 1–10 |
| Excluded Frame | Instance Number 5 (flagged as worksheet) |
| Expected outcome | Explicit positional gap at index 5 |

**Purpose:** Prove that exclusions are positional, explicit, and auditable.

---

## 5. Automated Assertions

### 5.1 Dataset A Assertions (15 total)

#### Category 1: Source Order Manifest Integrity

| ID | Assertion | Severity |
|----|-----------|----------|
| A1.1 | SourceOrderManifest exists | HARD FAIL |
| A1.2 | Manifest hash valid (SHA-256 matches) | HARD FAIL |
| A1.3 | Entry count = 12 | HARD FAIL |
| A1.4 | Instance Numbers = [1..12] sequential | HARD FAIL |
| A1.5 | Source index matches position | HARD FAIL |

#### Category 2: Export Order Manifest Integrity

| ID | Assertion | Severity |
|----|-----------|----------|
| A2.1 | ExportOrderManifest exists | HARD FAIL |
| A2.2 | Export references source manifest correctly | HARD FAIL |
| A2.3 | Export count = 12 | HARD FAIL |
| A2.4 | All dispositions = EXPORTED | HARD FAIL |

#### Category 3: Order Preservation (Core)

| ID | Assertion | Severity |
|----|-----------|----------|
| A3.1 | Export index = Source index (all) | HARD FAIL |
| A3.2 | Instance number sequence preserved | HARD FAIL |
| A3.3 | SOPInstanceUID mapping traceable | HARD FAIL |
| A3.4 | No duplicate export indices | HARD FAIL |
| A3.5 | No gaps in export indices | HARD FAIL |

#### Category 4: Verification Record

| ID | Assertion | Severity |
|----|-----------|----------|
| A4.1 | OrderVerificationRecord exists | HARD FAIL |
| A4.2 | References correct manifests | HARD FAIL |
| A4.3 | gate_passed flag accurate | HARD FAIL |

**Pass Rule:** All 15 assertions must pass.

### 5.2 Dataset B Assertions (17 hard + 2 manual + 3 soft)

#### Category 1: Source Frame Capture

| ID | Assertion | Severity |
|----|-----------|----------|
| B1.1 | Manifest exists and is_multiframe=True | HARD FAIL |
| B1.2 | Frame count = 20 | HARD FAIL |
| B1.3 | Frame numbers = [1..20] sequential | HARD FAIL |
| B1.4 | Single SOPInstanceUID for all frames | HARD FAIL |
| B1.5 | Source index = Frame number | HARD FAIL |
| B1.6 | Per-frame pixel hashes present | SOFT (evidence-enhancing) |

#### Category 2: Export Frame Verification

| ID | Assertion | Severity |
|----|-----------|----------|
| B2.1 | ExportOrderManifest exists | HARD FAIL |
| B2.2 | Export frame count = 20 | HARD FAIL |
| B2.3 | No flattening (single SOP) | HARD FAIL |
| B2.4 | All frames disposition = EXPORTED | HARD FAIL |

#### Category 3: Intra-Frame Order Proof

| ID | Assertion | Severity |
|----|-----------|----------|
| B3.1 | Export index = Source index (all frames) | HARD FAIL |
| B3.2 | Frame number sequence = [1..20] | HARD FAIL |
| B3.3 | No duplicate frame numbers | HARD FAIL |
| B3.4 | No gaps in frame sequence | HARD FAIL |
| B3.5 | Frame hashes consistent (if available) | SOFT |

#### Category 4: DICOM Structure Integrity

| ID | Assertion | Severity |
|----|-----------|----------|
| B4.1 | NumberOfFrames tag = 20 | HARD FAIL |
| B4.2 | Pixel array shape[0] = 20 | HARD FAIL |
| B4.3 | Multi-frame SOP Class preserved | HARD FAIL |

#### Category 5: Manual Verification (MANDATORY)

| ID | Check | Severity |
|----|-------|----------|
| B5.1 | Cine plays in reference viewer (not the export tool itself) | HARD FAIL |
| B5.2 | Frame order visually confirmed | HARD FAIL |
| B5.3 | Viewer name + version recorded | SOFT |

#### Category 6: Verification Record

| ID | Assertion | Severity |
|----|-----------|----------|
| B6.1 | OrderVerificationRecord exists | HARD FAIL |
| B6.2 | Manual verification artefact attached | HARD FAIL |
| B6.3 | gate_passed flag accurate | HARD FAIL |

**Pass Rule:** All 17 hard assertions + 2 mandatory manual checks must pass.

### 5.3 Dataset C Assertions (15 total)

#### Category 1: Source Order Baseline

| ID | Assertion | Severity |
|----|-----------|----------|
| C1.1 | SourceOrderManifest exists | HARD FAIL |
| C1.2 | Source count = 10 | HARD FAIL |
| C1.3 | Instance Numbers = [1..10] | HARD FAIL |

#### Category 2: Exclusion Declaration

| ID | Assertion | Severity |
|----|-----------|----------|
| C2.1 | Exactly 1 exclusion recorded | HARD FAIL |
| C2.2 | Excluded frame = Instance 5 | HARD FAIL |
| C2.3 | Exclusion reason present | HARD FAIL |
| C2.4 | Reason = WORKSHEET_DETECTED | HARD FAIL |

#### Category 3: Positional Gap Proof

| ID | Assertion | Severity |
|----|-----------|----------|
| C3.1 | Export count = 9 | HARD FAIL |
| C3.2 | Source index mapping correct (1-4→1-4, 6-10→5-9) | HARD FAIL |
| C3.3 | Instance Numbers = [1,2,3,4,6,7,8,9,10] | HARD FAIL |
| C3.4 | Gap logged with reason | HARD FAIL |

#### Category 4: Export Manifest Integrity

| ID | Assertion | Severity |
|----|-----------|----------|
| C4.1 | Export references source correctly | HARD FAIL |
| C4.2 | No duplicate source indices | HARD FAIL |

#### Category 5: Verification & Human Readability

| ID | Assertion | Severity |
|----|-----------|----------|
| C5.1 | OrderVerificationRecord exists | HARD FAIL |
| C5.2 | gate_passed = True | HARD FAIL |
| C5.3 | Human-readable gap explanation present | HARD FAIL |

**Pass Rule:** All 15 assertions must pass.

---

## 6. Evidence Checklist (Operator-Facing)

### Instructions for Operators

This checklist must be completed **in full** before Gate 1 can be marked PASSED.

- ☐ = Not started
- ◐ = In progress / Partial
- ✓ = Completed with evidence attached
- ✗ = Failed (blocks gate)

**Rule:** All items must be ✓ to pass. Any ✗ blocks Gate 1 and therefore **blocks all masking work**.

---

### Section 1: Pre-Execution Setup

| # | Item | Status | Evidence |
|---|------|--------|----------|
| 1.1 | Test datasets A, B, C created per specification | ☐ | Dataset files available |
| 1.2 | Dataset A: 12 single-frame CT/MR images, Instance Numbers 1–12 | ☐ | File listing |
| 1.3 | Dataset B: 1 multi-frame US/XA object, 20 frames, indices 1–20 | ☐ | DICOM header showing NumberOfFrames=20 |
| 1.4 | Dataset C: 10 single-frame images, Instance 5 marked as worksheet | ☐ | File listing + Instance 5 metadata |
| 1.5 | Reference DICOM viewer installed and identified (not the export tool itself) | ☐ | Viewer name + version |
| 1.6 | Test environment isolated (no production data) | ☐ | Environment confirmation |

---

### Section 2: Dataset A — Baseline Order Preservation

#### 2.1 Source Order Capture

| # | Assertion | Status | Evidence |
|---|-----------|--------|----------|
| A1.1 | SourceOrderManifest exists | ☐ | Manifest JSON file |
| A1.2 | Manifest hash valid | ☐ | Hash verification output |
| A1.3 | Entry count = 12 | ☐ | Manifest inspection |
| A1.4 | Instance Numbers = [1..12] sequential | ☐ | Manifest inspection |
| A1.5 | Source index matches position | ☐ | Automated test output |

#### 2.2 Export Order Verification

| # | Assertion | Status | Evidence |
|---|-----------|--------|----------|
| A2.1 | ExportOrderManifest exists | ☐ | Manifest JSON file |
| A2.2 | Export references source manifest correctly | ☐ | ID + hash match |
| A2.3 | Export count = 12 | ☐ | Manifest inspection |
| A2.4 | All dispositions = EXPORTED | ☐ | Manifest inspection |

#### 2.3 Order Preservation Proof

| # | Assertion | Status | Evidence |
|---|-----------|--------|----------|
| A3.1 | Export index = Source index (all) | ☐ | Automated test output |
| A3.2 | Instance number sequence preserved | ☐ | Automated test output |
| A3.3 | SOPInstanceUID mapping traceable | ☐ | Automated test output |
| A3.4 | No duplicate export indices | ☐ | Automated test output |
| A3.5 | No gaps in export indices | ☐ | Automated test output |

#### 2.4 Verification Record

| # | Assertion | Status | Evidence |
|---|-----------|--------|----------|
| A4.1 | OrderVerificationRecord exists | ☐ | Record JSON file |
| A4.2 | References correct manifests | ☐ | ID match verification |
| A4.3 | gate_passed = True | ☐ | Record inspection |

**Dataset A Status:** ☐ NOT PASSED

---

### Section 3: Dataset B — Multi-Frame Cine Preservation

#### 3.1 Source Frame Capture

| # | Assertion | Status | Evidence |
|---|-----------|--------|----------|
| B1.1 | Manifest exists and is_multiframe=True | ☐ | Manifest JSON |
| B1.2 | Frame count = 20 | ☐ | Manifest inspection |
| B1.3 | Frame numbers = [1..20] sequential | ☐ | Manifest inspection |
| B1.4 | Single SOPInstanceUID for all frames | ☐ | Manifest inspection |
| B1.5 | Source index = Frame number | ☐ | Automated test output |
| B1.6 | Per-frame pixel hashes present (optional) | ☐ | Manifest inspection |

#### 3.2 Export Frame Verification

| # | Assertion | Status | Evidence |
|---|-----------|--------|----------|
| B2.1 | ExportOrderManifest exists | ☐ | Manifest JSON |
| B2.2 | Export frame count = 20 | ☐ | Manifest inspection |
| B2.3 | No flattening (single SOP) | ☐ | Manifest inspection |
| B2.4 | All frames disposition = EXPORTED | ☐ | Manifest inspection |

#### 3.3 Intra-Frame Order Proof

| # | Assertion | Status | Evidence |
|---|-----------|--------|----------|
| B3.1 | Export index = Source index (all frames) | ☐ | Automated test output |
| B3.2 | Frame number sequence = [1..20] | ☐ | Automated test output |
| B3.3 | No duplicate frame numbers | ☐ | Automated test output |
| B3.4 | No gaps in frame sequence | ☐ | Automated test output |
| B3.5 | Frame hashes consistent (if available) | ☐ | Automated test output |

#### 3.4 DICOM Structure Integrity

| # | Assertion | Status | Evidence |
|---|-----------|--------|----------|
| B4.1 | NumberOfFrames tag = 20 | ☐ | DICOM header dump |
| B4.2 | Pixel array shape[0] = 20 | ☐ | Automated test output |
| B4.3 | Multi-frame SOP Class preserved | ☐ | DICOM header dump |

#### 3.5 Manual Verification (MANDATORY)

| # | Check | Status | Evidence Required |
|---|-------|--------|-------------------|
| B5.1 | Cine plays in reference viewer | ☐ | Screenshot or screen recording |
| B5.2 | Frame order visually confirmed | ☐ | Screenshots: Frame 1, 10, 20 |
| B5.3 | Viewer name + version recorded | ☐ | Text notation |

#### 3.6 Verification Record

| # | Assertion | Status | Evidence |
|---|-----------|--------|----------|
| B6.1 | OrderVerificationRecord exists | ☐ | Record JSON |
| B6.2 | Manual verification artefact attached | ☐ | File path in record |
| B6.3 | gate_passed = True | ☐ | Record inspection |

**Dataset B Status:** ☐ NOT PASSED

---

### Section 4: Dataset C — Exclusion Gap Preservation

#### 4.1 Source Order Baseline

| # | Assertion | Status | Evidence |
|---|-----------|--------|----------|
| C1.1 | SourceOrderManifest exists | ☐ | Manifest JSON |
| C1.2 | Source count = 10 | ☐ | Manifest inspection |
| C1.3 | Instance Numbers = [1..10] | ☐ | Manifest inspection |

#### 4.2 Exclusion Declaration

| # | Assertion | Status | Evidence |
|---|-----------|--------|----------|
| C2.1 | Exactly 1 exclusion recorded | ☐ | Export manifest |
| C2.2 | Excluded frame = Instance 5 | ☐ | Export manifest |
| C2.3 | Exclusion reason present | ☐ | Export manifest |
| C2.4 | Reason = WORKSHEET_DETECTED | ☐ | Export manifest |

#### 4.3 Positional Gap Proof

| # | Assertion | Status | Evidence |
|---|-----------|--------|----------|
| C3.1 | Export count = 9 | ☐ | Export manifest |
| C3.2 | Source index mapping correct | ☐ | Automated test output |
| C3.3 | Instance Numbers = [1,2,3,4,6,7,8,9,10] | ☐ | Export manifest |
| C3.4 | Gap logged with reason | ☐ | Audit log extract |

#### 4.4 Export Manifest Integrity

| # | Assertion | Status | Evidence |
|---|-----------|--------|----------|
| C4.1 | Export references source correctly | ☐ | ID + hash match |
| C4.2 | No duplicate source indices | ☐ | Automated test output |

#### 4.5 Verification & Human Readability

| # | Assertion | Status | Evidence |
|---|-----------|--------|----------|
| C5.1 | OrderVerificationRecord exists | ☐ | Record JSON |
| C5.2 | gate_passed = True | ☐ | Record inspection |
| C5.3 | Human-readable gap explanation present | ☐ | Text report extract |

**Dataset C Status:** ☐ NOT PASSED

---

### Section 5: Final Gate 1 Evidence Package

| # | Artefact | Status | Location |
|---|----------|--------|----------|
| 5.1 | All SourceOrderManifest JSON files | ☐ | |
| 5.2 | All ExportOrderManifest JSON files | ☐ | |
| 5.3 | All OrderVerificationRecord JSON files | ☐ | |
| 5.4 | Automated test output (full run log) | ☐ | |
| 5.5 | Dataset B manual verification screenshots | ☐ | |
| 5.6 | Human-readable summary reports (all datasets) | ☐ | |
| 5.7 | Reference viewer identification | ☐ | |

**Note:** Artefacts must be read-only once collected.

---

## 7. Gate Sign-Off

### Pre-Conditions (All Must Be True)

| # | Condition | Status |
|---|-----------|--------|
| 7.1 | Dataset A: All assertions passed | ☐ |
| 7.2 | Dataset B: All assertions + manual checks passed | ☐ |
| 7.3 | Dataset C: All assertions passed | ☐ |
| 7.4 | All evidence artefacts collected and stored | ☐ |
| 7.5 | Independent reviewer could verify from evidence alone | ☐ |

### Gate 1 Declaration

```
┌─────────────────────────────────────────────────────────────────────┐
│                                                                     │
│   GATE 1 — SERIES ORDER PRESERVATION                                │
│                                                                     │
│   Status:  ☐ NOT PASSED  /  ☐ PASSED                                │
│                                                                     │
│   Verified By: _______________________  Date: _______________       │
│                                                                     │
│   Reviewer:    _______________________  Date: _______________       │
│                                                                     │
│   Evidence Package Location: ___________________________________    │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

### Consequences of Gate 1 Status

| Gate 1 Status | Consequence |
|---------------|-------------|
| **NOT PASSED** | Masking implementation **BLOCKED**. No pixel mutation permitted. |
| **PASSED** | Gate 1 prerequisite satisfied. Proceed to Gate 2 (Source Recoverability). |

---

## Why This Gate Exists

Series order preservation is what makes the statement:

> "This is the study"

defensible.

Without it:
- FOI exports are contestable
- Legal evidence is weakened
- Trust in downstream masking is impossible

---

**Document Status:** DESIGN COMPLETE  
**Gate Status:** 🔴 NOT PASSED  
**Next Valid Action:** Execute Gate 1 verification with test datasets  
**Invalid Action:** Begin masking work
