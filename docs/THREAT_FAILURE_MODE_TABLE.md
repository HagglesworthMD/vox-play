# Threat / Failure Mode Table — Review-Gated Export (Sprint 2)

**Version:** v0.4.0-review-gated  
**Date:** 2025-12-15  
**Purpose:** Ensure safe failure, prevent PHI persistence, and maintain defensible audit semantics.

---

## Failure Mode Analysis

| Failure / Threat Scenario | What Could Go Wrong | Expected System Behaviour (Current) | Audit Outcome | Operator Outcome |
|---|---|---|---|---|
| Operator attempts export before accepting review | Release of unreviewed burned-in PHI risk | Export is blocked; explicit error shown | No Decision Trace commit | Operator must accept before export |
| Operator clicks Accept accidentally | Premature lock-in | Acceptance is explicit and one-way; UI warning displayed | Acceptance state reflected in workflow (no PHI persisted) | Operator cannot modify regions after accept |
| UI crash during review (pre-accept) | Loss of review progress | Session not accepted; export remains gated | No Decision Trace commit | Operator must re-open/review |
| Processing fails mid-run | Partial artefacts or inconsistent state | Export does not complete; ZIP not produced | No Decision Trace commit | Operator retries after addressing issue |
| ZIP creation fails after processing | "Audit says done" without deliverable | Decision Trace commit occurs only after ZIP creation | No Decision Trace commit | No export delivered; operator retries |
| Decision Trace DB write fails after ZIP creation | Export delivered without audit trail | Should fail closed (no release until audit commit succeeds) | No committed reviewer decisions | Operator sees failure; export not released |
| PDF generation fails | Missing audit summary artefact | Fail closed (treat as export failure) | No Decision Trace commit (if export not finalised) | Operator retries |
| Region list contains deleted regions | Incorrect audit accounting | Deleted regions excluded from summary/recording | Accurate counts only | Operator sees consistent summaries |
| OCR text contains PHI | PHI stored in logs | OCR text is never persisted | No PHI stored | N/A |
| Screenshot/thumb persistence | PHI artefact leakage | Thumbnails/screenshots not persisted | No PHI stored | N/A |
| Reviewer overrides ("don't mask") used | Masking not applied where risk exists | Override is explicit; summary records counts | Decision Trace records decision types | Operator remains accountable post-accept |
| Attempt to modify after accept | Post-accept tampering | ReviewSession is sealed; mutations rejected | Integrity preserved | Operator must start a new session/workflow |
| Replay/resume ambiguity | "Which decisions applied?" | Decisions committed only for the accepted session at export | Single commit point tied to export | Clear "accepted then exported" narrative |

---

## Safety Properties Summary

### Fail-Closed Behaviours

| Trigger | System Response |
|---------|-----------------|
| Export attempted without accept | ❌ Blocked |
| ZIP creation fails | ❌ No audit commit |
| Decision Trace write fails | ❌ Export not released |
| Session sealed | ❌ Mutations rejected |

### PHI Non-Persistence Guarantees

| Artefact Type | Persisted? |
|---------------|------------|
| OCR text content | ❌ Never |
| Image thumbnails | ❌ Never |
| Screenshots | ❌ Never |
| Region coordinates | ✅ Yes (non-PHI) |
| Decision types (MASK/UNMASK) | ✅ Yes (non-PHI) |
| Counts only | ✅ Yes (non-PHI) |

### Atomicity Properties

```
Processing Complete
        ↓
   ZIP Created ────────────────┐
        ↓                      │
   (If ZIP fails)              │
        ↓                      │
   ❌ No audit commit          │
                               │
   (If ZIP succeeds) ──────────┘
        ↓
   Decision Trace Commit
        ↓
   Export Released ✅
```

---

## Operator Accountability

| Action | Operator Responsibility |
|--------|------------------------|
| Review regions | Required before accept |
| Click "Accept & Continue" | Explicit acknowledgement |
| Override ("don't mask") | Recorded; operator accountable |
| Retry on failure | Must re-review if session lost |

---

## Notes

- This table is intended for **pilot governance discussions** and **vendor due diligence**.
- It describes **safety properties**, not claims of perfect PHI removal.
- All failure modes result in **conservative outcomes** (deny export, reject writes).

---

## Related Documents

- `docs/SPRINT_2_REVIEW_GATED_EXPORT.md` — Governance specification
- `docs/RELEASE_FREEZE_v0.4.0.md` — Change control policy
