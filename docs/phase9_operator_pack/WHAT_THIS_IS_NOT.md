# What VoxelMask Is NOT

**Purpose:** Prevent drift by being explicit about boundaries.  
**Version:** `v0.8.0-phase8-operational`

---

## VoxelMask Is NOT a Clinical System

- ❌ Not validated for clinical use
- ❌ Not intended for diagnostic imaging workflows
- ❌ Not a replacement for certified de-identification solutions
- ❌ Not approved for patient care decisions

**What it is:** A pilot/evaluation tool for internal de-identification research.

---

## VoxelMask Does NOT Guarantee Complete PHI Removal

- ❌ OCR detection is not 100% accurate
- ❌ Burned-in text in unusual locations may be missed
- ❌ Non-standard fonts, overlays, or embedded text may evade detection
- ❌ DICOM metadata cleaning follows configurable rules, not absolute guarantees

**What it does:** Provides operator-assisted de-identification with audit trails.

---

## VoxelMask Is NOT a PACS Router

- ❌ No DICOM send/receive networking
- ❌ No RIS/HIS/MPPS/worklist integration
- ❌ No automatic forwarding or routing
- ❌ No background processing or watch folders

**What it does:** Copy-out only. Exports to local filesystem.

---

## VoxelMask Does NOT Modify Source Data

- ❌ Original studies in PACS are never modified
- ❌ No write-back capability
- ❌ No in-place editing

**What it does:** Creates new, separate output files.

---

## VoxelMask Does NOT Retain Original Pixels

- ❌ Masked regions cannot be recovered
- ❌ No "undo" or "restore" functionality
- ❌ Original pixel data is not stored

**What it does:** Applies irreversible masking to output copies.

---

## VoxelMask Is NOT Self-Validating

- ❌ Does not self-certify compliance
- ❌ Does not validate against regulatory standards
- ❌ Does not replace human review

**What it does:** Provides tools and audit artefacts to support operator-led review.

---

## VoxelMask Is NOT for External Distribution

- ❌ Pilot outputs are for internal evaluation only
- ❌ Do not share outputs externally without explicit approval
- ❌ Do not use for multi-site research without governance review

**What it does:** Supports controlled internal pilot evaluation.

---

## Summary Table

| Claim | Status |
| :--- | :--- |
| Clinical-grade de-identification | ❌ NO |
| HIPAA Safe Harbor certified | ❌ NO |
| PACS integration | ❌ NO |
| Write-back to source | ❌ NO |
| Perfect PHI detection | ❌ NO |
| Recovery of masked content | ❌ NO |
| External distribution ready | ❌ NO |
| Operator review required | ✅ YES |
| Audit trail provided | ✅ YES |
| Copy-out only | ✅ YES |

---

## If Someone Asks You To...

| Request | Response |
| :--- | :--- |
| "Use this for clinical routing" | ❌ Decline — not validated for clinical use |
| "Send outputs to PACS" | ❌ Escalate — requires explicit approval |
| "Guarantee all PHI is removed" | ❌ Cannot guarantee — operator review required |
| "Undo the masking" | ❌ Not possible — masking is irreversible |
| "Share with external partner" | ❌ Escalate — requires governance approval |
