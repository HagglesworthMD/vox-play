# Phase 4 — Explicit Non-Goals

**(OCR Detection Hardening)**

## Purpose of This Section

This section defines what **Phase 4 explicitly does *not*** attempt to do.

These constraints are intentional and designed to:

* Preserve governance clarity
* Prevent scope creep into clinical or automated decision-making
* Maintain audit defensibility
* Reduce acquisition, regulatory, and liability risk

Phase 4 focuses **only** on improving the *quality and explainability of OCR-based detection*.

---

## Explicit Non-Goals

### 1. No Automated Masking or Pixel Modification

Phase 4 **does not**:

* Automatically mask detected text
* Modify PixelData during detection
* Trigger masking based on OCR confidence
* Apply heuristic or implicit pixel changes

**Rationale:**
Detection ≠ action. Masking remains a **separate, explicit, operator-controlled step** governed outside Phase 4.

---

### 2. No Claims of Complete PHI Detection

Phase 4 **does not**:

* Claim to detect all burned-in PHI
* Assert that OCR detection is exhaustive
* Represent images as "safe," "clean," or "de-identified"
* Substitute human review with algorithmic judgment

**Rationale:**
Burned-in PHI detection is inherently probabilistic. Overstated claims introduce unacceptable legal and governance risk.

---

### 3. No Clinical or Diagnostic Interpretation

Phase 4 **does not**:

* Interpret clinical content
* Distinguish clinically relevant vs irrelevant text
* Alter image presentation for diagnostic purposes
* Interact with reporting or interpretation workflows

**Rationale:**
VoxelMask is a **non-clinical**, PACS-adjacent system. Any diagnostic implication is explicitly out of scope.

---

### 4. No Silent or Implicit Behavior Changes

Phase 4 **does not**:

* Introduce heuristics that silently change behavior
* Modify detection thresholds without operator visibility
* Auto-adjust OCR behavior based on prior runs
* Learn or adapt from prior studies

**Rationale:**
All detection behavior must be **explicit, explainable, and reviewable** to remain audit-safe.

---

### 5. No Pixel Invariant Exceptions

Phase 4 **does not**:

* Weaken or bypass Phase 3 pixel invariants
* Introduce new execution paths that touch PixelData implicitly
* Combine detection and mutation logic
* Re-open or re-litigate Phase 3 architecture

**Rationale:**
Phase 3 behavior is **locked and versioned**. Phase 4 operates strictly above that boundary.

---

### 6. No Replacement of PACS Governance or SOPs

Phase 4 **does not**:

* Replace institutional review processes
* Override PACS, FOI, or research governance policies
* Act as a compliance authority
* Certify datasets for release

**Rationale:**
VoxelMask supports governance; it does not redefine it.

---

### 7. No Production PACS Write-Back

Phase 4 **does not**:

* Write modified objects back into PACS
* Perform in-place updates
* Act as a routing or distribution engine

**Rationale:**
The pilot remains **copy-out only**, preserving operational safety and audit separation.

---

### 8. No User Deception or Overconfidence Signaling

Phase 4 **does not**:

* Present confidence as certainty
* Use "pass/fail" language for detection
* Hide uncertainty from operators
* Collapse nuanced detection signals into simplistic scores

**Rationale:**
Operators must be informed, not reassured falsely.

---

## Summary Statement (Acquisition-Facing)

> Phase 4 improves the *visibility, explainability, and reviewability* of OCR-based burned-in text detection while explicitly avoiding automation, masking, or claims of completeness.
> All operator actions remain intentional, logged, and reversible.
> Detection outcomes inform review; they do not dictate action.

---

## Document Metadata

| Field               | Value                          |
|---------------------|--------------------------------|
| **Version**         | 1.0                            |
| **Created**         | 2025-12-16                     |
| **Classification**  | Governance / Diligence         |
| **Audience**        | Acquisition, Legal, PACS Admin |
| **Related Docs**    | `PHASE3_PIXEL_INVARIANT.md`    |
