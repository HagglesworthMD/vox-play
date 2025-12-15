# Sprint 2: Burned-In PHI Review Overlay — Design Specification

**Version:** 1.1  
**Date:** 2025-12-15  
**Status:** Design Phase (Amended)  
**Author:** VoxelMask Engineering  
**Sprint:** 2 of N  
**Dependency:** Sprint 1 (Decision Trace subsystem)

---

## Amendments Log

| Version | Change |
|---------|--------|
| 1.1 | Amendment 1: Clarify "Accept & Continue" gating language |
| 1.1 | Amendment 2: Rename `confidence` → `detection_strength` |
| 1.1 | Amendment 3: Use `frame_index = -1` for "all frames" |

---

## 1. Executive Summary

Sprint 2 adds **human-in-the-loop review** for burned-in PHI detection. A reviewer can inspect detected text regions, toggle mask/unmask, add manual regions, and proceed to export — with every action captured deterministically in the Decision Trace.

### What This System Is

- A **review gate** before export
- A **trust mechanism** (human verifies machine suggestions)
- An **audit trail generator** (reviewer actions → Decision Trace)

### What This System Is Not

- Not an accuracy measurement tool
- Not a training data collector
- Not an identity/permissions system
- Not a clinical workflow gating mechanism

---

## 2. UX Flow (Step-by-Step)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         BURNED-IN PHI REVIEW WORKFLOW                       │
└─────────────────────────────────────────────────────────────────────────────┘

Step 1: UPLOAD
    │
    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  User uploads DICOM file(s) or ZIP                                          │
│  System identifies US/SC/OT modalities eligible for pixel review            │
│  Non-eligible modalities (CT/MRI/etc.) skip to metadata-only processing     │
└─────────────────────────────────────────────────────────────────────────────┘
    │
    ▼
Step 2: DETECTION (Automatic)
    │
    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  For each eligible frame:                                                    │
│  • OCR engine detects static text regions                                   │
│  • Bounding boxes extracted (x, y, w, h)                                    │
│  • Default action set to MASK for all detected regions                      │
│  • Regions stored in session state (NOT in database yet)                    │
│                                                                             │
│  ⚠️ OCR text content is DISCARDED after bounding box extraction            │
└─────────────────────────────────────────────────────────────────────────────┘
    │
    ▼
Step 3: REVIEW OVERLAY (Human-in-the-loop)
    │
    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  UI displays:                                                               │
│  • Representative frame with overlay boxes                                  │
│  • Each box: colored border (red=MASK, green=UNMASK, blue=MANUAL)          │
│  • Click box → toggle state                                                 │
│  • Draw tool → add manual region                                           │
│  • Bulk controls: "Mask All" / "Unmask All" / "Reset to Detected"          │
│                                                                             │
│  Reviewer can:                                                              │
│  • Toggle individual regions                                                │
│  • Add new manual mask regions                                              │
│  • Delete manual regions (cannot delete OCR-suggested regions)              │
│  • Leave defaults unchanged                                                 │
└─────────────────────────────────────────────────────────────────────────────┘
    │
    ▼
Step 4: ACCEPT & CONTINUE (Gating)
    │
    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  Reviewer clicks "Accept & Continue to Export"                              │
│                                                                             │
│  Validation requirement:                                                    │
│  Reviewer explicitly acknowledges detected regions by clicking              │
│  "Accept & Continue", even if no per-region changes were made.              │
│                                                                             │
│  ⚠️ Export is BLOCKED until reviewer explicitly accepts                     │
└─────────────────────────────────────────────────────────────────────────────┘
    │
    ▼
Step 5: EXPORT (Processing)
    │
    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  For each region marked MASK:                                               │
│  • Apply black rectangle to pixel data                                      │
│  • Record decision in Decision Trace with appropriate ReasonCode           │
│                                                                             │
│  For each region marked UNMASK:                                             │
│  • Skip pixel modification                                                  │
│  • Record decision in Decision Trace (USER_OVERRIDE_RETAINED)              │
│                                                                             │
│  Metadata anonymisation proceeds as normal                                  │
└─────────────────────────────────────────────────────────────────────────────┘
    │
    ▼
Step 6: AUDIT & PDF
    │
    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  Decision Trace committed to SQLite                                         │
│  PDF report includes:                                                       │
│  • "Reviewer Actions" section                                               │
│  • Count of regions: masked / unmasked / manually added                     │
│  • Statement: "All reviewer actions captured in audit trail"               │
│                                                                             │
│  ⚠️ PDF contains NO OCR text, NO thumbnails, NO screenshots                │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 3. UI Interaction Design

### 3.1 Review Overlay Panel

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  📋 BURNED-IN PHI REVIEW                                     [?] Help       │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                                                                     │   │
│  │                    [DICOM IMAGE PREVIEW]                            │   │
│  │                                                                     │   │
│  │     ┌───────────────┐                                               │   │
│  │     │ Region 1 (OCR)│ ◀── Red border = will be masked              │   │
│  │     └───────────────┘                                               │   │
│  │                                                                     │   │
│  │              ┌─────────────┐                                        │   │
│  │              │ Region 2    │ ◀── Green border = will NOT be masked  │   │
│  │              └─────────────┘                                        │   │
│  │                                                                     │   │
│  │                       ┌──────────┐                                  │   │
│  │                       │ Region 3 │ ◀── Blue border = manually added │   │
│  │                       └──────────┘                                  │   │
│  │                                                                     │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
│  ── Bulk Controls ──────────────────────────────────────────────────────   │
│  [ Mask All Detected ]  [ Unmask All ]  [ Reset to Defaults ]              │
│                                                                             │
│  ── Drawing ────────────────────────────────────────────────────────────   │
│  [ ✏️ Add Manual Region ]  [ 🗑️ Clear Manual Regions ]                     │
│                                                                             │
├─────────────────────────────────────────────────────────────────────────────┤
│  REGION LIST                                                                │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │ #  Source   Coordinates        Action      Toggle                    │   │
│  │ 1  OCR      (50,100) 400×80    🔴 MASK     [ Unmask ]               │   │
│  │ 2  OCR      (50,200) 300×60    🟢 UNMASK   [ Mask ]                 │   │
│  │ 3  Manual   (200,300) 150×40   🔵 MASK     [ Unmask ] [ Delete ]    │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
│  ── Summary ────────────────────────────────────────────────────────────   │
│  Detected regions: 2  |  Manual regions: 1  |  Will be masked: 2           │
│                                                                             │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│            [ ✅ Accept & Continue to Export ]                               │
│                                                                             │
│  ⚠️ You must review all regions before proceeding.                         │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 3.2 Box Overlay Behavior

| Color | State | Meaning |
|-------|-------|---------|
| 🔴 Red (solid border) | `MASK` | Region WILL be masked (default for OCR) |
| 🟢 Green (dashed border) | `UNMASK` | Region will NOT be masked (reviewer override) |
| 🔵 Blue (solid border) | `MASK` (manual) | Manually added region, will be masked |

### 3.3 Interaction Rules

| Action | Effect |
|--------|--------|
| Click on box | Toggle MASK ↔ UNMASK |
| Draw rectangle | Add new manual region (default: MASK) |
| "Mask All Detected" | Set all OCR regions to MASK |
| "Unmask All" | Set all regions to UNMASK |
| "Reset to Defaults" | Restore OCR regions to MASK, remove manual regions |
| "Delete" (manual only) | Remove manually-added region |

### 3.4 Detection Strength Display (Optional, Safe Wording)

If detection strength is available from OCR, display as:

> **Detection strength:** Low / Medium / High

**Never use:**
- "Accuracy"
- "Certainty"
- "Confidence" (in UI labels)
- "Probability"
- Percentages

This avoids any implication of diagnostic reliability.

---

## 4. State Model

### 4.1 ReviewRegion Data Structure

```python
@dataclass
class ReviewRegion:
    """
    Represents a single reviewable region in the burned-in PHI workflow.
    
    Contains ONLY geometric and action state — never text content.
    """
    region_id: str                      # UUID, e.g., "r-001", "r-002"
    x: int                              # Bounding box X (pixels)
    y: int                              # Bounding box Y (pixels)
    w: int                              # Bounding box width (pixels)
    h: int                              # Bounding box height (pixels)
    source: str                         # "OCR" | "MANUAL"
    default_action: str                 # "MASK" | "UNMASK"
    reviewer_action: Optional[str]      # None (unchanged) | "MASK" | "UNMASK" | "DELETED"
    detection_strength: Optional[str]   # None | "LOW" | "MEDIUM" | "HIGH" (never numeric)
    frame_index: int                    # -1 = applies to all frames, >= 0 = specific frame


@dataclass
class ReviewSession:
    """
    Session state for the review workflow.
    
    Stored in Streamlit session_state, never persisted to database.
    """
    session_id: str             # UUID for this session
    sop_instance_uid: str       # The DICOM instance being reviewed
    regions: List[ReviewRegion]
    review_started: bool        # Has user entered review mode?
    review_accepted: bool       # Has user clicked "Accept & Continue"?
    created_at: str             # ISO 8601 timestamp
```

### 4.2 Frame Index Convention

| Value | Meaning |
|-------|---------|
| `frame_index = -1` | Region applies to **all frames** (static overlay) |
| `frame_index >= 0` | Region applies to **specific frame** (zero-indexed) |

This convention avoids confusion with zero-indexed frame arrays and is safe for future multi-frame US clip support.

### 4.3 Session State Lifecycle

```
Upload → Detection → regions populated with source="OCR", default_action="MASK"
                   → reviewer_action = None (untouched)
                   → frame_index = -1 (applies to all frames)

Review  → User toggles region → reviewer_action = "MASK" or "UNMASK"
        → User adds manual  → new region with source="MANUAL"
        → User deletes manual → reviewer_action = "DELETED"

Accept  → review_accepted = True
        → Session is now "sealed" for export

Export  → Regions processed, Decision Trace written
        → Session cleared
```

---

## 5. Decision Trace Mapping

### 5.1 ActionType + ReasonCode Matrix

| Scenario | ActionType | ReasonCode | target_name |
|----------|------------|------------|-------------|
| OCR region auto-detected, reviewer left as MASK | `MASKED` | `BURNED_IN_TEXT_DETECTED` | `PixelRegion[n]` |
| OCR region, reviewer changed to UNMASK | `RETAINED` | `USER_OVERRIDE_RETAINED` | `PixelRegion[n]` |
| OCR region, reviewer changed to MASK (after unmask) | `MASKED` | `USER_MASK_REGION_SELECTED` | `PixelRegion[n]` |
| Manual region added by reviewer, MASK | `MASKED` | `USER_MASK_REGION_SELECTED` | `PixelRegion[n]` |
| Manual region deleted by reviewer | (no trace) | — | — |
| Reviewer accepted defaults without changes | `MASKED` | `BURNED_IN_TEXT_DETECTED` | `PixelRegion[n]` |

### 5.2 Decision Recording Logic

```python
def record_region_decisions(
    collector: DecisionTraceCollector,
    regions: List[ReviewRegion],
    sop_instance_uid: str
):
    """
    Record all region decisions to the Decision Trace.
    
    Called at export time, after reviewer has accepted.
    """
    for idx, region in enumerate(regions):
        # Skip deleted manual regions — no trace needed
        if region.reviewer_action == "DELETED":
            continue
        
        # Determine final action
        final_action = region.reviewer_action or region.default_action
        
        if final_action == "MASK":
            # Determine reason code
            if region.source == "MANUAL":
                reason = ReasonCode.USER_MASK_REGION
            elif region.reviewer_action == "MASK":
                # Reviewer explicitly set to MASK (after toggle)
                reason = ReasonCode.USER_MASK_REGION
            else:
                # Default OCR detection, unchanged
                reason = ReasonCode.BURNED_IN_TEXT
            
            collector.add(
                scope_level=ScopeLevel.PIXEL_REGION,
                scope_uid=sop_instance_uid,
                action_type=ActionType.MASKED,
                target_type=TargetType.PIXEL_REGION,
                target_name=f"PixelRegion[{idx}]",
                reason_code=reason,
                rule_source=RuleSource.USER_MASK_INPUT if "USER" in reason else RuleSource.MODALITY_SAFETY_PROTOCOL,
                region_x=region.x,
                region_y=region.y,
                region_w=region.w,
                region_h=region.h
            )
        
        elif final_action == "UNMASK":
            # Reviewer chose to retain (not mask)
            collector.add(
                scope_level=ScopeLevel.PIXEL_REGION,
                scope_uid=sop_instance_uid,
                action_type=ActionType.RETAINED,
                target_type=TargetType.PIXEL_REGION,
                target_name=f"PixelRegion[{idx}]",
                reason_code=ReasonCode.USER_OVERRIDE_RETAIN,
                rule_source=RuleSource.USER_MASK_INPUT,
                region_x=region.x,
                region_y=region.y,
                region_w=region.w,
                region_h=region.h
            )
```

### 5.3 Audit Trail Guarantees

| Guarantee | Enforcement |
|-----------|-------------|
| Every masked region has a decision record | Loop over all MASK regions at export |
| Every unmasked region (override) has a record | Explicit RETAINED record for USER_OVERRIDE |
| No OCR text stored | ReviewRegion has no text field; existing PHI exclusion tests apply |
| Reviewer action is traceable | `reason_code` distinguishes OCR vs USER actions |

---

## 6. Non-Goals (Explicit)

| Item | Status | Rationale |
|------|--------|-----------|
| Role-based access control (RBAC) | ❌ Out of scope | Future sprint |
| User identity storage | ❌ Out of scope | Session-only |
| Reviewer metrics/dashboards | ❌ Out of scope | Future sprint |
| Automation rules ("always mask corner") | ❌ Out of scope | Breaks human-in-the-loop |
| Thumbnail storage in logs | ❌ Prohibited | PHI risk |
| OCR text storage in logs | ❌ Prohibited | PHI risk |
| Screenshot capture | ❌ Prohibited | PHI risk |
| Confidence percentages | ❌ Prohibited | Clinical implication risk |

---

## 7. Implementation Plan (PR-Sized Steps)

### PR 1: Review Session State Model
**Scope:** Data structures only, no UI

- Add `src/review_session.py` with `ReviewRegion` and `ReviewSession` dataclasses
- Add unit tests for state transitions
- No UI changes

**Files:** 
- `src/review_session.py` (new)
- `tests/test_review_session_unit.py` (new)

**LOC:** ~200

---

### PR 2: Decision Trace Integration for Reviewer Actions
**Scope:** Extend decision_trace.py for review scenarios

- Verify `USER_OVERRIDE_RETAIN` exists in ReasonCode
- Add `record_region_decisions()` function
- Add unit tests proving PHI exclusion for reviewer actions

**Files:**
- `src/decision_trace.py` (modify)
- `tests/test_decision_trace_unit.py` (extend)

**LOC:** ~150

---

### PR 3: Review Overlay UI Scaffold
**Scope:** Basic UI structure, no interactivity

- Add review panel to `src/app.py` (collapsible section)
- Display detected regions as list (read-only)
- Add placeholder for image overlay

**Files:**
- `src/app.py` (modify)

**LOC:** ~200

---

### PR 4: Interactive Box Overlay and Toggles
**Scope:** Full interactivity

- Implement canvas overlay for region boxes
- Click-to-toggle functionality
- Bulk controls (Mask All / Unmask All / Reset)
- "Accept & Continue" gating

**Files:**
- `src/app.py` (modify)
- `src/review_session.py` (modify for state updates)

**LOC:** ~400

---

### PR 5: End-to-End Integration and PDF Section
**Scope:** Wire everything together

- Connect review session to export pipeline
- Call `record_region_decisions()` at export
- Add "Reviewer Actions" section to PDF report

**Files:**
- `src/app.py` (modify)
- `src/pdf_reporter.py` (modify)
- Integration tests

**LOC:** ~300

---

## 8. Testing Plan

### 8.1 Unit Tests (Required)

| Component | Tests |
|-----------|-------|
| `ReviewRegion` dataclass | Field validation, defaults, frame_index convention |
| `ReviewSession` lifecycle | State transitions, validation |
| `record_region_decisions()` | Correct ActionType/ReasonCode mapping |
| PHI exclusion (extended) | Reviewer actions produce no PHI in trace |
| Bulk action logic | Mask All / Unmask All / Reset |

### 8.2 Integration Tests (Required)

| Scenario | Validation |
|----------|------------|
| Upload → Review → Export with defaults | Decision Trace contains BURNED_IN_TEXT |
| Upload → Review → Toggle → Export | Decision Trace contains USER_OVERRIDE_RETAIN |
| Manual region → Export | Decision Trace contains USER_MASK_REGION |
| Accept gating | Export blocked until Accept clicked |

### 8.3 Explicitly Excluded from Tests

| Component | Reason |
|-----------|--------|
| Streamlit rendering | UI framework responsibility |
| Canvas drawing internals | Third-party library |
| OCR accuracy | Out of scope (upstream) |
| Image display performance | Browser responsibility |

---

## 9. Performance Considerations

### 9.1 Avoiding Heavy Redraw Loops

| Risk | Mitigation |
|------|------------|
| Redrawing overlay on every state change | Use `st.session_state` caching; only redraw on explicit action |
| Large image loading | Thumbnail for review, full image for export only |
| Many regions (>50) | Paginate region list; overlay still shows all |

### 9.2 Memory Management

| Item | Approach |
|------|----------|
| Review session | Stored in `st.session_state`, cleared on export or cancel |
| Detected regions | In-memory only; never persisted until export |
| Image data | Single frame loaded for review; streamed for export |

---

## 10. Summary

Sprint 2 adds a **trust layer** between OCR detection and export. Every reviewer action is captured deterministically, enabling governance teams to:

1. **Verify** that human review occurred
2. **Understand** why each region was masked or retained
3. **Audit** without accessing PHI

The system remains:
- **Copy-out only** — no PACS modification
- **Non-clinical** — no diagnostic claims
- **PHI-free in logs** — enforced by structure and tests

---

## Appendix: Approval Checklist

Before implementation, confirm:

- [ ] State model reviewed (`detection_strength`, `frame_index = -1` convention)
- [ ] Accept gating language approved
- [ ] Decision Trace mapping approved for all reviewer scenarios
- [ ] PHI exclusion verified (no text fields in ReviewRegion)
- [ ] Implementation plan approved (5 PRs)
- [ ] Testing strategy approved

---

**Document Status:** Ready for Senior Engineering Review (Amended)  
**Next Steps:** Approval → PR 1 Implementation

---

*End of Sprint 2: Burned-In PHI Review Overlay — Design Specification v1.1*
