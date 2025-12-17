# Phase 7 — Bulk Apply & Document Review

**Status:** Design Complete  
**Type:** Review Tooling Expansion  
**Prerequisite:** Phase 6 Complete  
**Dependency:** Phase 5C Frozen (Processing Unchanged)

---

## Governance Boundary

This phase **expands review decision tooling** without modifying processing logic.

**What IS Changed:**

| Component | Change | Audit Impact |
|-----------|--------|--------------|
| `ReviewRegion` | Add provenance fields | ✅ More data logged |
| `ReviewSession` | Add bulk apply methods | ✅ Explicit expansion |
| Bulk Apply UI | New modal with preview | ✅ User confirmation required |
| Document Review Panel | Separate from image review | ✅ Clear modality boundary |

**What Is NOT Changed:**

| Component | Status |
|-----------|--------|
| `anonymise_metadata()` | ❌ Frozen |
| `apply_pixel_mask()` | ❌ Frozen |
| `export_dicom()` | ❌ Frozen |
| Audit evidence schema | ❌ Frozen |
| Gate 1 ordering logic | ❌ Frozen |
| DICOM structure on disk | ❌ Frozen |

---

## Non-Goals (Explicit Exclusions)

The following are **explicitly NOT in scope** for Phase 7:

- No AI inference or "smart" detection
- No automatic mask inheritance (masks are COPIED, not inherited)
- No cross-modality bulk operations (image → document or vice versa)
- No geometry matching or resolution normalization
- No implicit global masking behaviour
- No write-back to PACS

---

## Scope of Work

### Part A: Safe Bulk Mask Application

**Goal:** Allow users to efficiently apply mask decisions to multiple images while maintaining per-instance audit trail.

**Core Principle:**

> **Expansion, not inheritance.**
> 
> Bulk apply CREATES N individual masking decisions, not 1 shared mask.

**Mental Model:**

```
┌────────────────────────────────────────────────────────────────┐
│                     BULK APPLY FLOW                            │
├────────────────────────────────────────────────────────────────┤
│                                                                │
│  1. User draws mask on Image A (Instance #12)                  │
│                                                                │
│  2. User clicks "Apply mask to..."                             │
│     ├─ ○ This series only (43 images)                          │
│     └─ ○ All US images in study (55 images)                    │
│                                                                │
│  3. System shows PREVIEW:                                      │
│     ┌──────────────────────────────────────────────────────────┐
│     │ The following 42 instances will receive                  │
│     │ the mask from Instance #12:                              │
│     │                                                          │
│     │ ⚠️ This will apply identical pixel regions across       │
│     │    images. Review results carefully.                     │
│     │                                                          │
│     │ ☑ S001/IMG_0001 (Instance #1)                            │
│     │ ☑ S001/IMG_0002 (Instance #2)                            │
│     │ ☐ S001/IMG_0012 (Instance #12) ← SOURCE (excluded)       │
│     │ ☑ S001/IMG_0013 (Instance #13)                           │
│     │ ...                                                      │
│     │                                                          │
│     │ [ ] Select All   [ ] Deselect All                        │
│     │                                                          │
│     │ [Cancel]  [Apply to 41 Selected]                         │
│     └──────────────────────────────────────────────────────────┘
│                                                                │
│  4. On Apply:                                                  │
│     For EACH selected instance:                                │
│       - Create individual ReviewRegion                         │
│       - Set region.bulk_apply_source = "SOP_UID_OF_SOURCE"     │
│       - Record in DecisionTrace with provenance                │
│                                                                │
└────────────────────────────────────────────────────────────────┘
```

**Data Structures:**

```python
@dataclass
class ReviewRegion:
    # ... existing fields ...
    
    # Phase 7: Bulk apply provenance
    bulk_apply_source: Optional[str] = None  # SOPInstanceUID of source image
    bulk_apply_id: Optional[str] = None       # UUID grouping bulk operation


@dataclass
class BulkApplyOperation:
    """Represents a pending bulk mask application."""
    
    operation_id: str              # UUID for this bulk operation
    source_instance_uid: str       # Where the mask was drawn
    source_regions: List[ReviewRegion]  # Regions being copied
    
    # Target scope
    scope: Literal["series", "modality"]
    target_series_uid: Optional[str] = None
    target_modality: Optional[str] = None
    
    # Expanded targets (after user confirmation)
    target_instance_uids: List[str] = field(default_factory=list)
    excluded_instance_uids: List[str] = field(default_factory=list)
```

**Audit Trail Entry (per instance):**

```json
{
    "decision_type": "pixel_mask",
    "action": "mask",
    "sop_instance_uid": "1.2.392.xxx.78",
    "region_id": "abc-123",
    "region_bounds": {"x": 10, "y": 20, "w": 100, "h": 50},
    "source": "bulk_apply",
    "bulk_apply_source": "1.2.392.xxx.76",
    "bulk_apply_id": "op-uuid-456",
    "timestamp": "2025-12-17T12:00:00Z"
}
```

---

### Part B: Modality Validation (Hard Boundary)

**Critical Constraint:**

```
┌────────────────────────────────────────────────────────────────┐
│                   ⚠️ HARD BOUNDARY ⚠️                          │
├────────────────────────────────────────────────────────────────┤
│                                                                │
│  US/CT/MR Images         │  OT/SC Documents                    │
│  ─────────────────       │  ─────────────────                  │
│  • Reviewed together     │  • Reviewed SEPARATELY              │
│  • Bulk apply allowed    │  • Bulk apply within docs ONLY      │
│  • User-defined regions  │  • Preset bands + manual            │
│                          │                                     │
│  ───────────────────────────────────────────────────────────   │
│                                                                │
│  NEVER:                                                        │
│  • Auto-inherit US mask to documents                           │
│  • Cross-modality bulk apply                                   │
│  • Assume document structure matches US                        │
│                                                                │
└────────────────────────────────────────────────────────────────┘
```

**Validation Logic:**

```python
IMAGE_MODALITIES = {"US", "CT", "MR", "DX", "CR", "MG", "XA", "RF", "NM", "PT"}
DOCUMENT_MODALITIES = {"OT", "SC", "SR", "DOC"}

def validate_bulk_apply_scope(source_modality: str, target_modalities: Set[str]) -> Tuple[bool, str]:
    """Validate that bulk apply stays within modality class."""
    
    source_is_image = source_modality in IMAGE_MODALITIES
    source_is_doc = source_modality in DOCUMENT_MODALITIES
    
    for target_mod in target_modalities:
        target_is_image = target_mod in IMAGE_MODALITIES
        target_is_doc = target_mod in DOCUMENT_MODALITIES
        
        if source_is_image and target_is_doc:
            return False, "Cannot apply image mask to documents"
        if source_is_doc and target_is_image:
            return False, "Cannot apply document mask to images"
    
    return True, "OK"
```

---

### Part C: Document Review Panel

**Goal:** Provide safe, explicit masking controls for OT/SC documents with clear separation from image review.

**UI Layout:**

```
┌─────────────────────────────────────────────────────────────────┐
│ 📄 Document Review                                              │
│ ─────────────────                                               │
│                                                                 │
│ 5 documents detected (OT/SC modality)                           │
│                                                                 │
│ ⚠️ Documents are reviewed separately from images.              │
│    Masks from images will NOT be applied to documents.          │
│                                                                 │
│ ┌─────────────────────────────────────────────────────────────┐ │
│ │ Quick Presets:                                              │ │
│ │                                                             │ │
│ │ [Apply Header Band (top 10%)] [Apply Footer Band (bot 10%)] │ │
│ │                                                             │ │
│ │ ☐ Apply preset to all documents in this study               │ │
│ └─────────────────────────────────────────────────────────────┘ │
│                                                                 │
│ Document 1 of 5: Vue RIS Scanned Documents                      │
│ ◀ [Slider] ▶                                                    │
│                                                                 │
│ [Document Image Display]                                        │
│                                                                 │
│ Regions: 0 detected, 0 manual                                   │
│ [+ Add Manual Region]                                           │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

**Preset Bands:**

```python
DOCUMENT_PRESETS = {
    "header_band": {
        "name": "Header Band (top 10%)",
        "description": "Mask top 10% — common location for patient headers",
        "region": lambda h, w: {"x": 0, "y": 0, "width": w, "height": int(h * 0.10)},
    },
    "footer_band": {
        "name": "Footer Band (bottom 10%)",
        "description": "Mask bottom 10% — common location for timestamps",
        "region": lambda h, w: {"x": 0, "y": int(h * 0.90), "width": w, "height": int(h * 0.10)},
    },
    "header_footer": {
        "name": "Header + Footer (top/bottom 10%)",
        "description": "Mask both header and footer bands",
        "regions": lambda h, w: [
            {"x": 0, "y": 0, "width": w, "height": int(h * 0.10)},
            {"x": 0, "y": int(h * 0.90), "width": w, "height": int(h * 0.10)},
        ],
    },
}
```

---

## Implementation Checklist

### Phase 7.1 — Bulk Apply Core

- [ ] Add `bulk_apply_source` and `bulk_apply_id` to `ReviewRegion`
- [ ] Create `BulkApplyOperation` dataclass
- [ ] Add `expand_targets()` method with modality validation
- [ ] Add `apply()` method that creates individual decisions
- [ ] Update `DecisionTrace` to record bulk apply provenance

### Phase 7.2 — Bulk Apply UI

- [ ] Create bulk apply modal component
- [ ] Add scope selector (series / modality)
- [ ] Add preview list with checkboxes
- [ ] Add warning text about identical pixel regions
- [ ] Add confirmation button with count
- [ ] Test with multi-series study

### Phase 7.3 — Document Review Panel

- [ ] Create separate document review section in UI
- [ ] Add modality boundary warning message
- [ ] Implement preset band buttons
- [ ] Add "Apply to all documents" checkbox with bulk expansion
- [ ] Add per-document manual region support
- [ ] Validate cross-modality bulk apply is blocked

### Phase 7.4 — Testing

- [ ] `test_bulk_apply_creates_individual_decisions`
- [ ] `test_bulk_apply_provenance_recorded`
- [ ] `test_cross_modality_bulk_apply_blocked`
- [ ] `test_document_preset_bands_correct_dimensions`
- [ ] `test_document_bulk_apply_within_documents_only`

---

## Files Changed

| File | Change |
|------|--------|
| `src/review_session.py` | Add bulk apply fields and methods |
| `src/decision_trace.py` | Add bulk apply provenance logging |
| `src/app.py` | Add bulk apply modal and document review panel |
| `src/document_presets.py` | NEW: Preset band definitions |
| `tests/test_bulk_apply.py` | NEW: Bulk apply tests |
| `tests/test_document_review.py` | NEW: Document review tests |

---

## Governance Summary

### Why Bulk Actions Remain Auditable

1. **Expansion, not inheritance**: Bulk apply *creates* N individual decisions, not 1 shared mask
2. **Provenance tracked**: Each region knows its `bulk_apply_source` and `bulk_apply_id`
3. **User confirmation**: Preview list allows deselection before commit
4. **Modality barrier**: Cross-class bulk apply is blocked at validation
5. **Soft warning**: Users warned about identical pixel regions

### Why Documents Are Separate

1. **Different structure**: Documents have headers/footers, not ultrasound overlays
2. **Different PHI locations**: Patient info in different positions
3. **Different review workflow**: Preset bands vs drawn regions
4. **Clear audit boundary**: Document decisions logged separately

---

## Sign-Off Criteria

Phase 7 is complete when:

1. ✅ Bulk apply creates individual per-instance decisions
2. ✅ Bulk apply provenance recorded in audit trail
3. ✅ Cross-modality bulk apply blocked
4. ✅ Document review panel separated from image review
5. ✅ Preset bands functional with bulk apply to all documents
6. ✅ All new tests passing
7. ✅ FREEZE_LOG updated

---

*This document defines Phase 7 scope. It builds on Phase 6 (Viewer UX) and Phase 5C (Frozen Processing).*
