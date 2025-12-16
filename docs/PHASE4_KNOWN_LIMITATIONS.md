# Phase 4 — Known Limitations

**(OCR Detection Hardening)**

## Purpose of This Section

This section documents the **inherent limitations** of OCR-based burned-in text detection in VoxelMask.

These limitations are:

* Acknowledged by design
* Not bugs or defects
* Foundational to why **human review remains mandatory**

This document exists to ensure operators, governance bodies, and acquirers understand detection boundaries **before relying on output**.

---

## Detection Is Probabilistic, Not Exhaustive

OCR-based detection **cannot guarantee** identification of all burned-in PHI.

| Limitation | Impact |
|------------|--------|
| Detection is probabilistic | Some PHI may not be detected |
| Confidence scores are estimates | High confidence ≠ certainty |
| No ground truth exists | Validation is heuristic |
| Novel text patterns may evade detection | OCR models have coverage gaps |

**Implication:**
VoxelMask detection informs review; it does not replace it.

---

## Modality-Specific Weaknesses

OCR performance varies significantly across imaging modalities.

### Ultrasound (US)

| Challenge | Description |
|-----------|-------------|
| Burned-in overlays | Patient/institution data embedded in PixelData |
| Low contrast regions | Text may blend with anatomical structures |
| Manufacturer variability | Overlay placement differs by vendor |
| Dynamic cine loops | Text may appear only in specific frames |

### Secondary Capture (SC)

| Challenge | Description |
|-----------|-------------|
| Scanned documents | Handwritten text, stamps, faxed headers |
| Variable image quality | Scan artifacts, noise, skew |
| Mixed content | Clinical notes adjacent to images |
| Non-standard layouts | No predictable text regions |

### Other Modalities

| Modality | Known Issues |
|----------|--------------|
| CR/DX | Technologist annotations, positioning markers |
| MG | Embedded patient demographics in mammography images |
| NM | Burned-in study metadata overlays |

---

## Font, Overlay, and Rendering Limitations

OCR engines have inherent sensitivity to visual presentation.

| Factor | Impact on Detection |
|--------|---------------------|
| **Font size** | Very small text (< 8pt equivalent) may be missed |
| **Font style** | Unusual, decorative, or proprietary fonts reduce accuracy |
| **Font color** | Low-contrast text on similar backgrounds evades detection |
| **Anti-aliasing** | Blurred edges from compression reduce character clarity |
| **Overlay transparency** | Semi-transparent overlays may not render clearly |
| **Rotation/skew** | Text at non-standard angles reduces OCR accuracy |

---

## Compression and Noise Sensitivity

Image quality directly affects OCR reliability.

| Condition | Effect |
|-----------|--------|
| **Lossy JPEG compression** | Character edges degrade, reducing recognition |
| **Low bit-depth** | Limited grayscale range flattens text contrast |
| **Acquisition noise** | Speckle and grain interfere with text extraction |
| **Rescaling artifacts** | Interpolation during resize blurs text |
| **Multi-frame averaging** | Text may be partially visible across frames |

---

## Third-Party OCR Engine Dependency

VoxelMask relies on external OCR engines (e.g., Tesseract, EasyOCR).

| Dependency Risk | Description |
|-----------------|-------------|
| **Engine accuracy** | Detection quality depends on engine performance |
| **Language models** | Non-English text may have reduced accuracy |
| **Version drift** | OCR engine updates may change detection behavior |
| **Configuration sensitivity** | Results vary with engine parameters |
| **Unsupported scripts** | Some character sets may not be recognized |

**Mitigation:**
OCR engine version is logged in audit output. Detection behavior changes require explicit operator acknowledgment.

---

## Human Review Remains Mandatory

Given the limitations above, **automated detection does not constitute de-identification**.

| Requirement | Rationale |
|-------------|-----------|
| Operator must review all detections | Algorithms miss edge cases |
| Operator must inspect low-confidence regions | Uncertainty must be surfaced |
| Operator must verify post-masking output | Detection informs; action remains intentional |
| Institutional SOP must define review thresholds | VoxelMask does not set policy |

---

## What VoxelMask Does *Not* Warrant

VoxelMask **makes no claim** that:

* All burned-in PHI will be detected
* Detection output is suitable for unsupervised de-identification
* Exported datasets are "safe," "clean," or "compliant"
* OCR confidence scores represent ground-truth accuracy
* Any specific regulatory standard is met by detection alone

---

## Summary Statement (Acquisition-Facing)

> VoxelMask's OCR detection is a **probabilistic assistance tool** that surfaces potential burned-in text for human review.
> It operates within documented constraints and explicitly avoids claims of completeness or automated compliance.
> Detection limitations are inherent to OCR technology and are disclosed to ensure informed operator judgment.

---

## Document Metadata

| Field               | Value                              |
|---------------------|------------------------------------|
| **Version**         | 1.0                                |
| **Created**         | 2025-12-16                         |
| **Classification**  | Governance / Diligence             |
| **Audience**        | Acquisition, Legal, PACS Admin     |
| **Related Docs**    | `PHASE4_NON_GOALS.md`, `PHASE3_PIXEL_INVARIANT.md` |
