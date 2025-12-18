# Operator Checklist

**For:** VoxelMask Internal Pilot  
**Version:** `v0.8.0-phase8-operational`  
**Print this page and follow step-by-step.**

---

## ⚠️ Key Reminders (Read First)

- **Copy-out only** — VoxelMask does NOT modify source studies in PACS
- **Non-clinical pilot** — Outputs are for internal evaluation only
- **Irreversible masking** — Masked regions cannot be recovered
- **Review is mandatory** — You must review detected regions before accepting

---

## Pre-Run Checklist

Before clicking "Process":

- [ ] **Confirm copy-out mode** — You understand outputs go to `downloads/`, not back to PACS
- [ ] **Select correct profile** — Choose `Internal Repair`, `Research`, or `FOI` as appropriate
- [ ] **Verify output path exists** — `downloads/` directory is writable
- [ ] **Confirm study type** — Synthetic/test data for pilot, or approved internal evaluation study
- [ ] **Check disk space** — At least 250MB free (preflight will warn if insufficient)
- [ ] **Upload files** — Select DICOM files or ZIP archive

---

## During Run

What to expect:

- [ ] **Preflight passes** — No red error about dirs/disk/dependencies
- [ ] **Region detection runs** — You see detected regions appear in the review panel
- [ ] **Review regions** — Toggle any regions you want to KEEP (not mask)
- [ ] **Accept review** — Click "Accept & Continue" to confirm your decisions
- [ ] **Processing completes** — You see "✅ Complete!" message
- [ ] **Download available** — ZIP download button appears

### Warning Signs (Stop and Escalate)

- 🚫 Preflight failure → See `RUNBOOK_TROUBLESHOOTING.md`
- 🚫 "No files were processed" → Check file format and SOP class
- 🚫 Unexpected error message → Note the message, check logs

---

## Post-Run Checklist

After successful processing:

- [ ] **Download output ZIP** — Save to your designated folder
- [ ] **Locate run directory** — `downloads/voxelmask_runs/<run_id>/`
- [ ] **Verify run status** — Check `run_status.json` shows `"status": "completed"`
- [ ] **Collect evidence** — If required, attach:
  - `run_receipt.json`
  - `VoxelMask_AuditLog_*.txt`
  - Output ZIP
- [ ] **Record run ID** — Note the `run_id` for traceability

### What NOT to Do

- ❌ Do NOT import outputs back into PACS without explicit approval
- ❌ Do NOT assume all PHI is removed — review is required
- ❌ Do NOT delete the run directory until evaluation is complete
- ❌ Do NOT use for clinical diagnosis or patient care

---

## Evidence Attachment Guide

When submitting for review, include:

| Artefact | Why |
| :--- | :--- |
| `run_receipt.json` | Proves configuration and profile used |
| `run_status.json` | Proves success/failure outcome |
| `VoxelMask_AuditLog_*.txt` | Shows processing steps and decisions |
| Output ZIP | The actual de-identified output |

---

## Sign-Off (Optional)

| Field | Value |
| :--- | :--- |
| Operator | _________________________ |
| Date | _________________________ |
| Run ID | _________________________ |
| Outcome | ☐ Completed ☐ Failed |
| Notes | _________________________ |
