# Freeze Notes: Preflight Findings

**Status:** Freeze-safe — informational only  
**Added:** Sprint 2.5  
**Author:** VoxelMask Engineering

---

## Overview

The **Preflight Findings** feature passively detects DICOM objects that may require special attention during review. It is **advisory only** and does **not** affect anonymisation, masking, or export behaviour.

## What It Detects

| Finding Type | SOP Class UID | Description |
|--------------|---------------|-------------|
| **Secondary Capture** | `1.2.840.10008.5.1.4.1.1.7` | Images created by screen capture or document scanning. May contain unmasked PHI from scanned forms, screenshots, or reports. |
| **Encapsulated PDF** | `1.2.840.10008.5.1.4.1.1.104.1` | PDF documents wrapped in DICOM format. This is a **non-image object** and is commonly overlooked during export. May contain full-text PHI. |

## Behaviour Guarantees

✅ **Advisory only** — displays a warning panel for user awareness  
✅ **No gating** — does not block accept or export  
✅ **No auto-exclusion** — does not modify dataset lists  
✅ **No masking changes** — pixel processing is unaffected  
✅ **No anonymisation changes** — metadata handling is unaffected  
✅ **Deterministic** — same input always produces same findings  

## Technical Details

- Detection occurs once per `ReviewSession`, during session creation
- Findings are stored in `ReviewSession.review_findings`
- UI indicator appears inside the "Burned-In PHI Review" expander
- Panel is read-only: no buttons, no toggles, no actions

## Why Encapsulated PDF Matters

Encapsulated PDF is a non-image DICOM object type. Unlike images:
- It cannot be visually inspected in standard DICOM viewers
- It is not subject to pixel-level masking
- It may contain complete patient records, reports, or scanned documents
- It is **commonly overlooked** during de-identification workflows

The preflight warning ensures operators are aware of these objects before export.

---

*This feature is freeze-safe and may be merged during code freeze periods.*
