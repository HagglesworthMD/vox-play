# Phase 4 — Risk Mitigation Mapping

**(OCR Detection Hardening)**

## Purpose

This document maps **explicit Phase 4 non-goals and known limitations** to:

* Potential risks if misunderstood or misused
* Concrete mitigation mechanisms built into VoxelMask
* Verifiable evidence artefacts (code, tests, logs, docs)

It exists to demonstrate that **risk has been identified, constrained, and governed** — not eliminated.

---

## Scope Boundary

This mapping applies **only** to:

* OCR-based burned-in text **detection**
* Non-clinical, copy-out workflows
* Operator-reviewed use cases (FOI, research, governance)

It explicitly excludes masking, export decisions, and clinical use.

---

## Risk Mitigation Table

| Area             | Non-Goal / Limitation               | Risk If Misinterpreted         | Mitigation Mechanism                                  | Evidence / Artefact                    |
| ---------------- | ----------------------------------- | ------------------------------ | ----------------------------------------------------- | -------------------------------------- |
| OCR Detection    | No claim of complete PHI detection  | User assumes images are "safe" | Explicit uncertainty language; no "clean/safe" states | `PHASE4_KNOWN_LIMITATIONS.md`; UI copy |
| OCR Detection    | Probabilistic accuracy              | False confidence in missed PHI | Detection posture categories (not pass/fail)          | Detection output model; audit logs     |
| Automation       | No automated masking                | Unauthorised pixel alteration  | Masking requires explicit operator action             | Phase 3 dispatch separation            |
| Pixel Handling   | No pixel mutation during detection  | Silent data corruption         | Pixel invariant checks (SHA-256)                      | `v0.4.1` / `v0.4.2` tags; tests        |
| Operator Control | Detection ≠ action                  | Tool seen as autonomous        | ReviewSession enforces explicit intent                | ReviewSession logs                     |
| UI Semantics     | No "safe/unsafe" labels             | Legal over-interpretation      | Neutral, descriptive wording only                     | UI strings; docs                       |
| OCR Failure      | OCR may fail silently in edge cases | Undetected burned-in PHI       | OCR failure surfaced as uncertainty                   | Detection status flags                 |
| Modality Risk    | US / SC high false-negative risk    | Inappropriate trust in output  | Modality-aware risk signaling                         | Known Limitations doc                  |
| Third-Party OCR  | Dependency on OCR engine            | Vendor liability confusion     | OCR treated as assistive component                    | Architecture docs                      |
| Governance       | Not a compliance authority          | Misuse as approval gate        | Explicit governance disclaimers                       | README; Non-Goals doc                  |
| PACS Ops         | No PACS write-back                  | Operational disruption         | Copy-out only architecture                            | SCP/SCU config                         |
| Learning Systems | No adaptive learning                | Undocumented behavior drift    | Static configuration only                             | Code review; no ML training            |
| Audit            | Detection logs ≠ PHI assertions     | Legal exposure in audits       | Careful, factual audit language                       | Audit log schema                       |

---

## Key Design Principles Reinforced

### 1. Visibility Over Certainty

When detection is uncertain, **uncertainty is surfaced**, not suppressed.

### 2. Explicit Human Responsibility

VoxelMask supports review; it does not replace it.

### 3. Separation of Concerns

Detection, masking, and export remain **architecturally and semantically separated**.

### 4. Evidence Over Assurances

Every mitigation has a corresponding artefact that can be inspected.

---

## Acquisition-Facing Summary

> Phase 4 risk is managed through **scope limitation, explicit uncertainty, operator control, and verifiable safeguards**, rather than automation or claims of completeness.
> Failure modes are acknowledged, surfaced, and logged — not hidden.

---

## Related Documents

* `PHASE4_NON_GOALS.md`
* `PHASE4_KNOWN_LIMITATIONS.md`
* `PHASE3_PIXEL_INVARIANT.md`
* Audit log schema

---

## Document Metadata

| Field               | Value                                      |
|---------------------|--------------------------------------------|
| **Version**         | 1.0                                        |
| **Created**         | 2025-12-16                                 |
| **Classification**  | Governance / Diligence / Risk              |
| **Audience**        | Acquisition, Legal, PACS Admin, Vendors    |
| **Related Docs**    | `PHASE4_NON_GOALS.md`, `PHASE4_KNOWN_LIMITATIONS.md` |
