# Phase 12 — Binary Activation Checklist

**Purpose:** Determine whether VoxelMask may transition from internal pilot artefact to externally legible evaluation product.

**Rule:** If ANY mandatory gate is **NO** or **UNCERTAIN**, Phase 12 **does not activate**. No exceptions. No partial credit.

**Audience:** Hospital governance, PACS management, vendor diligence teams.

**Date:** 2025-12-18

---

## Instructions

For each gate:

- Mark `[x]` for **YES** (verified, artefact exists, constraint met)
- Mark `[ ]` for **NO** (not met, artefact missing, constraint violated)
- **N/A is not permitted** for mandatory gates

If you cannot confidently mark YES, mark NO.

---

## Section 1 — Scope & Governance Locks

| # | Gate | Artefact Reference | Status |
|---|------|-------------------|--------|
| 1.1 | Processing scope is frozen (no new features permitted) | `docs/FREEZE_LOG.md` (Phase 5C Close-Out) | [ ] YES / [ ] NO |
| 1.2 | Recoverability model is declared and locked (Model B — External) | `docs/PHASE5C_GATE2_DECISION_RECORD.md` | [ ] YES / [ ] NO |
| 1.3 | Audit schema is frozen | `docs/PHASE5C_GATE2_EVIDENCE_BUNDLE_SCHEMA.md` | [ ] YES / [ ] NO |
| 1.4 | Series order preservation is proven | `docs/PHASE5C_GATE1_SERIES_ORDER_PRESERVATION.md` | [ ] YES / [ ] NO |
| 1.5 | Non-goals are explicitly documented | `docs/PHASE4_NON_GOALS.md` | [ ] YES / [ ] NO |
| 1.6 | Known limitations are explicitly documented | `docs/PHASE4_KNOWN_LIMITATIONS.md` | [ ] YES / [ ] NO |

**Section 1 Outcome:**

```
[ ] PASS — All gates YES
[ ] FAIL — Phase 12 must not activate
```

---

## Section 2 — UI & Semantic Integrity

| # | Gate | Artefact Reference | Status |
|---|------|-------------------|--------|
| 2.1 | UI language is frozen | `docs/FREEZE_LOG.md` (Phase 6 entry) | [ ] YES / [ ] NO |
| 2.2 | Forbidden words list is defined and enforced | `docs/FREEZE_LOG.md` (Language Rules Locked) | [ ] YES / [ ] NO |
| 2.3 | No reversible-looking actions (undo, restore, re-identify) | `docs/PHASE4_NON_GOALS.md` §7, `FREEZE_LOG.md` Phase 5C | [ ] YES / [ ] NO |
| 2.4 | No "confidence", "success rate", or "AI-ish" language | `docs/FREEZE_LOG.md` (Phase 6) | [ ] YES / [ ] NO |
| 2.5 | NON-CLINICAL disclaimer permanently visible | `src/app.py` footer | [ ] YES / [ ] NO |
| 2.6 | COPY-OUT mode permanently visible | `src/app.py` header/subheading | [ ] YES / [ ] NO |
| 2.7 | Errors are blocking and declarative (not dismissible warnings) | Runtime behaviour | [ ] YES / [ ] NO |

**Section 2 Outcome:**

```
[ ] PASS — All gates YES
[ ] FAIL — Phase 12 must not activate
```

---

## Section 3 — Operator Independence

| # | Gate | Artefact Reference | Status |
|---|------|-------------------|--------|
| 3.1 | Operator checklist exists | `docs/phase9_operator_pack/OPERATOR_CHECKLIST.md` | [ ] YES / [ ] NO |
| 3.2 | Troubleshooting runbook exists | `docs/phase9_operator_pack/RUNBOOK_TROUBLESHOOTING.md` | [ ] YES / [ ] NO |
| 3.3 | Pilot README exists | `docs/phase9_operator_pack/PILOT_README.md` | [ ] YES / [ ] NO |
| 3.4 | Scope boundaries documented ("what this is not") | `docs/phase9_operator_pack/WHAT_THIS_IS_NOT.md` | [ ] YES / [ ] NO |
| 3.5 | Sample run artefacts documented | `docs/phase9_operator_pack/SAMPLE_RUN_ARTEFACTS.md` | [ ] YES / [ ] NO |
| 3.6 | **Operator Substitution Test:** A random PACS engineer, given only the UI, artefacts, and exported audit report, can explain what VoxelMask does without author present | Simulated in `docs/PHASE10_HANDOFF_SIMULATION_FORMAL.md` | [ ] YES / [ ] NO |

**Section 3 Outcome:**

```
[ ] PASS — All gates YES
[ ] FAIL — Phase 12 must not activate
```

---

## Section 4 — Evidence & Audit Continuity

| # | Gate | Artefact Reference | Status |
|---|------|-------------------|--------|
| 4.1 | For any processed study, an auditor can determine: **what was ingested** | Evidence bundle `source_object_record` | [ ] YES / [ ] NO |
| 4.2 | For any processed study, an auditor can determine: **under what declared intent** | Evidence bundle `job_manifest.profile` | [ ] YES / [ ] NO |
| 4.3 | For any processed study, an auditor can determine: **what transformations were applied** | Evidence bundle `mask_plan`, `decision_record` | [ ] YES / [ ] NO |
| 4.4 | For any processed study, an auditor can determine: **what was NOT claimed** | `docs/PHASE4_KNOWN_LIMITATIONS.md`, `docs/PHASE4_NON_GOALS.md` | [ ] YES / [ ] NO |
| 4.5 | For any processed study, an auditor can determine: **who ran it** | Evidence bundle `job_manifest.operator` (or host) | [ ] YES / [ ] NO |
| 4.6 | For any processed study, an auditor can determine: **when** | Evidence bundle `job_manifest.started_at`, `completed_at` | [ ] YES / [ ] NO |
| 4.7 | For any processed study, an auditor can determine: **with which version** | Evidence bundle `job_manifest.version` | [ ] YES / [ ] NO |
| 4.8 | Nothing about processing feels "implicit" | Reviewer judgment | [ ] YES / [ ] NO |

**Section 4 Outcome:**

```
[ ] PASS — All gates YES
[ ] FAIL — Phase 12 must not activate
```

---

## Section 5 — Failure Mode Explicitness

| # | Gate | Artefact Reference | Status |
|---|------|-------------------|--------|
| 5.1 | Failure modes are documented | `docs/phase9_operator_pack/RUNBOOK_TROUBLESHOOTING.md` | [ ] YES / [ ] NO |
| 5.2 | OCR uncertainty is explicitly handled (not hidden) | `docs/PHASE4_KNOWN_LIMITATIONS.md` | [ ] YES / [ ] NO |
| 5.3 | No "this might work" states exist in UI flow | Runtime behaviour | [ ] YES / [ ] NO |
| 5.4 | No optional-but-dangerous paths exist | Runtime behaviour | [ ] YES / [ ] NO |
| 5.5 | All processing paths terminate in explicit success or explicit failure | Runtime behaviour | [ ] YES / [ ] NO |
| 5.6 | Failure reasons are recorded in run status | `run_status.json` schema | [ ] YES / [ ] NO |

**Section 5 Outcome:**

```
[ ] PASS — All gates YES
[ ] FAIL — Phase 12 must not activate
```

---

## Section 6 — Misuse Resistance

| # | Gate | Artefact Reference | Status |
|---|------|-------------------|--------|
| 6.1 | Clinical routing is not possible | Architecture (copy-out only) | [ ] YES / [ ] NO |
| 6.2 | Write-back to PACS is not possible | Architecture (no DICOM C-STORE to source) | [ ] YES / [ ] NO |
| 6.3 | Background automation is not possible | Architecture (requires operator presence) | [ ] YES / [ ] NO |
| 6.4 | Claims of completeness are not present | `docs/PHASE4_NON_GOALS.md` §2 | [ ] YES / [ ] NO |
| 6.5 | "AI" framing is not present | `docs/FREEZE_LOG.md` (forbidden words) | [ ] YES / [ ] NO |
| 6.6 | Performance boasting is not present | UI and documentation audit | [ ] YES / [ ] NO |
| 6.7 | Workflow shortcuts that bypass review are not possible | Architecture (gated export) | [ ] YES / [ ] NO |

**Section 6 Outcome:**

```
[ ] PASS — All gates YES
[ ] FAIL — Phase 12 must not activate
```

---

## Section 7 — Distribution Safety

| # | Gate | Artefact Reference | Status |
|---|------|-------------------|--------|
| 7.1 | Internal distribution to imaging teams is safe | Operator pack exists | [ ] YES / [ ] NO |
| 7.2 | "Have a look at this tool" conversations are safe | Vendor briefing exists (`docs/PHASE4_VENDOR_BRIEFING.md`) | [ ] YES / [ ] NO |
| 7.3 | Pilot evaluations without hand-holding are safe | Operator Substitution Test (3.6) passed | [ ] YES / [ ] NO |
| 7.4 | Cold-reader artefact review is safe | Artefact index exists (`docs/ARTEFACT_INDEX.md`) | [ ] YES / [ ] NO |
| 7.5 | Quiet vendor curiosity is safe | Executive summary exists (`docs/PHASE5B_EXECUTIVE_SUMMARY.md`) | [ ] YES / [ ] NO |

**Section 7 Outcome:**

```
[ ] PASS — All gates YES
[ ] FAIL — Phase 12 must not activate
```

---

## Section 8 — Acquisition Readiness Signal

| # | Gate | Artefact Reference | Status |
|---|------|-------------------|--------|
| 8.1 | Threat and failure mode table exists | `docs/THREAT_FAILURE_MODE_TABLE.md` | [ ] YES / [ ] NO |
| 8.2 | Pilot assurance overview exists | `docs/PILOT_ASSURANCE_OVERVIEW.md` | [ ] YES / [ ] NO |
| 8.3 | Release freeze policy is documented | `docs/RELEASE_FREEZE_v0.4.0.md` | [ ] YES / [ ] NO |
| 8.4 | All existing tests pass | `pytest` output | [ ] YES / [ ] NO |
| 8.5 | Git tag for current baseline exists | `git tag -l` | [ ] YES / [ ] NO |

**Section 8 Outcome:**

```
[ ] PASS — All gates YES
[ ] FAIL — Phase 12 must not activate
```

---

## Final Determination

**All section outcomes must be PASS.**

| Section | Outcome |
|---------|---------|
| 1 — Scope & Governance Locks | [ ] PASS / [ ] FAIL |
| 2 — UI & Semantic Integrity | [ ] PASS / [ ] FAIL |
| 3 — Operator Independence | [ ] PASS / [ ] FAIL |
| 4 — Evidence & Audit Continuity | [ ] PASS / [ ] FAIL |
| 5 — Failure Mode Explicitness | [ ] PASS / [ ] FAIL |
| 6 — Misuse Resistance | [ ] PASS / [ ] FAIL |
| 7 — Distribution Safety | [ ] PASS / [ ] FAIL |
| 8 — Acquisition Readiness Signal | [ ] PASS / [ ] FAIL |

---

## Activation Decision

```
[ ] PHASE 12 ACTIVATED
    All sections PASS. System may be used by non-authors without explanation.

[ ] PHASE 12 NOT ACTIVATED
    One or more sections FAIL. System remains in internal pilot posture.
    Failed gates must be documented. No remediation required — hold is acceptable.
```

---

## Signature Block

| Field | Value |
|-------|-------|
| Checklist completed by | |
| Role | |
| Date | |
| Baseline tag | |

---

## Document Metadata

| Field | Value |
|-------|-------|
| Version | 1.0 |
| Created | 2025-12-18 |
| Classification | Governance / Activation Gate |
| Audience | Internal governance, PACS management, vendor diligence |

---

*This checklist is audit-grade. It does not introduce new requirements. It tests claims already made.*
