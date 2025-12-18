# VoxelMask — Artefact Index

**Purpose:** Navigation guide for readers arriving at this repository.  
**Baseline:** `v0.9.0-phase9-operator-pack`

---

## By Role

### If you are an operator (imaging systems staff)

Start here:

| Document | Location |
| :--- | :--- |
| Pilot overview | [`docs/phase9_operator_pack/PILOT_README.md`](./phase9_operator_pack/PILOT_README.md) |
| Pre-run and post-run checklist | [`docs/phase9_operator_pack/OPERATOR_CHECKLIST.md`](./phase9_operator_pack/OPERATOR_CHECKLIST.md) |
| Troubleshooting runbook | [`docs/phase9_operator_pack/RUNBOOK_TROUBLESHOOTING.md`](./phase9_operator_pack/RUNBOOK_TROUBLESHOOTING.md) |
| Scope boundaries | [`docs/phase9_operator_pack/WHAT_THIS_IS_NOT.md`](./phase9_operator_pack/WHAT_THIS_IS_NOT.md) |

---

### If you are governance or audit

Start here:

| Document | Location |
| :--- | :--- |
| Formal handoff simulation | [`docs/PHASE10_HANDOFF_SIMULATION_FORMAL.md`](./PHASE10_HANDOFF_SIMULATION_FORMAL.md) |
| Evidence bundle schema | [`docs/PHASE5C_GATE2_EVIDENCE_BUNDLE_SCHEMA.md`](./PHASE5C_GATE2_EVIDENCE_BUNDLE_SCHEMA.md) |
| Audit completeness gate | [`docs/PHASE5C_GATE3_AUDIT_COMPLETENESS.md`](./PHASE5C_GATE3_AUDIT_COMPLETENESS.md) |
| Sample run artefacts | [`docs/phase9_operator_pack/SAMPLE_RUN_ARTEFACTS.md`](./phase9_operator_pack/SAMPLE_RUN_ARTEFACTS.md) |
| Threat and failure mode table | [`docs/THREAT_FAILURE_MODE_TABLE.md`](./THREAT_FAILURE_MODE_TABLE.md) |

---

### If you are a vendor or external evaluator

Start here:

| Document | Location |
| :--- | :--- |
| Executive summary | [`docs/PHASE5B_EXECUTIVE_SUMMARY.md`](./PHASE5B_EXECUTIVE_SUMMARY.md) |
| Vendor briefing | [`docs/PHASE4_VENDOR_BRIEFING.md`](./PHASE4_VENDOR_BRIEFING.md) |
| Known limitations | [`docs/PHASE4_KNOWN_LIMITATIONS.md`](./PHASE4_KNOWN_LIMITATIONS.md) |
| Non-goals | [`docs/PHASE4_NON_GOALS.md`](./PHASE4_NON_GOALS.md) |
| Handoff simulation (narrative) | [`docs/PHASE10_HANDOFF_SIMULATION.md`](./PHASE10_HANDOFF_SIMULATION.md) |

---

### If you are a developer

Start here:

| Document | Location |
| :--- | :--- |
| User guide | [`docs/USER_GUIDE.md`](./USER_GUIDE.md) |
| Freeze log | [`docs/FREEZE_LOG.md`](./FREEZE_LOG.md) |
| Masking design | [`docs/PHASE5B_MASKING_DESIGN.md`](./PHASE5B_MASKING_DESIGN.md) |
| Decision trace audit | [`docs/SPRINT1_AUDIT_DECISION_TRACE.md`](./SPRINT1_AUDIT_DECISION_TRACE.md) |

---

## By Tag

| Tag | Phase | Description |
| :--- | :--- | :--- |
| `v0.9.0-phase9-operator-pack` | 9 | Operator documentation pack for internal pilot |
| `v0.10.0-phase10-handoff-simulation` | 10 | Handoff simulation (narrative proof of operability) |

To check out a specific tag:

```bash
git checkout v0.9.0-phase9-operator-pack
```

---

## Scope Boundaries

VoxelMask is documented to be:

- Copy-out only (source data is not modified)
- Non-clinical (pilot/evaluation use)
- Operator-reviewed (no silent automation)

For explicit scope exclusions, see [`docs/phase9_operator_pack/WHAT_THIS_IS_NOT.md`](./phase9_operator_pack/WHAT_THIS_IS_NOT.md).

---

## Document Maintenance

This index points to existing artefacts. It does not introduce new claims or behaviour.

Last updated: 2025-12-18
