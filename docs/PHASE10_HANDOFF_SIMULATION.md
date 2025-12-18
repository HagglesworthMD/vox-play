# Phase 10 — Internal Handoff Simulation

**Purpose:** Demonstrate that VoxelMask can be operated without the author present.  
**Version:** `v0.9.0-phase9-operator-pack`  
**Status:** Fictional but realistic scenario for governance/vendor confidence.

---

## Scenario Context

### Request

Imaging Operations received an internal request:

> "We need to de-identify a recent ultrasound study for use in a vendor demonstration. The original study is in the active PACS archive. No PHI can leave the building. This is for evaluation only — not clinical use."

### Constraints

- Copy-out only — source study remains untouched in PACS
- Output must be PHI-sterile
- Must produce evidence of what was done
- Operator is not a developer

---

## Operator Actions

### Operator

**Kim (Imaging Ops Technician)**  
No prior VoxelMask experience. Given the Operator Checklist and 5 minutes of overview.

### Step 1: Pre-Run Checklist

Kim opens the printed `OPERATOR_CHECKLIST.md` and works through it:

| Checklist Item | Kim's Action |
| :--- | :--- |
| Confirm copy-out mode | ✅ Understood — outputs go to `downloads/`, not PACS |
| Select correct profile | ✅ "Internal Repair" selected (internal use, no external release) |
| Verify output path exists | ✅ Confirmed `downloads/` is writable |
| Confirm study type | ✅ This is an approved internal evaluation study |
| Check disk space | ✅ 12GB free |
| Upload files | ✅ Exported 47 DICOM files from PACS workstation, zipped, uploaded |

### Step 2: Run Execution

Kim proceeds through the application:

| Action | Observation |
| :--- | :--- |
| Preflight | ✅ Passed — green checkmarks |
| Region detection | 12 regions detected across 47 files |
| Region review | Kim reviews detected regions, toggles 2 to KEEP (vendor logo, laterality marker) |
| Accept & Continue | ✅ Clicked — processing begins |
| Processing | ✅ Complete — 47/47 files processed |
| Download | ✅ Downloaded `US_Abdomen_20251218.zip` |

### Step 3: Post-Run Checklist

| Checklist Item | Kim's Action |
| :--- | :--- |
| Download output ZIP | ✅ Saved to `Z:\VendorDemo\Staging\` |
| Locate run directory | ✅ Found `downloads/voxelmask_runs/VM_RUN_f7e8d9c0a1b2/` |
| Verify run status | ✅ `run_status.json` shows `"status": "completed"` |
| Collect evidence | ✅ Copied `run_receipt.json`, `run_status.json`, and audit log |
| Record run ID | ✅ Noted `VM_RUN_f7e8d9c0a1b2` in request ticket |

---

## System Behaviour

### Run Timeline

| Timestamp (local) | Event |
| :--- | :--- |
| 10:32:15 | Run context created |
| 10:32:16 | Preflight passed |
| 10:32:16 | Receipt written |
| 10:32:17 | Region detection started |
| 10:32:42 | Region detection complete (12 regions) |
| 10:34:10 | Operator accepted review |
| 10:34:11 | Processing started |
| 10:35:47 | Processing complete |
| 10:35:48 | Output ZIP created |
| 10:35:48 | Run status updated to `completed` |

### Status Transitions

```
pending → preflight_passed → processing → completed
```

---

## Outcome

**Status:** ✅ Completed successfully

### Artefacts Produced

| Artefact | Location | Present |
| :--- | :--- | :--- |
| Output ZIP | `downloads/US_Abdomen_20251218.zip` | ✅ |
| Run status | `.../VM_RUN_f7e8d9c0a1b2/run_status.json` | ✅ |
| Run receipt | `.../VM_RUN_f7e8d9c0a1b2/receipts/run_receipt.json` | ✅ |
| Audit log | `.../VM_RUN_f7e8d9c0a1b2/logs/VoxelMask_AuditLog_20251218_103215.txt` | ✅ |

### Evidence Bundle Contents

**run_status.json:**
```json
{
  "run_id": "VM_RUN_f7e8d9c0a1b2",
  "started_at": "2025-12-18T10:32:15+11:00",
  "status": "completed",
  "completed_at": "2025-12-18T10:35:48+11:00"
}
```

**run_receipt.json (excerpt):**
```json
{
  "run_id": "VM_RUN_f7e8d9c0a1b2",
  "processing_mode": "internal_repair",
  "selection_scope": {
    "include_images": true,
    "include_documents": false
  },
  "preflight": {
    "ok": true
  }
}
```

---

## Operator Issue Raised

### Incident

Two days later, Kim runs VoxelMask on a different study and gets:

> **"No files were processed successfully"**

Kim doesn't panic. Kim consults `RUNBOOK_TROUBLESHOOTING.md`.

### Diagnostic Steps (from Runbook)

1. Located run directory: `downloads/voxelmask_runs/VM_RUN_x1y2z3w4v5u6/`
2. Checked `run_status.json`:
   ```json
   {
     "run_id": "VM_RUN_x1y2z3w4v5u6",
     "started_at": "2025-12-20T14:15:00+11:00",
     "status": "failed",
     "failed_at": "2025-12-20T14:15:03+11:00",
     "failure_reason": "no_files_processed"
   }
   ```
3. Consulted Runbook "Common Causes" table
4. Identified likely cause: **All files were Encapsulated PDF (unsupported SOP class)**

### Resolution

Kim re-exported the study from PACS, this time excluding the PDF attachment objects. Second run succeeded.

**No escalation required. Resolved using documentation only.**

---

## What Governance Sees

### Audit Trail Summary

| Question | Answer |
| :--- | :--- |
| Who ran this? | Kim (Imaging Ops) |
| When? | 2025-12-18 10:32–10:35 local |
| What profile? | `internal_repair` |
| What was included? | Images only (documents excluded) |
| What was the outcome? | Completed successfully |
| What evidence exists? | `run_status.json`, `run_receipt.json`, audit log |
| Was PHI exposed? | No — all evidence artefacts are PHI-sterile |
| Was source data modified? | No — copy-out only |

### Governance Checklist

- [x] Operator followed documented procedure
- [x] System produced expected artefacts
- [x] Evidence is complete and PHI-sterile
- [x] Failure was self-diagnosed using provided documentation
- [x] No author intervention required

---

## What This Simulation Proves

1. **Operability**: A non-developer operator can run VoxelMask successfully
2. **Self-service troubleshooting**: Documentation is sufficient for common failures
3. **Evidence completeness**: All artefacts needed for audit are produced automatically
4. **PHI discipline**: No PHI in evidence bundle
5. **Scope discipline**: Operator understands copy-out, non-clinical constraints

---

## Limitations Acknowledged

This simulation does not prove:

- Behaviour under edge cases (corrupt files, network failures)
- Multi-operator concurrent use
- Integration with hospital ticketing systems
- Long-term artefact retention

These are out of scope for Phase 10.

---

## Version

This simulation reflects `v0.9.0-phase9-operator-pack`.

---

## Related Documents

A formal governance-oriented rendering of this simulation is available in [`PHASE10_HANDOFF_SIMULATION_FORMAL.md`](./PHASE10_HANDOFF_SIMULATION_FORMAL.md).
