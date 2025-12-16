# Freeze Notes: Preflight Findings

**Status:** Freeze-safe — informational only  
**Added:** Sprint 2.5  
**Author:** VoxelMask Engineering

---

## Overview

The **Preflight Findings** feature passively detects DICOM objects that may require special attention during review. It is **advisory only** and does **not** affect anonymisation, masking, or export behaviour.

## What It Detects

| Finding Type | SOP Class UID | Description |
|--------------|---------------|-------------|
| **Secondary Capture** | `1.2.840.10008.5.1.4.1.1.7` | Images created by screen capture or document scanning. May contain unmasked PHI from scanned forms, screenshots, or reports. |
| **Encapsulated PDF** | `1.2.840.10008.5.1.4.1.1.104.1` | PDF documents wrapped in DICOM format. This is a **non-image object** and is commonly overlooked during export. May contain full-text PHI. |

## Behaviour Guarantees

✅ **Advisory only** — displays a warning panel for user awareness  
✅ **No gating** — does not block accept or export  
✅ **No auto-exclusion** — does not modify dataset lists  
✅ **No masking changes** — pixel processing is unaffected  
✅ **No anonymisation changes** — metadata handling is unaffected  
✅ **Deterministic** — same input always produces same findings  

## Technical Details

- Detection occurs once per `ReviewSession`, during session creation
- Findings are stored in `ReviewSession.review_findings`
- UI indicator appears inside the "Burned-In PHI Review" expander
- Panel is read-only: no buttons, no toggles, no actions

## Why Encapsulated PDF Matters

Encapsulated PDF is a non-image DICOM object type. Unlike images:
- It cannot be visually inspected in standard DICOM viewers
- It is not subject to pixel-level masking
- It may contain complete patient records, reports, or scanned documents
- It is **commonly overlooked** during de-identification workflows

The preflight warning ensures operators are aware of these objects before export.

---

*This feature is freeze-safe and may be merged during code freeze periods.*

---

## Phase 2: Manual PDF Exclusion (Post-Freeze)

**Status:** Implemented with hardened mapping  
**Added:** Sprint 2.6  

### Overview

Phase 2 adds **user-driven exclusion** of Encapsulated PDFs from export. This is a manual operator action, logged for audit purposes.

### Key Safety Measures

1. **Deterministic Filename ↔ UID Mapping**
   - At preflight scan time, each file is registered with its (filename, SOPInstanceUID, SOPClassUID) tuple
   - Mapping is stored in `ReviewSession.file_uid_mapping`
   - Export filtering uses this stored mapping — **no re-reading of files**
   - Eliminates unreliable ad-hoc file reads during export

2. **Double SOP Class Verification**
   - `get_excluded_filenames()` checks BOTH:
     - UID matches an excluded PDF finding
     - SOP Class confirms file is Encapsulated PDF (`1.2.840.10008.5.1.4.1.1.104.1`)
   - Non-PDF files can NEVER be accidentally excluded

3. **Audit Logging**
   - Exclusion decisions logged with:
     - Action: `EXCLUDE_ENCAPSULATED_PDF` or `INCLUDE_ENCAPSULATED_PDF`
     - SOP Instance UID (from stored mapping)
     - Operator ID
     - UTC timestamp

### Behaviour Guarantees (Phase 2)

✅ **User-initiated only** — no automatic exclusion  
✅ **Reversible until seal** — operator can change decision until accept  
✅ **Deterministic** — same files + decisions = same export  
✅ **Masking unchanged** — PDF exclusion does not affect masking  
✅ **Anonymisation unchanged** — metadata handling is unaffected  
✅ **Non-PDF safe** — Secondary Capture cannot be excluded via this mechanism  

### Technical Details

| Method | Purpose |
|--------|---------|
| `register_file_uid()` | Store filename → UID mapping at scan time |
| `get_excluded_filenames()` | Resolve excluded UIDs to filenames via mapping |
| `get_sop_uid_for_file()` | Look up UID for a registered filename |
| `set_pdf_excluded()` | Set exclusion state (blocked after seal) |

### Test Coverage

- 12 tests in `TestFileUIDMapping`
- 2 tests in `TestMappingStabilityAcrossReruns`
- Verifies: correct mapping, non-PDF safety, stability across operations

---

*Phase 2 hardening complete. Mapping approach ensures reliable file identification.*

