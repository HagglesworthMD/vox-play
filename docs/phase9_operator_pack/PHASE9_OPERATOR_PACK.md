# Phase 9 — Operator Pack

**Document ID:** PHASE9_OPERATOR_PACK  
**Status:** Active  
**Based on:** `v0.8.0-phase8-operational`  
**Last updated:** 2025-12-18

---

## Purpose

This pack provides everything an operator needs to run VoxelMask during internal pilot evaluation — without requiring developer assistance.

---

## What's In This Pack

| Document | Purpose |
| :--- | :--- |
| `PILOT_README.md` | How to run VoxelMask (minimal steps + guardrails) |
| `OPERATOR_CHECKLIST.md` | Pre-run / run / post-run checklist (printable) |
| `RUNBOOK_TROUBLESHOOTING.md` | Deterministic triage for common failures |
| `WHAT_THIS_IS_NOT.md` | Drift prevention (what VoxelMask is NOT) |
| `SAMPLE_RUN_ARTEFACTS.md` | Example outputs and folder layouts |

---

## Scope

This pack covers:

- ✅ Running VoxelMask on pilot/evaluation studies
- ✅ Understanding outputs and evidence artefacts
- ✅ Troubleshooting common failures
- ✅ Knowing the boundaries of the tool

---

## Non-Goals (Explicit)

This pack does NOT:

- ❌ Provide clinical or diagnostic guidance
- ❌ Guarantee complete PHI removal
- ❌ Cover PACS integration, routing, or worklist setup
- ❌ Replace formal training or certification

---

## Key Boundaries (Repeated in Every Document)

| Constraint | Meaning |
| :--- | :--- |
| **Copy-out only** | VoxelMask does not modify source studies in PACS |
| **Non-clinical pilot** | Outputs are for internal evaluation, not clinical routing |
| **Irreversible masking** | Masked regions cannot be recovered |
| **Operator review required** | Automated detection is not perfect; human review is mandatory |

---

## Version Baseline

This operator pack is validated against:

```
Tag:    v0.8.0-phase8-operational
Commit: 3606a9b
```

If you are running a different version, behaviour may differ.

---

## Where to Find Artefacts After a Run

| Artefact | Location |
| :--- | :--- |
| Output ZIP | `downloads/<study_name>.zip` |
| Run directory | `downloads/voxelmask_runs/<run_id>/` |
| Run status | `downloads/voxelmask_runs/<run_id>/run_status.json` |
| Run receipt | `downloads/voxelmask_runs/<run_id>/receipts/run_receipt.json` |
| Audit log | `downloads/voxelmask_runs/<run_id>/logs/VoxelMask_AuditLog_*.txt` |

---

## Questions?

If something is unclear or missing, document the gap and escalate. Do not improvise clinical workflows.
