# VoxelMask — Phase 4 Vendor Briefing

**Burned-In Text Detection (Non-Clinical, Copy-Out Pilot)**

## What VoxelMask Is

VoxelMask is a **PACS-adjacent, non-clinical** system designed to support **governed de-identification workflows** by:

* Deterministically anonymising **DICOM metadata**
* **Detecting** (not automatically masking) burned-in text via OCR
* Preserving **explicit operator control**
* Producing **audit-grade evidence** for review workflows (FOI, research, governance)

VoxelMask is intentionally conservative, PACS-realistic, and designed for **safe pilot evaluation** rather than clinical deployment.

---

## What Phase 4 Covers (and Why)

**Phase 4 focuses exclusively on improving OCR detection quality and explainability.**

The goal is not automation.
The goal is **visibility**: helping operators reliably identify where burned-in text *may* exist so that human review is informed and auditable.

Phase 4 work is constrained by formal non-goals, known limitations, and documented risk controls **before** any detection behavior is modified.

---

## What Phase 4 Explicitly Does *Not* Do

Phase 4 does **not**:

* Automatically mask or modify pixels
* Claim complete or exhaustive PHI detection
* Replace human review
* Perform clinical or diagnostic interpretation
* Write modified objects back into PACS
* Introduce adaptive or learning behavior
* Bypass Phase 3 pixel-invariant protections

Detection informs review.
Action remains **explicit and operator-controlled**.

---

## How Risk Is Managed (At a Glance)

VoxelMask manages risk through **constraint, separation, and evidence**, not through overconfidence.

* **Separation of concerns**
  Detection, masking, and export are architecturally separated.

* **Explicit uncertainty**
  Detection results surface confidence and failure modes; no "clean/safe" states exist.

* **Operator intent enforced**
  All mutations require explicit user action and are logged.

* **Immutable pixel guarantees**
  Metadata-only paths are enforced and validated by pixel invariants.

* **Audit-first design**
  Detection outputs, configuration, and review actions are preserved verbatim.

These controls are documented and traceable in-repo.

---

## Known Constraints (Openly Acknowledged)

* Burned-in text detection is **probabilistic**
* Certain modalities (e.g. ultrasound, secondary capture) are inherently higher risk
* OCR accuracy varies by font, overlay style, compression, and noise
* Third-party OCR engines are treated as **assistive components**, not authorities

VoxelMask does not hide these constraints; it exposes them to the operator.

---

## Evidence, Not Promises

Phase 4 is supported by three explicit governance artefacts:

* **Phase 4 Non-Goals** — what the system will not do
* **Phase 4 Known Limitations** — where detection cannot guarantee outcomes
* **Phase 4 Risk Mitigation Map** — how risks are constrained and evidenced

These documents exist to support technical diligence and governance review.

---

## Positioning Summary

VoxelMask is **not** an automated de-identification engine.
It is a **governance-aligned support tool** designed to make de-identification workflows:

* More transparent
* More reviewable
* More defensible

without introducing clinical risk or hidden automation.

---

## Intended Evaluation Context

* Pilot / proof-of-concept
* FOI and research preparation workflows
* PACS-adjacent, copy-out environments
* Human-in-the-loop review

---

**In short:**
VoxelMask improves *how well risks are seen*, not *how quickly actions are taken*.

---

## Document Metadata

| Field               | Value                                      |
|---------------------|--------------------------------------------|
| **Version**         | 1.0                                        |
| **Created**         | 2025-12-16                                 |
| **Classification**  | External / Vendor / Diligence              |
| **Audience**        | Vendors, Acquirers, External Stakeholders  |
| **Related Docs**    | `PHASE4_NON_GOALS.md`, `PHASE4_KNOWN_LIMITATIONS.md`, `PHASE4_RISK_MITIGATION_MAP.md` |
