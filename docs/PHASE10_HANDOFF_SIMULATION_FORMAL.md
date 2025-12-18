# PHASE 10 — Internal Handoff Simulation (Formal)

**VoxelMask v0.9.0-phase9-operator-pack**

> This document presents the Phase 10 handoff scenario in a governance-oriented format for audit and vendor review. It does not introduce new behaviour. A narrative-oriented rendering of the same scenario is available in `PHASE10_HANDOFF_SIMULATION.md`.

---

## Purpose

This document simulates a realistic internal pilot handoff of VoxelMask to an operator **without involvement from the system author**.

The objective is to demonstrate:

* Operator self-sufficiency
* Deterministic system behaviour
* Governance-safe failure handling
* Audit-grade artefact availability

This is a **fictional but operationally realistic scenario**, based entirely on documented behaviour and artefacts available at `v0.9.0-phase9-operator-pack`.

---

## 1. Scenario Context

| Attribute | Value |
| :--- | :--- |
| Request Type | Internal research workflow support |
| Clinical Status | Non-clinical, copy-out only |
| Routing/Write-back | None |
| Input Data | Synthetic / test DICOM studies staged in a non-production directory |
| Operator Role | Imaging systems staff member (no developer access) |

**Documentation Available to Operator:**

* `PILOT_README.md`
* `OPERATOR_CHECKLIST.md`
* `RUNBOOK_TROUBLESHOOTING.md`
* `WHAT_THIS_IS_NOT.md`

---

## 2. Operator Preparation (Pre-Run)

The operator performs the **Pre-Run checklist** from `OPERATOR_CHECKLIST.md`:

- [x] Confirms VoxelMask version: `v0.9.0-phase9-operator-pack`
- [x] Confirms **copy-out only** operation
- [x] Confirms non-clinical dataset
- [x] Confirms output directory is writable and empty
- [x] Confirms selected compliance profile is appropriate for research use

No deviations from the checklist are recorded.

---

## 3. Run Initiation

The operator starts a new run using the documented process.

### System Behaviour (Observed)

| Event | Status |
| :--- | :--- |
| Run ID generated | ✓ |
| Canonical run paths created | ✓ |
| Preflight checks | Passed |
| `run_status.json` created | ✓ (status: `in_progress`) |
| `started_at` timestamp recorded | ✓ (UTC ISO-8601) |

No warnings or errors are presented during startup.

---

## 4. Processing Outcome (Simulated Failure Case)

During processing, no output files are successfully produced.

This scenario intentionally demonstrates a **safe failure path**.

### System Behaviour (Observed)

| Event | Status |
| :--- | :--- |
| Processing completes | ✓ (no crash) |
| Files meeting processing criteria | 0 |
| Run state transition | → `failed` |
| `failed_at` timestamp recorded | ✓ |
| Failure reason recorded | `no_files_processed` |

Processing terminates cleanly.  
No partial or ambiguous outputs are produced.

---

## 5. Artefacts Produced

The following artefacts are present on disk after run completion:

### Run Status

`run_status.json` (excerpt):

```json
{
  "run_id": "VM_RUN_example123",
  "started_at": "2025-12-18T01:12:00+00:00",
  "status": "failed",
  "failed_at": "2025-12-18T01:12:32+00:00",
  "failure_reason": "no_files_processed"
}
```

### Evidence / Receipts

| Property | Status |
| :--- | :--- |
| PHI-sterile evidence receipt | Generated |
| Patient identifiers present | None |
| Pixel data embedded | None |
| Timestamps | Deterministic |
| Paths | Canonical |

### Output Bundle

| Property | Status |
| :--- | :--- |
| Output ZIP produced | No (expected for this failure mode) |
| Residual temporary files | None outside run directory |

---

## 6. Operator Triage (Using Runbook Only)

The operator refers to `RUNBOOK_TROUBLESHOOTING.md`, section:

> **Failure: `no_files_processed`**

Following the documented guidance, the operator:

- [x] Confirms SOP classes of input files
- [x] Confirms files are readable DICOM
- [x] Confirms modality support expectations
- [x] Confirms this is a non-clinical test dataset

**Escalation required:** No  
**System changes attempted:** None

---

## 7. Governance Review Perspective

From a governance or audit standpoint, the following are available:

| Question | Answer |
| :--- | :--- |
| What was the run ID? | `VM_RUN_example123` |
| When did the run start? | `2025-12-18T01:12:00+00:00` |
| When did the run end? | `2025-12-18T01:12:32+00:00` |
| What was the outcome? | `failed` |
| What was the failure reason? | `no_files_processed` |
| Was PHI exposed? | No |
| Were partial outputs produced? | No |
| Is the failure reason explicit? | Yes |

There is no ambiguity about:

* What was attempted
* What occurred
* Whether PHI was exposed
* Whether partial outputs exist

---

## 8. Outcome

The simulated handoff demonstrates that:

| Claim | Demonstrated |
| :--- | :--- |
| Operator can run VoxelMask using documentation alone | ✓ |
| Failures are explicit, safe, and auditable | ✓ |
| No developer intervention required to interpret outcomes | ✓ |
| Governance artefacts are complete even in failure cases | ✓ |

This concludes the Phase 10 internal handoff simulation (formal rendering).

---

## Document Metadata

| Field | Value |
| :--- | :--- |
| Phase | 10 — Internal Handoff Simulation |
| Rendering | Formal (governance/vendor) |
| Code Changes | None |
| Baseline Tag | `v0.9.0-phase9-operator-pack` |
| Related Document | `PHASE10_HANDOFF_SIMULATION.md` (narrative rendering) |
