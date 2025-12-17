# README_PILOT.md

## VoxelMask — Internal Pilot README

### What this is

VoxelMask is a **non-clinical, copy-out de-identification support tool** designed to assist with:

* Deterministic DICOM metadata anonymisation
* Detection and masking of burned-in text in medical images
* Generation of audit-grade artefacts for review and governance

VoxelMask operates **outside clinical workflows** and **does not modify source PACS data**.

---

### What this is NOT

VoxelMask does **not**:

* Make diagnostic or clinical decisions
* Correct or "fix" clinical images
* Write data back to PACS
* Guarantee complete removal of all PHI
* Provide reversible masking or recovery of masked content

---

### Pilot safety boundaries

* **Copy-out only**: input data is read from user-selected files or exports
* **No PACS write-back**
* **No RIS / MPPS / worklist integration**
* **Manual operator review required**
* **Explicit acceptance step before export**

---

### Intended use (pilot)

* Internal research preparation
* FOI / legal discovery support
* Governance evaluation of de-identification workflows
* Engineering and PACS team evaluation

Not approved for clinical decision-making.

---

### Operator responsibilities

Operators must:

* Review detected regions before export
* Confirm acceptance of masking decisions
* Validate output prior to downstream use
* Retain audit artefacts as required by local policy

---

### Outputs

VoxelMask produces:

* Masked DICOM (or fallback formats)
* Structured audit logs (SQLite, CSV, PDF)
* Evidence bundles suitable for internal governance review

---

### Status

**Pilot / Evaluation use only**
Not certified medical software.
