# Gate 2 Decision Record (ADR)

**Title:** Gate 2 — Source Recoverability Model Selection  
**Status:** **Accepted**  
**Decision Date:** 2025-12-16  
**Project:** VoxelMask — PACS De-Identification Platform  
**Phase:** Phase 5C — Governance & Audit Hardening

---

## Context

VoxelMask performs **copy-out de-identification** of DICOM studies for non-clinical use cases (FOI, patient access, research).
A core design decision is how the platform handles **source recoverability** of original (unmasked) pixels after masking.

This decision directly affects:

* Governance risk and breach blast radius
* FOI / patient defensibility ("what was removed?")
* Acquisition readiness (vault vs processor)
* Alignment with Philips PACS / SAMI operational models
* Pilot safety ("copy-out only" purity)

Three recoverability models were evaluated:

| Model       | Summary                                                                                                                 |
| ----------- | ----------------------------------------------------------------------------------------------------------------------- |
| **Model A** | VoxelMask can re-create original pixels                                                                                 |
| **Model B** | VoxelMask cannot re-create originals, but verifiable linkage exists to an authoritative external source (PACS / escrow) |
| **Model C** | Irrecoverable by design                                                                                                 |

---

## Decision

**VoxelMask SHALL implement Model B — External Source Recoverability.**

VoxelMask will **never store identifiable original pixel data** nor retain sufficient reversible information to reconstruct original images.
Recoverability of original pixels remains **external and authoritative** (PACS by default).

VoxelMask SHALL instead provide a **verifiable evidence chain** that allows an auditor, given access to the original source, to independently confirm:

* provenance,
* detection,
* masking actions,
* and integrity of the de-identification process.

---

## Rationale

### Governance & Risk

* Avoids turning VoxelMask into a **high-risk image vault**
* Minimises breach blast radius
* Simplifies DPIA / PIA positioning
* Aligns with "boring infrastructure" acquisition expectations

### FOI / Patient Defensibility

* Supports "show what was removed" by enabling **independent verification against PACS**
* Evidence is deterministic, reproducible, and reviewable without PHI persistence

### PACS Operational Realism

* PACS remains the **system of record**
* VoxelMask operates as a **non-authoritative processor**
* Fully compatible with Philips / SAMI SOP and retention models

### Pilot Safety

* Preserves strict **copy-out only** behaviour
* Prevents shadow-PACS patterns during pilot and evaluation phases

---

## Explicit Constraints

* **VoxelMask MUST NOT store original pixel data**
* **VoxelMask MUST NOT store recovered PHI text** (e.g. OCR-extracted names)
* Audit artefacts may include **locations, confidence, and parameters only**
* Any future recoverability extension MUST remain **governance-controlled and external**

---

## Optional Extension (Non-Default)

**Governance Escrow Mode (Future / Optional)**

A sealed, externally governed escrow may retain originals **only** for edge cases (e.g. PACS retention expired).
VoxelMask may store:

* escrow reference ID
* sealed package hash

VoxelMask MUST NOT manage escrow access, keys, or content.

---

## Consequences

* Gate 3 (Audit Completeness) must ensure evidence is sufficient for **external verification**
* Storage footprint remains minimal and non-identifying
* Verification tooling becomes a first-class deliverable

---

## Decision Owner

VoxelMask Project Lead

---

## Related Documents

* `PHASE5C_GATE1_COMPLETION_RECORD.md` — Series Order Preservation (Gate 1 PASSED)
* `PHASE5C_GATE2_ARTIFACT_CHECKLIST.md` — Model B Evidence Requirements
* `PHASE5C_GATE3_AUDIT_COMPLETENESS.md` — Audit Completeness Specification

---

## Approval

| Role | Name | Date |
|------|------|------|
| Project Lead | Brian Shaw | 2025-12-16 |

---

**End of Gate 2 Decision Record**
