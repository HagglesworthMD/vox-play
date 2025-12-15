# Sprint 2 Review — Burned-In PHI Review Overlay (Gated Export)

**Version:** v0.4.0-review-gated  
**Scope:** Sprint 2 PR 1–5  
**Status:** Complete (pilot-safe)  
**Date:** 2025-12-15

---

## Purpose

Sprint 2 adds a human-in-the-loop burned-in PHI review workflow for modalities with pixel-embedded text risk (e.g., US/SC/doc-like content). The workflow is explicitly non-clinical and copy-out only, and is designed to be auditable, deterministic, and governance-defensible.

---

## Review Gating

Export is blocked until the operator explicitly completes and accepts the burned-in PHI review when a review is required.

### Gate Condition

- If the input set requires burned-in PHI review:
  - Export is disabled until `ReviewSession.review_accepted == True`.
- If a review is not applicable for the input set:
  - Export proceeds without the burned-in review gate.

### Rationale

This prevents accidental release of data where pixel PHI risk exists and creates an explicit, enforceable operator responsibility boundary.

---

## Accept Semantics

Acceptance is a deliberate, one-way transition.

### Behaviour

- The UI presents an **"Accept & Continue"** action only when acceptance is valid (session started, not yet accepted).
- On acceptance:
  - `ReviewSession.accept()` is called.
  - The session is **sealed** (immutable).
  - Further region mutations are rejected (no add/edit/delete/toggle).

### Operator Meaning

Acceptance indicates the operator has reviewed the regions and acknowledges that the export will apply the final masking decisions.

### Governance Notes

- Acceptance is never inferred from navigation or export attempts.
- Acceptance is required only when burned-in PHI review is applicable.
- No OCR text, thumbnails, or screenshots are persisted as part of acceptance.

---

## Audit Timing Guarantees

Decision Trace persistence for reviewer actions occurs at export time and is sequenced to avoid "audit says yes but export failed" states.

### Timing

1. Input processing and masking complete in memory.
2. ZIP export artefact is created successfully.
3. Reviewer region decisions are recorded to Decision Trace (collector → writer) and committed.
4. Export artefacts (ZIP + PDF summary) are made available.

### Guarantees

- If export fails prior to ZIP creation: **no Decision Trace commit** occurs.
- Decision Trace writes happen only after export artefacts exist, avoiding partial audit records.
- Reviewer summary in the PDF contains **counts only** (no PHI content).

---

## PHI Safety Boundaries (Sprint 2)

- No OCR text is persisted.
- No burned-in image thumbnails or screenshots are persisted.
- Review artefacts stored/recorded are limited to non-PHI decision metadata (e.g., counts and decision types), consistent with pilot governance constraints.

---

## Architecture Summary

### Components

| Module | Role |
|--------|------|
| `review_session.py` | ReviewSession state, ReviewRegion dataclass, action enums |
| `decision_trace.py` | DecisionTraceCollector, DecisionTraceWriter, record_region_decisions() |
| `app.py` | UI scaffold, accept button, export gating, PDF integration |

### Data Flow

```
Upload DICOM → Modality Check → PHI Review Required?
                                        │
                    ┌───────────────────┴───────────────────┐
                    │                                       │
                    ▼                                       ▼
           [Review Panel]                           [Direct Export]
                    │
                    ▼
        Add/Toggle/Delete Regions
                    │
                    ▼
         Click "Accept & Continue"
                    │
                    ▼
           review_session.accept()
                    │
                    ▼
            Session Sealed (immutable)
                    │
                    ▼
        Export Button Enabled (gating passes)
                    │
                    ▼
              Process Files
                    │
                    ▼
           Create ZIP Artefact
                    │
                    ▼
    record_region_decisions() → DecisionTraceWriter.commit()
                    │
                    ▼
          Generate PDF Report
                    │
                    ▼
        Download Available ✓
```

---

## Testing Coverage

### Unit Tests Added (Sprint 2)

| Test File | Coverage |
|-----------|----------|
| `test_review_session_unit.py` | ReviewSession, ReviewRegion, enums |
| `test_decision_trace_unit.py` | DecisionTraceCollector, DecisionTraceWriter |
| `test_review_session_accept.py` | Accept gating, sealing, Decision Trace integration |

### Key Test Cases

- New session cannot accept (review not started)
- Started session can accept
- Accept seals session (immutable)
- Cannot accept twice
- Cannot accept without starting
- Sealed session rejects modifications
- record_region_decisions() creates correct decisions
- Overrides recorded with USER_OVERRIDE_RETAIN
- Deleted regions excluded from recording
- Collector locks after commit
- Summary counts exclude deleted regions

---

## PR History

| PR | Title | Commit |
|----|-------|--------|
| PR 1 | ReviewSession + ReviewRegion data structures | — |
| PR 2 | Decision Trace mapping for reviewer actions | — |
| PR 3 | UI scaffold for burned-in PHI review | — |
| PR 4 | Interactive region controls (toggle, bulk, manual) | `3aa935a` |
| PR 5 | Accept gating + export integration | `838fd49` |

---

## Out of Scope / Non-Goals (Explicit)

- ❌ No PACS write-back (copy-out only)
- ❌ No claims of perfect PHI removal
- ❌ No RIS/MPPS/worklist integration
- ❌ No clinical routing or clinical usage assumptions
- ❌ No reviewer identity persistence (operator is anonymous for pilot)
- ❌ No automatic OCR (manual region drawing only in current version)

---

## Governance Attestation

This implementation:

1. **Preserves operator responsibility** — The human must explicitly accept before export.
2. **Maintains audit integrity** — Decisions are recorded only after successful export.
3. **Avoids PHI in audit trail** — Only counts and decision types are persisted.
4. **Supports regulatory review** — All decisions are traceable to enumerated reason codes.

---

## Version History

| Version | Date | Changes |
|---------|------|---------|
| v0.4.0-review-gated | 2025-12-15 | Sprint 2 complete |
