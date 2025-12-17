# PILOT_HANDOFF.md

## VoxelMask — Internal Pilot Handoff

### Purpose

This document accompanies the VoxelMask internal pilot package.

VoxelMask is provided for **evaluation and governance review only**.

---

### Summary

VoxelMask is a PACS-adjacent, copy-out tool intended to assist teams in evaluating:

* Deterministic metadata anonymisation
* Burned-in text detection and masking
* Auditability of de-identification workflows

The tool operates entirely outside clinical systems and does not modify source data.

---

### Key constraints

* No write-back to PACS
* No clinical decision support
* No reversibility of masked output
* Manual operator acceptance required

---

### What success looks like

This pilot is successful if reviewers can:

* Understand operator intent and decision points
* Trace masking and anonymisation actions via audit artefacts
* Confirm governance alignment without ambiguity

---

### Next steps

* Collect operator feedback
* Review governance artefacts
* Decide whether to proceed to broader internal evaluation

No functional changes are expected during the pilot phase.
