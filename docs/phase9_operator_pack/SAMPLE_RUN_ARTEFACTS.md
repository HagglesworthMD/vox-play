# Sample Run Artefacts

**Purpose:** Show what "good" looks like for evidence and outputs.  
**Version:** `v0.8.0-phase8-operational`

---

## Run Directory Layout

After a successful run, you'll find:

```
downloads/
├── <study_name>.zip              # Output ZIP (download this)
└── voxelmask_runs/
    └── VM_RUN_a1b2c3d4e5f6/      # Run directory (unique per run)
        ├── run_status.json       # Run completion status
        ├── bundle/               # (Reserved for future use)
        ├── logs/
        │   └── VoxelMask_AuditLog_20251218_110530.txt
        ├── receipts/
        │   └── run_receipt.json  # PHI-sterile config capture
        └── tmp/                  # (Cleaned up on success)
```

---

## Example: run_status.json (Success)

```json
{
  "run_id": "VM_RUN_a1b2c3d4e5f6",
  "started_at": "2025-12-18T00:05:30+00:00",
  "status": "completed",
  "completed_at": "2025-12-18T00:06:15+00:00"
}
```

---

## Example: run_status.json (Failure)

```json
{
  "run_id": "VM_RUN_x9y8z7w6v5u4",
  "started_at": "2025-12-18T00:10:00+00:00",
  "status": "failed",
  "failed_at": "2025-12-18T00:10:05+00:00",
  "failure_reason": "no_files_processed"
}
```

---

## Example: run_status.json (Preflight Failed)

```json
{
  "run_id": "VM_RUN_preflight123",
  "started_at": "2025-12-18T00:15:00+00:00",
  "status": "preflight_failed"
}
```

---

## Example: run_receipt.json

```json
{
  "run_id": "VM_RUN_a1b2c3d4e5f6",
  "started_at": "2025-12-18T00:05:30+00:00",
  "receipt_written_at": "2025-12-18T00:05:31+00:00",
  "processing_mode": "internal_repair",
  "gateway_profile": "internal_repair",
  "selection_scope": {
    "include_images": true,
    "include_documents": false
  },
  "build_info": "build=3606a9b pid=12345 cwd=/home/user/VOXELMASK-4 ts=2025-12-18T00:05:30",
  "git_sha": "unknown",
  "preflight": {
    "ok": true
  },
  "phase": "phase8",
  "item": "4.4"
}
```

### Receipt Fields Explained

| Field | Meaning |
| :--- | :--- |
| `run_id` | Unique identifier for this run |
| `started_at` | When run context was created (UTC) |
| `receipt_written_at` | When this receipt was written (UTC) |
| `processing_mode` | Selected profile (internal_repair, research, foi) |
| `gateway_profile` | Same as processing_mode (legacy compat) |
| `selection_scope` | What object types were included |
| `build_info` | Git commit, PID, working directory, timestamp |
| `preflight.ok` | Whether preflight checks passed |

---

## Example: Audit Log Excerpt

```
═══════════════════════════════════════════════════════════════
VoxelMask Audit Log
═══════════════════════════════════════════════════════════════
Run ID: VM_RUN_a1b2c3d4e5f6
Profile: internal_repair
Selection Scope: images=True, documents=False

--- File 1: US_001.dcm ---
Input SHA256: a1b2c3d4...
Output SHA256: e5f6g7h8...
Regions Detected: 3
Regions Masked: 2
Regions Kept: 1
UID Regeneration: Applied

--- File 2: US_002.dcm ---
...
```

---

## What to Attach When Escalating

| Scenario | Attach |
| :--- | :--- |
| Successful run | `run_receipt.json`, `run_status.json` |
| Failed run | `run_status.json`, `VoxelMask_AuditLog_*.txt`, any `*_error.txt` |
| Preflight failure | `run_status.json`, `preflight_error.txt` |
| Partial output | All of the above + description of what's missing |

---

## PHI-Sterile Guarantee

All evidence artefacts in this section are **PHI-sterile**:

- ✅ No patient names
- ✅ No MRNs
- ✅ No accession numbers
- ✅ No study/series/instance UIDs
- ✅ No filenames containing patient info
- ✅ Hashes only for input/output integrity

---

## Version

These examples reflect `v0.8.0-phase8-operational`.
