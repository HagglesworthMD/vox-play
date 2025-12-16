# Phase 6 — UX Hardening

## Phase Overview

**Phase 6 — UX Hardening** addresses user-facing clarity improvements deferred from Phase 5C to preserve audit integrity and governance defensibility at freeze.

This phase focuses on **signalling and messaging**, not processing behaviour. All underlying conservative safeguards established in Phase 5C remain unchanged.

---

## Status

**NOT STARTED**

Phase 6 cannot commence until Phase 5C is fully validated in pilot deployment.

---

## Explicit Non-Goals

The following are **explicitly out of scope** for Phase 6:

| Non-Goal | Rationale |
|----------|-----------|
| Weakening conservative inclusion logic | Phase 5C guarantees must be preserved |
| Allowing UI selections to override compliance policy | Processing decisions remain policy-driven |
| Reducing audit evidence granularity | Evidence bundle schema is frozen |
| Introducing clinical write-back | Remains excluded per project scope |
| Changing SOP Class–based classification | Core processing logic is frozen |

Any proposal that conflicts with these non-goals requires a **new phase declaration** and governance review.

---

## Safety Constraints

All Phase 6 changes **MUST**:

1. **Not weaken Phase 5C guarantees** — Conservative inclusion behaviour is protected
2. **Not alter processing outcomes** — Same inputs must produce same outputs
3. **Not modify evidence bundle schema** — Audit artefacts are frozen
4. **Not introduce silent exclusions** — All object handling must remain logged
5. **Be presentation-layer only** — Backend policy logic is not in scope

---

## In-Scope Work Items

### 1. SOP Class–Aware Signalling

**Problem:** Users may be surprised when document-like objects (e.g. SC worksheets) are processed even when "Include Documents" is unchecked.

**Solution:** Display contextual messaging explaining *why* objects are included based on SOP Class and PHI risk assessment.

**Example UX:**

> ℹ️ *3 objects included due to potential burned-in PHI (SOP Class: Secondary Capture). These are processed conservatively regardless of document selection.*

**Constraints:**
- Message is informational only
- Does not offer override capability
- Does not change processing behaviour

---

### 2. Object Classification Summary

**Problem:** Users cannot easily see how objects were classified (Image vs Document vs SC).

**Solution:** Add a pre-processing summary panel showing:
- Count by SOP Class
- Count by Modality
- Objects flagged for conservative inclusion
- Objects excluded (with reason)

**Constraints:**
- Read-only display
- Reflects actual processing intent
- Does not allow modification

---

### 3. Compliance Mode Clarification

**Problem:** The implications of "Research" vs "Clinical Correction" mode may not be immediately clear to operators.

**Solution:** Add inline help text or tooltip explaining:
- Research mode: Conservative inclusion, full anonymisation
- Clinical Correction: Targeted field replacement, identity preservation

**Constraints:**
- Help text only
- Does not change mode behaviour

---

### 4. Post-Processing Manifest Review

**Problem:** Users may want to verify what was processed before export.

**Solution:** Display a manifest of processed objects with:
- SOPInstanceUID (or hash)
- Classification (Image/Document/SC)
- Actions taken (masked regions, anonymised fields)
- Inclusion reason

**Constraints:**
- Read-only post-processing view
- Does not allow modification after processing
- Aligns with existing audit bundle content

---

## Acceptance Criteria

Phase 6 is complete when:

1. [ ] SOP Class–aware signalling is implemented and tested
2. [ ] Object classification summary is visible pre-processing
3. [ ] Compliance mode help text is present
4. [ ] Post-processing manifest review is available
5. [ ] All Phase 5C tests continue to pass
6. [ ] Evidence bundle schema remains unchanged
7. [ ] Conservative inclusion behaviour is verified unaffected

---

## Dependencies

| Dependency | Status |
|------------|--------|
| Phase 5C frozen | ✅ Complete |
| Phase 5C pilot validation | ⏳ In progress |
| Evidence bundle schema stable | ✅ Frozen |

---

## Risk Assessment

| Risk | Mitigation |
|------|------------|
| UX changes inadvertently alter processing | All changes are presentation-layer only; backend untouched |
| Users expect override capability | Messaging explicitly states conservative behaviour is intentional |
| Regression in Phase 5C compliance | Full test suite run required before Phase 6 merge |

---

## Governance Notes

Phase 6 is a **UX refinement phase**, not a policy change phase.

All messaging introduced in Phase 6 must:
- Use **factual, neutral language**
- Avoid **action verbs** that imply system recommendations
- Align with **Phase 5A semantic conventions**

No changes in Phase 6 affect:
- Audit defensibility
- Evidence bundle structure
- Compliance guarantees

---

## Sign-Off

**Created:** 16 December 2025  
**Author:** Project Owner / Engineer  
**Status:** Draft — awaiting Phase 5C pilot completion

---

*This document establishes the scope and constraints for Phase 6. Implementation may not begin until Phase 5C pilot validation is complete.*
