# Release Freeze — v0.4.0-review-gated

**Tag:** `v0.4.0-review-gated`  
**Date:** 2025-12-15  
**Status:** Sprint 2 Pilot Workflow Baseline  

---

## Freeze Intent

This tag represents the Sprint 2 pilot workflow baseline for the Burned-In PHI Review Overlay with Gated Export.

### Protected Guarantees

The following behaviours are frozen and must not be weakened:

| Guarantee | Description |
|-----------|-------------|
| **Auditability** | All reviewer decisions are recorded with enumerated reason codes |
| **Acceptance Gating** | Export is blocked until explicit `ReviewSession.accept()` |
| **Decision Trace Timing** | Audit writes occur only after successful export artefact creation |
| **PHI Boundaries** | No OCR text, screenshots, or thumbnails are persisted |

### Prohibited Changes

Any change that:

- ❌ Weakens auditability
- ❌ Allows export without explicit acceptance
- ❌ Alters Decision Trace write timing (audit before export succeeds)
- ❌ Persists OCR text, screenshots, or thumbnails
- ❌ Introduces routing, write-back, or automation that blurs clinical vs non-clinical use

...is prohibited without explicit governance review.

---

## Change Control

Any modification affecting the following areas requires:

1. **Explicit review** by project governance
2. **Updated tests** demonstrating unchanged guarantees
3. **Documentation update** to `docs/SPRINT_2_REVIEW_GATED_EXPORT.md`

### Protected Areas

| Module | Protected Behaviour |
|--------|---------------------|
| `src/review_session.py` | `accept()`, `is_sealed()`, `can_accept()` |
| `src/decision_trace.py` | `record_region_decisions()`, `DecisionTraceWriter.commit()` |
| `src/app.py` | Export gating validation, Decision Trace commit timing |

### Required Tests

Changes to protected areas must pass:

- `tests/test_review_session_accept.py` — Accept gating and sealing
- `tests/test_decision_trace_unit.py` — Decision Trace integrity
- `tests/test_review_session_unit.py` — ReviewSession immutability

---

## Baseline Metrics

| Metric | Value |
|--------|-------|
| Total Tests | 483 |
| Tests Passing | 483 |
| Tests Skipped | 2 |
| Protected Area Tests | 12 (accept gating) + 14 (decision trace) |

---

## Version History

| Version | Date | Notes |
|---------|------|-------|
| v0.4.0-review-gated | 2025-12-15 | Sprint 2 freeze baseline |

---

## Governance Contact

Changes to frozen behaviours require review by the project maintainer before merge.
