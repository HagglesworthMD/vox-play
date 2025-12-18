# Runbook — Troubleshooting

**For:** VoxelMask Internal Pilot  
**Version:** `v0.8.0-phase8-operational`

---

## How to Use This Runbook

1. Identify the failure symptom from the table below
2. Follow the diagnostic steps
3. Take the recommended action
4. If unresolved, escalate with evidence

---

## Failure: Preflight Failed

**Symptom:** Red error "🚫 Preflight checks failed" appears before processing starts.

### Where to Look

| File | Location |
| :--- | :--- |
| Preflight error log | `downloads/voxelmask_runs/<run_id>/logs/preflight_error.txt` |
| Run status | `downloads/voxelmask_runs/<run_id>/run_status.json` (status: `preflight_failed`) |

### Common Causes

| Error Message Contains | Likely Cause | Action |
| :--- | :--- | :--- |
| `Cannot create directory` | Permissions issue | Check `downloads/` is writable |
| `Directory not writable` | Filesystem permissions | Check folder permissions |
| `Insufficient free space` | Disk full | Free up disk space (need 250MB+) |
| `Missing dependency: pydicom` | Environment issue | Reinstall dependencies |
| `Processing mode is not set` | Profile not selected | Select a profile before processing |

### Safe Actions

- ✅ Check and fix the reported issue
- ✅ Retry the run
- ❌ Do NOT manually create run_status.json

---

## Failure: No Files Were Processed

**Symptom:** Processing completes but shows "No files were processed successfully".

### Where to Look

| File | Location |
| :--- | :--- |
| Run status | `downloads/voxelmask_runs/<run_id>/run_status.json` (status: `failed`, reason: `no_files_processed`) |
| Audit log | `downloads/voxelmask_runs/<run_id>/logs/VoxelMask_AuditLog_*.txt` |

### Common Causes

| Scenario | Likely Cause | Action |
| :--- | :--- | :--- |
| All files skipped | Unsupported SOP Class (e.g., PDF, SR) | Check modality/file types |
| Pixel decode failure | Compressed or corrupt DICOM | Check transfer syntax |
| Empty upload | No files selected | Re-upload files |
| All files excluded | Selection scope filtered everything | Check "Include Images" setting |

### Safe Actions

- ✅ Check file types and modalities
- ✅ Try with known-good test files
- ✅ Check selection scope settings
- ❌ Do NOT modify DICOM files directly

---

## Failure: Evidence Bundle Missing or Partial

**Symptom:** Expected files in run directory are missing.

### What to Check

| Expected File | If Missing |
| :--- | :--- |
| `run_status.json` | Run may have crashed before context creation |
| `run_receipt.json` | Receipt capture failed (non-fatal) — check `receipt_warning.txt` |
| `VoxelMask_AuditLog_*.txt` | Processing may not have reached completion |
| Output ZIP | Check if run completed successfully |

### Diagnostic Steps

1. Check `run_status.json` status field
2. Look for any `*_error.txt` or `*_warning.txt` files in `logs/`
3. Check console/terminal output for Python exceptions

### Safe Actions

- ✅ Note what's missing and what's present
- ✅ Include partial evidence when escalating
- ❌ Do NOT fabricate missing files

---

## Failure: Unexpected Exception

**Symptom:** Python error or stack trace appears.

### What to Capture

- Screenshot or copy of the error message
- Run ID (if available)
- Any files in `downloads/voxelmask_runs/<run_id>/logs/`
- Steps that led to the error

### Safe Actions

- ✅ Note the error and escalate
- ✅ Do NOT retry on the same data without guidance
- ❌ Do NOT attempt to "fix" DICOM files

---

## Escalation Template

When escalating an issue, include:

```
Run ID: <run_id>
Symptom: <what you observed>
Expected: <what should have happened>
Profile: <Internal Repair / Research / FOI>
Files attached:
- [ ] run_status.json
- [ ] run_receipt.json
- [ ] preflight_error.txt (if present)
- [ ] VoxelMask_AuditLog_*.txt
- [ ] Screenshot of error (if applicable)
```

---

## What NOT to Do

- ❌ Do NOT modify any files in the run directory
- ❌ Do NOT re-run the same study without understanding the failure
- ❌ Do NOT assume partial outputs are usable
- ❌ Do NOT import failed outputs into PACS
