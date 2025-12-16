# Phase 6 — Explicit Selection Semantics

**Document Type:** Governance Design & Freeze Declaration  
**Status:** ACTIVE  
**Version:** 0.6.0-explicit-selection  
**Date:** 2025-12-16  
**Author:** VoxelMask Engineering

---

## Executive Summary

Phase 6 replaces implicit document inclusion behaviour with **explicit operator intent**.

Key Changes:
- Documents/secondary objects are **NEVER** included unless explicitly selected
- Selection scope is **ALWAYS** recorded in audit output
- UI shows **"Excluded by selection"** instead of "Documents 0"
- Viewer reflects true inclusion state

This is an intentional evolution from Phase 5C conservative inclusion.

---

## 1. Problem Statement

### 1.1 Previous Behaviour (Phase 5C)

- UI implied "Documents not selected"
- Engine still included worksheets/secondary objects in Research mode
- This caused **operator confusion and trust erosion**

### 1.2 Root Cause

Conservative inclusion was implemented at the **processing layer** but not consistently surfaced in the **presentation layer**.

---

## 2. Solution

### 2.1 Explicit Selection Model

Introduced `SelectionScope` dataclass in `src/selection_scope.py`:

```python
@dataclass
class SelectionScope:
    include_images: bool = True       # Default: include images
    include_documents: bool = False   # Default: EXCLUDE documents
```

### 2.2 UI Changes

Two explicit toggles in the Processing Configuration section:

| Toggle | Default | Tooltip |
|--------|---------|---------|
| ☑ Include Imaging Series | ON | Include standard imaging modalities (US, CT, MR, XR, etc.) in the output package. |
| ☐ Include Associated Documents | OFF | Non-image objects (worksheets, reports, SC, OT) are only included when explicitly selected. This affects output content and audit records. |

### 2.3 Status Messages

When `include_documents = False`:
```
ℹ️ Associated Documents: Excluded by selection
Worksheets, reports, SC/OT objects, and PDFs will not appear in output package, viewer, or audit evidence bundle.
```

When `include_documents = True`:
```
📋 Associated Documents: Included
Worksheets, reports, SC/OT objects, and PDFs will be included and labelled as "Associated Objects" in the output.
```

When documents are detected but excluded:
```
📋 {N} Associated Document(s): Excluded by selection
Enable "Include Associated Documents" to include worksheets/reports in output.
```

---

## 3. Audit Logging (NON-NEGOTIABLE)

Every processing run MUST record:

```
════════════════════════════════════════════════════════════
SELECTION SCOPE
────────────────────────────────────────────────────────────

Include Imaging Series:      YES
Include Associated Documents: NO

EXCLUSION NOTE:
  Associated non-image objects were excluded based on explicit user selection.

Scope Created:  2025-12-16T12:00:00Z
════════════════════════════════════════════════════════════
```

JSON Evidence Bundle Format:
```json
{
  "selection_scope": {
    "include_images": true,
    "include_documents": false,
    "created_at": "2025-12-16T12:00:00Z",
    "modified_at": null
  },
  "exclusion_note": "Associated non-image objects were excluded based on explicit user selection."
}
```

---

## 4. Object Classification

### 4.1 Categories

| Category | Examples | Toggle |
|----------|----------|--------|
| IMAGE | US, CT, MR, XR, NM, PT, MG | include_images |
| DOCUMENT | SC, OT, worksheets, screenshots | include_documents |
| STRUCTURED_REPORT | SR modality | include_documents |
| ENCAPSULATED_PDF | PDF SOP Class | include_documents |

### 4.2 Classification Priority

1. SOP Class UID (most reliable)
2. Modality tag (SC, OT, SR, DOC, PR)
3. Series Description keywords (WORKSHEET, REPORT, etc.)
4. Image Type (DERIVED, SECONDARY)

---

## 5. Viewer Behaviour

### 5.1 When Documents Excluded

Documents:
- Do NOT appear in output package
- Do NOT appear in audit evidence bundle
- Do NOT appear in viewer list
- UI does NOT show "Documents 0"

### 5.2 When Documents Included

Documents:
- Are included in output package
- Are labelled as "Associated Object (Worksheet)" / "Associated Object (SC)" etc.
- Appear in viewer with proper labels
- Inclusion reason is logged

### 5.3 Non-Image Objects in Viewer

For non-image objects (if included):
- Cine controls disabled
- Explicit label: "Non-image object — scrolling not applicable"
- Single-frame indication shown

---

## 6. Series Order Preservation

Phase 6 preserves Phase 5C series ordering guarantees:

| Requirement | Status | Evidence |
|-------------|--------|----------|
| Study → Series → Instance hierarchy | ✓ Preserved | Viewer reads hierarchy from DICOM |
| Original SeriesNumber order | ✓ Preserved | Sorting by SeriesNumber |
| Original InstanceNumber order | ✓ Preserved | Sorting by InstanceNumber |
| AcquisitionDateTime tiebreak | ✓ Preserved | Falls back to AcquisitionDateTime |
| SOPInstanceUID tiebreak | ✓ Preserved | Lexical ordering for equal instances |

---

## 7. Guardrails

### 7.1 MUST NOT

- ❌ Implicitly include documents
- ❌ Change processing without audit trace
- ❌ Use "automatic", "safe", "guaranteed" language
- ❌ Claim clinical suitability
- ❌ Show "Documents 0" when documents are excluded by selection

### 7.2 MUST

- ✅ Make selection intent explicit
- ✅ Preserve Phase 5C audit defensibility
- ✅ Fail loudly, not silently
- ✅ Keep defaults conservative
- ✅ Log all exclusions with reason

---

## 8. Acceptance Criteria

| Criterion | Status | Evidence |
|-----------|--------|----------|
| Documents excluded unless explicitly selected | ✅ | `SelectionScope.include_documents = False` by default |
| Selection scope recorded in audit output | ✅ | `generate_scope_audit_block()` called |
| Viewer reflects true inclusion state | ✅ | "Excluded by selection" message |
| Series scrolls like PACS cine | ✅ | Preserved from Phase 5C |
| Single-frame / non-image behaviour clearly labelled | ✅ | Viewer labels non-image objects |
| No regression to silent inclusion | ✅ | Selection scope filtering enforced |

---

## 9. Implementation Files

| File | Purpose |
|------|---------|
| `src/selection_scope.py` | SelectionScope dataclass, classification logic, audit helpers |
| `src/app.py` | UI toggles, selection scope filtering, audit integration |
| `tests/test_selection_scope.py` | 39 unit tests for selection scope logic |

---

## 10. Freeze Declaration

**This document describes a Phase 6 behavioural change.**

Phase 6 intentionally replaces Phase 5C conservative auto-inclusion with explicit operator intent.

This is acceptable because:
- It is visible
- It is logged
- It is reversible
- It is defensible under FOI and vendor review

If any ambiguity remains, bias toward **not including data** and **telling the user why**.

---

## 11. Version History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 0.6.0-explicit-selection | 2025-12-16 | VoxelMask Engineering | Initial Phase 6 implementation |

---

**Phase 6 Design Complete.**
**Tag: `v0.6.0-explicit-selection`**
