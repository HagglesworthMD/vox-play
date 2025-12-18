# Pilot README

**VoxelMask — Imaging De-Identification (Internal Pilot)**  
**Version:** `v0.8.0-phase8-operational`

---

## ⚠️ Critical Boundaries

| Constraint | What It Means |
| :--- | :--- |
| **Copy-out only** | VoxelMask exports to `downloads/`. It does NOT write back to PACS. |
| **Non-clinical pilot** | Outputs are for internal evaluation only. Not for clinical use. |
| **Irreversible masking** | Masked regions cannot be recovered. Original pixels are not retained. |
| **Not a guarantee** | VoxelMask does not guarantee complete PHI removal. Operator review is required. |

---

## Quick Start (Minimal Steps)

### 1. Launch VoxelMask

```bash
cd /path/to/VOXELMASK-4
source .venv/bin/activate
streamlit run src/app.py
```

### 2. Open in Browser

Navigate to the URL shown (typically `http://localhost:8501`).

### 3. Select Profile

Choose the appropriate de-identification profile:

- **Internal Repair** — Preserves patient identity, regenerates UIDs
- **Research (Safe Harbor)** — Removes direct identifiers
- **FOI** — Forensic/legal export

### 4. Upload Files

Drag and drop DICOM files or a ZIP archive.

### 5. Review Detected Regions

- VoxelMask detects potential burned-in PHI
- Toggle regions to **Keep** (not mask) or leave as **Mask**
- Click **Accept & Continue** to confirm

### 6. Download Output

- Click the download button to save the output ZIP
- Output is saved to `downloads/<study_name>.zip`

---

## Where Outputs Go

| Artefact | Location |
| :--- | :--- |
| Output ZIP | `downloads/<study_name>.zip` |
| Run directory | `downloads/voxelmask_runs/<run_id>/` |
| Run status | `.../run_status.json` |
| Evidence receipt | `.../receipts/run_receipt.json` |
| Audit log | `.../logs/VoxelMask_AuditLog_*.txt` |

---

## What to Do If Something Goes Wrong

1. **Note the run ID** (visible in console output)
2. **Check run_status.json** for status (`completed`, `failed`, `preflight_failed`)
3. **Check logs/** for error files
4. **See `RUNBOOK_TROUBLESHOOTING.md`** for common failures
5. **Escalate** with evidence if unresolved

---

## What NOT to Do

- ❌ Do NOT import outputs back into PACS without approval
- ❌ Do NOT assume all PHI is removed
- ❌ Do NOT use for patient care or diagnosis
- ❌ Do NOT delete run directories during evaluation

---

## Support

If you encounter issues not covered in the troubleshooting runbook, escalate with:

- Run ID
- Run status file
- Error screenshots/logs
- Steps to reproduce

---

## Version

This README is validated against `v0.8.0-phase8-operational`.
