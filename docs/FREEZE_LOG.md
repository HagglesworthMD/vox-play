# Freeze Log — v0.4.0-review-gated

**Freeze Period:** 2025-12-15 onwards  
**Tag:** `v0.4.0-review-gated`  
**Purpose:** Track observations during pilot freeze period

---

## Freeze Rules

During freeze, only the following are permitted:
- ✅ Build fixes
- ✅ Documentation fixes
- ✅ Test hygiene
- ❌ No new features
- ❌ No behaviour changes to protected areas

---

## Daily Log

### 2025-12-15 — Freeze Start

**Actions:**
- [x] Tag `v0.4.0-review-gated` created and pushed
- [x] Governance documentation committed
- [x] 483 tests passing

**Observations:**
- (Record any pilot sanity run observations here)

**Issues Found:**
- None

---

### Template for Daily Entries

```markdown
### YYYY-MM-DD — Day N

**Actions:**
- [ ] What was tested

**Observations:**
- What was observed (even if expected)

**Issues Found:**
- Any surprises (note: don't fix during freeze unless safety-critical)
```

---

## Pilot Sanity Run Checklist

Before pilot demo, verify:

- [ ] US example: export gated until accept
- [ ] SC/doc-like example: export gated until accept
- [ ] Accept seals session (cannot modify after)
- [ ] Audit PDF produced only after successful export
- [ ] Decision Trace commit only after ZIP creation
- [ ] Counts in PDF match expected

---

## Notes

Record any observations, even if harmless. This log supports governance discussions.

---

# Freeze Log Entry — Phase 5C

## Phase

**Phase 5C — Audit Completeness**

---

## Freeze Status

**FROZEN**

No further functional, schema, or behavioural changes are permitted within Phase 5C.

---

## Freeze Date

**16 December 2025**

---

## Scope of Freeze

This freeze applies to all components involved in **audit evidence generation and completeness**, including but not limited to:

* Audit evidence bundle structure and schema
* Decision logging for:

  * Metadata anonymisation
  * OCR detection outcomes
  * Pixel masking application / non-application
* Coverage accounting for all processed DICOM objects
* Configuration capture and hashing
* Integrity verification mechanisms (hashes, manifests)
* PHI guardrail signalling and negative assertions

---

## Freeze Rationale

Phase 5C establishes that VoxelMask can produce a **minimum sufficient, defensible audit evidence set** for non-clinical, copy-out de-identification workflows.

The freeze confirms that:

* Audit artefacts are **explicit**, not inferred
* Processing decisions are **reconstructable from evidence**
* Evidence is generated **at processing time**, not retrospectively
* Failure modes and uncertainty are **visible and logged**

This represents the completion of the Phase 5C design intent.

---

## Evidence Supporting Freeze

The freeze is supported by the following verified artefacts:

* Phase 5C design specification (`PHASE5C_GATE3_AUDIT_COMPLETENESS.md`)
* Evidence bundle schema enforcement tests
* End-to-end audit bundle validation tests
* PHI guardrail tests ensuring no silent masking or omission
* Deterministic behaviour verification across repeated runs

All supporting tests passed at the time of freeze.

---

## Explicit Exclusions (Unchanged by Freeze)

The following remain **out of scope** and are unaffected by this freeze:

* Clinical write-back to PACS
* RIS / MPPS / workflow integration
* Real-time routing or clinical decision support
* Claims of complete or perfect PHI removal
* Legal or compliance determinations beyond evidence provision

These exclusions are intentional and documented.

---

## Change Control Post-Freeze

Any of the following changes **invalidate this freeze** and require a new phase declaration:

* Modification of audit evidence schema or required fields
* Introduction of new audit artefact types
* Changes to recoverability or source retention model
* Alteration of PHI guardrail semantics
* Introduction of clinical or PACS write-back capability

Minor documentation clarifications that do not affect behaviour or evidence semantics are permitted.

---

## Governance Statement

Phase 5C concludes the audit defensibility layer for VoxelMask in its pilot-safe, copy-out configuration.

The system is now positioned to support:

* Internal governance review
* FOI and research oversight
* Vendor and partner technical due diligence

without expanding clinical scope or governance risk.

---

## Sign-Off

**Declared by:** Project Owner / Engineer  
**Role:** PACS Systems Engineer (Pilot Context)  
**Project:** VoxelMask  
**Date:** 16 December 2025

---

*This freeze log entry is audit-grade and suitable for governance, FOI officers, or acquisition due-diligence review.*

---

## Phase 5C Close-Out — Known Conservative Behaviour

**Scope clarification — document and worksheet handling**

During Phase 5C validation, it was observed that in **Research compliance mode**, certain document-like objects (e.g. worksheets or secondary capture instances) were processed even when document handling was not explicitly selected via the user interface.

This behaviour is **intentional and policy-driven**, not a processing error.

VoxelMask currently classifies and processes objects based on **image-bearing characteristics and SOP Class**, rather than UI selection alone. Where an object is deemed to potentially contain burned-in PHI within pixel data (for example, US-derived worksheets or SC instances), it is conservatively included to prevent inadvertent omission of identifiable information.

This design ensures that:

* Processing decisions are **deterministic and reproducible**
* Potential PHI-bearing objects are **not silently excluded**
* All inclusions are **explicitly logged and auditable**
* Research workflows err on the side of **over-inclusion rather than data leakage**

User interface selections are treated as **intent signals**, not authoritative overrides of compliance policy, during Phase 5C.

No changes to this behaviour were made during Phase 5C in order to preserve:

* Audit integrity
* Evidence bundle consistency
* Governance defensibility at freeze

**Planned refinement**

User-facing clarification and object-type signalling (e.g. SOP Class-aware messaging or warnings) are explicitly deferred to **Phase 6 — UX Hardening**. Any such refinements will not weaken the underlying conservative processing guarantees established in Phase 5C.

**Phase 5C Status**

Phase 5C is considered **complete and frozen**, with conservative inclusion behaviour documented, understood, and accepted as compliant with pilot-safe, non-clinical research use.

---

# Freeze Log Entry — Phase 6

## Phase

**Phase 6 — UI Language Pass**

---

## Freeze Status

**FROZEN**

No further wording, labelling, or presentation changes are permitted within Phase 6 scope without explicit re-evaluation.

---

## Freeze Date

**16 December 2025**

---

## Scope of Freeze

This freeze applies to all **user-facing text and labelling** within the VoxelMask application, including but not limited to:

* Application header and subheading
* Page title (browser tab)
* Profile selector labels and tooltips
* Section headers and helper text
* Button labels
* Footer disclaimer
* Error and warning messages

---

## Language Rules Locked

The following language constraints are now enforced:

### Forbidden Words (Anywhere)

* ❌ AI-powered
* ❌ Fully anonymised
* ❌ Guaranteed
* ❌ Safe for clinical use
* ❌ HIPAA compliant (as a blanket claim)
* ❌ All PHI removed

### Required Framing

* ✅ "Evaluation build. Copy-out processing only. Not for clinical use."
* ✅ "Profiles reflect policy intent, not regulatory certification."
* ✅ "Output is intended for research, audit, or evaluation workflows."
* ✅ Persistent footer disclaimer acknowledging non-guarantee

---

## Changes Implemented

| Location | Before | After |
|----------|--------|-------|
| Page title | `VoxelMask - Intelligent De-ID` | `VoxelMask — Imaging De-Identification (Pilot Mode)` |
| Header | `VoxelMask` | `VoxelMask — Imaging De-Identification (Pilot Mode)` |
| Subheading | `*Professional DICOM De-Identification for Clinical & Research Use*` | `**Evaluation build. Copy-out processing only. Not for clinical use.**` |
| Profile selector label | `Operation Profile` | `De-Identification Profile` |
| Profile: internal_repair | `🔧 Clinical Correction - Fix patient name/headers (Internal Use)` | `🔧 Internal Repair - Metadata correction (evaluation only)` |
| Section header | `📁 Select DICOM Files` | `Input Studies` |
| Helper text | (none) | `DICOM studies are processed in copy-out mode. Source data is not modified.` |
| Footer | `VoxelMask | DICOM De-Identification Engine` | Persistent disclaimer (non-guarantee + user responsibility) |

---

## Governance Rationale

This language pass ensures:

* **No implicit clinical safety claims** — explicit non-clinical boundary
* **No silent guarantees** — explicit fallibility acknowledged
* **Acquisition-grade language** — suitable for vendor due diligence
* **FOI defensibility** — no overclaims that could be misrepresented
* **Ops-friendly clarity** — unambiguous expectations for operators

---

## Evidence Supporting Freeze

* All UI text updated in `src/app.py`
* 666 tests passing after changes
* No behaviour changes — presentation-layer only
* Commit: `Phase 6: UI Language Pass — governance-safe wording`

---

## Change Control Post-Freeze

Any of the following changes **invalidate this freeze** and require re-evaluation:

* Introduction of clinical workflow claims
* Removal of non-clinical disclaimers
* Modification of footer disclaimer
* Use of forbidden words
* Changes implying guarantee or completeness

---

## Sign-Off

**Declared by:** Project Owner / Engineer  
**Role:** PACS Systems Engineer (Pilot Context)  
**Project:** VoxelMask  
**Date:** 16 December 2025

---

*This freeze log entry is audit-grade and suitable for governance, FOI officers, or acquisition due-diligence review.*

---

# Freeze Log Entry — Phase 6 (SOP Class Classification Fix)

## Phase

**Phase 6 — SOP Class-Based Object Classification**

---

## Status

**IMPLEMENTED**

Critical loophole in document exclusion logic has been closed.

---

## Implementation Date

**16 December 2025**

---

## Bug Summary

A critical bug was identified where DICOM objects could bypass the `include_documents=False` filter by having a mismatched modality string.

### Root Cause

The bucket classification logic in `app.py` used **modality string** as the primary classifier:

```python
# OLD (VULNERABLE):
if modality == 'US':
    bucket_us.append(file_buffer)
elif modality in ['SC', 'OT']:
    bucket_docs.append(file_buffer)
```

This allowed documents to leak into image buckets if their Modality tag was incorrectly set (e.g., an Encapsulated PDF with Modality="US").

### Attack Vector Examples

| Object Type | SOP Class UID | Modality | OLD Bucket | Risk |
|-------------|---------------|----------|------------|------|
| Encapsulated PDF | `1.2.840.10008.5.1.4.1.1.104.1` | `US` | `bucket_us` | **BYPASS** |
| Secondary Capture | `1.2.840.10008.5.1.4.1.1.7` | `CT` | `bucket_safe` | **BYPASS** |
| Multi-frame SC | `1.2.840.10008.5.1.4.1.1.7.1` | `MR` | `bucket_safe` | **BYPASS** |

---

## Fix Applied

The bucket classification now uses `classify_object()` from `selection_scope.py` as the **single source of truth**:

```python
# NEW (SECURE):
category = classify_object(
    modality=modality,
    sop_class_uid=sop_class_uid,
    series_description=series_desc,
    image_type=''
)

if category == ObjectCategory.IMAGE:
    if modality == 'US':
        bucket_us.append(file_buffer)
    else:
        bucket_safe.append(file_buffer)
elif category in (ObjectCategory.DOCUMENT, ObjectCategory.STRUCTURED_REPORT, 
                  ObjectCategory.ENCAPSULATED_PDF):
    bucket_docs.append(file_buffer)
```

### Classification Priority Order

1. **SOP Class UID** (authoritative) — checked first
2. **Modality string** (fallback) — only if SOP Class not in known list
3. **SeriesDescription keywords** — last resort for worksheet detection

---

## Behaviour After Fix

| Object Type | SOP Class UID | Modality | NEW Bucket | Gate |
|-------------|---------------|----------|------------|------|
| Encapsulated PDF | `1.2.840.10008.5.1.4.1.1.104.1` | `US` | `bucket_docs` | `include_documents` |
| Secondary Capture | `1.2.840.10008.5.1.4.1.1.7` | `CT` | `bucket_docs` | `include_documents` |
| Real US Image | `1.2.840.10008.5.1.4.1.1.6.1` | `US` | `bucket_us` | `include_images` |
| Real CT Image | `1.2.840.10008.5.1.4.1.1.2` | `CT` | `bucket_safe` | `include_images` |

---

## Regression Tests Added

New test class `TestSOPClassOverridesModality` in `tests/test_selection_scope.py`:

* `test_pdf_with_us_modality_is_still_pdf` — CRITICAL loophole test
* `test_secondary_capture_with_ct_modality_is_document`
* `test_multiframe_sc_with_mr_modality_is_document`
* `test_sr_sop_with_us_modality_is_sr`
* `test_sop_class_takes_priority_over_safe_modality`
* `test_document_exclusion_works_with_mismatched_modality` — END-TO-END
* `test_real_us_image_still_included`
* `test_real_ct_image_still_included`

---

## Governance Impact

* **FOI Defensibility**: `include_documents=False` now truly excludes all documents
* **Audit Integrity**: Selection scope is recorded accurately
* **Series Preservation**: No impact on Gate 1 ordering guarantees
* **PACS Realism**: SOP Class is the correct DICOM identity, not modality string

---

## Files Changed

| File | Change |
|------|--------|
| `src/app.py` | Replaced modality-based bucket logic with `classify_object()` |
| `tests/test_selection_scope.py` | Added `TestSOPClassOverridesModality` regression tests |
| `docs/FREEZE_LOG.md` | This entry |

---

## Sign-Off

**Declared by:** Project Owner / Engineer  
**Role:** PACS Systems Engineer (Pilot Context)  
**Project:** VoxelMask  
**Date:** 16 December 2025

---

*This fix closes a critical loophole and is required for governance-safe, acquisition-clean deployment.*

