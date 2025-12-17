# DEPLOYMENT_NOTES.md

## Deployment Notes — Internal Pilot

### Environment

* Python 3.11+
* Linux or macOS (pilot tested)
* Local filesystem access for temp storage
* No outbound network access required

---

### Network

* Optional DICOM SCP (copy-out only)
* No inbound modification paths
* Firewall-friendly

---

### Storage

* Temporary processing directories
* Output ZIP bundles
* SQLite audit database (local)

No persistent PHI storage beyond operator-chosen output paths.

---

### OCR & imaging

* OCR used solely for text detection
* OCR confidence is advisory, not definitive
* Pixel masking is irreversible in output artefacts

---

### Failure handling

* Individual file failures do not halt sessions
* Partial output is clearly flagged
* Audit logs record processing outcomes

---

### Removal

VoxelMask can be removed by deleting:

* Application directory
* Local temp directories
* Optional audit DB files

No PACS configuration changes required.
