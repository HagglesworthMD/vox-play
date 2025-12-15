# Pilot Assurance Overview — VoxelMask (Audit + Review-Gated Export)

**Tag baseline:** v0.4.0-review-gated  
**Audience:** PACS / Imaging Ops, Information Governance, Vendor Reviewers  
**Scope:** Non-clinical, copy-out only, pilot evaluation / research workflows

---

## What VoxelMask Is (Pilot Scope)

VoxelMask is a PACS-adjacent de-identification workflow focused on:
- Deterministic DICOM metadata anonymisation
- Burned-in PHI detection support and pixel masking
- Human-in-the-loop review for burned-in PHI risk cases
- Audit-grade traceability (SQLite + PDF artefacts)

**Pilot constraints (hard):**
- Copy-out only (no PACS write-back)
- Non-clinical use (no diagnostic/clinical claims)
- No claims of perfect PHI removal
- No RIS/MPPS/worklist integration

---

## Sprint 1 — Audit Decision Trace (v0.3.1-audit-trace)

Sprint 1 established the audit-grade accountability foundation:
- Deterministic ReasonCode taxonomy
- Decision Trace capture for key actions and outcomes
- PHI-free audit logging enforced by unit tests
- SQLite persistence for audit events
- Exportable PDF summary artefacts

**Assurance intent:**
- Provide a defensible account of "what was done, why, and when"
- Ensure logs remain PHI-free by construction and test enforcement

---

## Sprint 2 — Burned-In PHI Review Overlay with Gated Export (v0.4.0-review-gated)

Sprint 2 introduced human-in-the-loop review for pixel PHI risk cases (e.g., US/SC/doc-like):
- ReviewSession / ReviewRegion model with deterministic state transitions
- Interactive UI controls for region decisions (mask / don't mask / manual regions)
- Explicit "Accept & Continue" gating
- Export blocked until review is accepted when required
- Reviewer decisions recorded to Decision Trace only at export time
- PDF includes reviewer summary as counts only (no PHI content)

**Key control:** export cannot proceed for review-required inputs until explicit acceptance occurs.

---

## Control Semantics (Operator + Audit)

### Review Gating
- If burned-in review is required: export is disabled until `review_accepted == True`.
- If review is not applicable: export proceeds without the gate.

### Acceptance Semantics
- Acceptance is explicit and one-way.
- Once accepted, the review session is sealed (immutable); post-accept mutations are rejected.

### Audit Timing Guarantee (Atomicity)
Reviewer decisions are committed only after successful export artefact creation:
1. Processing and masking complete
2. ZIP export artefact successfully created
3. Reviewer decisions recorded and committed to Decision Trace (SQLite)
4. Export artefacts (ZIP + PDF) made available

**Guarantee:**
- If export fails before artefact creation: **no reviewer Decision Trace commit occurs**.

---

## Failure / Threat Model

A structured threat / failure mode analysis is maintained in:
- `docs/THREAT_FAILURE_MODE_TABLE.md`

It documents:
- Failure scenario
- Expected system behaviour (fail-closed)
- Audit outcomes
- Operator outcomes

This is intended for governance review and vendor due diligence.

---

## PHI Safety Boundaries (Pilot)

By design and policy:
- OCR text is not persisted
- Thumbnails/screenshots are not persisted
- Audit artefacts store counts and decision metadata only (no PHI payload)

---

## Explicit Non-Claims (Important)

VoxelMask does **not** claim:
- Perfect PHI removal from pixels or metadata
- Clinical safety or diagnostic suitability
- Real-time clinical routing or production PACS integration
- RIS/MPPS/worklist correctness or coverage
- That human review can be replaced or bypassed

VoxelMask is intended for:
- Pilot evaluation
- Research workflows
- Governance-aligned de-identification where human confirmation is required

---

## Release Freeze / Change Control

The baseline control guarantees for `v0.4.0-review-gated` are protected by:
- `docs/RELEASE_FREEZE_v0.4.0.md`

Any change affecting:
- export gating
- accept semantics
- Decision Trace write timing
- audit artefacts

…requires explicit review and updated tests demonstrating unchanged guarantees.

---

## Related Documents

| Document | Purpose |
|----------|---------|
| `SPRINT_2_REVIEW_GATED_EXPORT.md` | Technical governance specification |
| `RELEASE_FREEZE_v0.4.0.md` | Change control policy |
| `THREAT_FAILURE_MODE_TABLE.md` | Failure mode analysis |
| `FREEZE_LOG.md` | Daily observations during freeze period |
