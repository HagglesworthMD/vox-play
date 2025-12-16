# Gate 1 — Step 3B: Viewer Parity Check

**Document Type:** Verification Evidence  
**Gate:** Gate 1 — Series Order Preservation  
**Step:** Step 3B — Viewer Parity Check  
**Status:** PASS (with documented caveats)

---

## Verification Context

| Field | Value |
|-------|-------|
| **Verification ID** | `3B-20251216-090200` |
| **Verification Timestamp** | 2025-12-16T09:02:00+00:00 |
| **Baseline Manifest** | `f28ba6f8-7a9a-497c-83b8-5f61b5a31107` |
| **Ordered Manifest** | (from ordered_series_manifest.json) |
| **Verifier** | Automated Gate 1 Execution |

---

## Viewer Environment

| Property | Value |
|----------|-------|
| **Primary Viewer** | VoxelMask DICOM_Viewer.html (embedded HTML5 viewer from export package) |
| **Secondary Viewer** | VoxelMask Streamlit App (src/app.py) preview panel |
| **Verification Date** | 2025-12-16 |
| **Verification Time** | 20:02 AEDT (09:02 UTC) |
| **Platform** | Linux (SteamOS/Arch-based) |
| **Test Data Source** | `FOI_5015705699.zip` extracted to gate1_evidence/source_data/ |
| **Operator** | Brian Shaw |

---

## Series Verification Results

### Series 1: US Primary (`1.2.392.200036.9116.6.18.17543328.9500.20240221225741415.4.8`)

| Check | Result | Notes |
|-------|--------|-------|
| **Modality** | US | Ultrasound Image Storage |
| **Instance Count** | 43 | All present |
| **InstanceNumber Range** | 1-45 (with gaps at 21-22) | Gap explained: source data has natural gap |
| **Scroll Forward** | ✓ PASS | Sequential from IN=1 to IN=45 |
| **Scroll Backward** | ✓ PASS | Reverse order maintained |
| **Cine Playback** | N/A | Single-frame instances, no multi-frame cine |
| **Ordering Method** | INSTANCE_NUMBER | No tie-breaks required |
| **Reorders Applied** | 0 | Source order == canonical order |

**Verdict: PASS**

---

### Series 2: US Secondary (`1.2.840.113619.2.169.579907165010730.11.254195.1708558522`)

| Check | Result | Notes |
|-------|--------|-------|
| **Modality** | US | Ultrasound (Secondary Capture / SC variant) |
| **Instance Count** | 7 | All present |
| **InstanceNumber Range** | 1-7 | Sequential, no gaps |
| **Scroll Forward** | ✓ PASS | Sequential from IN=1 to IN=7 |
| **Scroll Backward** | ✓ PASS | Reverse order maintained |
| **Cine Playback** | N/A | Single-frame instances |
| **AcquisitionTime** | Missing for all 7 | InstanceNumber ordering sufficient |
| **Ordering Method** | INSTANCE_NUMBER | No tie-breaks required |
| **Reorders Applied** | 0 | Source order == canonical order |

**Verdict: PASS**

---

### Series 3: OT Documents (`501570569999999`)

| Check | Result | Notes |
|-------|--------|-------|
| **Modality** | OT | Other (Scanned Documents) |
| **Instance Count** | 5 | All present |
| **InstanceNumber** | ALL = 1 | Non-sequential; vendor/PACS quirk |
| **AcquisitionTime** | Missing for all 5 | Not applicable for scanned docs |
| **Ordering Method** | SOP_UID_TIEBREAK | Lexical ordering by SOPInstanceUID |
| **Reorders Applied** | 4 | Position changes due to UID ordering |
| **Scroll Forward** | ✓ PASS | Stable, deterministic order |
| **Scroll Backward** | ✓ PASS | Reverse of deterministic order |

**Caveat:** Source order for OT series was **not clinically meaningful** — all instances had identical InstanceNumber=1 and no AcquisitionTime. The applied ordering (lexical SOPInstanceUID) provides:
- Determinism (same order every time)
- Repeatability (independent of filesystem)
- Stability (will not change unless SOPInstanceUIDs change)

**This is acceptable behaviour for document series per Gate 1 specification.**

**Verdict: PASS (with documented caveat)**

---

## Summary of Verification

| Series | Modality | Instances | Reordered | Method | Verdict |
|--------|----------|-----------|-----------|--------|---------|
| `1.2.392...` | US | 43 | 0 | INSTANCE_NUMBER | ✓ PASS |
| `1.2.840...` | US | 7 | 0 | INSTANCE_NUMBER | ✓ PASS |
| `50157...` | OT | 5 | 4 | SOP_UID_TIEBREAK | ✓ PASS* |

*With caveat: OT source order was arbitrary; deterministic ordering applied.

---

## Acceptance Criteria Check

| Criterion | Status | Evidence |
|-----------|--------|----------|
| Scroll/cine parity preserved | ✓ MET | All series scroll correctly |
| Differences explained by deterministic tie-breaks | ✓ MET | OT series: UID tie-break logged |
| Zero dropped instances | ✓ MET | 55 baseline = 55 ordered |
| Zero duplicated instances | ✓ MET | All SOPInstanceUIDs unique |

---

## Gate 1 Step 3B Declaration

**Viewer Parity Status: PASS**

All series verified for scroll parity. Ordering differences in OT document series are:
1. Explicitly logged in `ordering_decision_log.json`
2. Caused by deterministic tie-break logic (SOPInstanceUID lexical)
3. Expected behaviour for non-sequential document series
4. Not a clinical ordering concern (scanned documents have no inherent frame order)

---

**Document Hash (for bundling):** To be computed at bundle time.
