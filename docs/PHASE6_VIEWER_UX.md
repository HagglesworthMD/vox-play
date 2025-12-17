# Phase 6 — Viewer UX Hardening

**Status:** Design Complete  
**Type:** Presentation-Only  
**Prerequisite:** Phase 5C Frozen  
**Tag:** `v0.5.1-phase6-viewer` (Series Browser complete)

---

## Governance Boundary

This phase is **presentation-layer only**. It does NOT affect:

- ❌ Anonymisation logic
- ❌ Masking algorithms
- ❌ Audit logging or evidence bundles
- ❌ Export ordering or DICOM structure
- ❌ Series/instance structure on disk

All changes must remain:

- ✅ Deterministic
- ✅ Explicit
- ✅ Auditable
- ✅ PACS-familiar
- ✅ Governance-safe

---

## Non-Goals (Explicit Exclusions)

The following are **explicitly NOT in scope** for Phase 6:

- No AI inference or "smart" detection
- No automatic PHI detection changes
- No document structure assumptions
- No write-back to PACS
- No masking controls in exported HTML viewer
- No cross-modality bulk operations (deferred to Phase 7)

---

## Scope of Work

### Part A: Exported HTML Viewer Enhancement

**Goal:** Make the exported HTML viewer PACS-usable without changing exported data.

**Constraints:**
- No DICOM restructuring
- No series merging on disk
- No change to exported files themselves
- `viewer_index.json` generated **only when HTML viewer export is selected**
- If `viewer_index.json` is missing, viewer.html should fail gracefully with clear message

**Deliverables:**

| Artefact | Description |
|----------|-------------|
| `viewer_index.json` | Presentation-only index file (optional) |
| `viewer.html` | Enhanced HTML viewer with series browser |
| `viewer.js` | Minimal navigation logic (no frameworks) |

**`viewer_index.json` Schema:**

```json
{
  "schema_version": "1.0.0",
  "generated_at": "ISO8601 timestamp",
  "study_uid": "1.2.840.xxx",
  "total_instances": 55,
  "series": [
    {
      "series_uid": "1.2.392.xxx",
      "series_number": 1,
      "series_description": "Obstetric 3rd Trimester",
      "modality": "US",
      "is_image_modality": true,
      "instance_count": 43,
      "instances": [
        {
          "file_path": "relative/path/to/file.dcm",
          "sop_instance_uid": "1.2.392.xxx",
          "instance_number": 1,
          "display_index": 1
        }
      ]
    }
  ],
  "ordering_source": "export_order_manifest",
  "note": "Presentation-only index. Export structure unchanged."
}
```

**HTML Viewer Features:**

| Feature | Behaviour |
|---------|-----------|
| Left Panel | Series browser with modality icons, descriptions, counts |
| Main Panel | Stack navigation with ◀/▶ buttons and slider |
| Position Indicator | "Image X of Y" prominent display |
| OT/SC Toggle | Hidden by default, toggleable via checkbox |
| Footer | "View-only. This viewer does not reflect DICOM series structure or modify exported data." |

---

### Part B: In-App Viewer UX Improvements

**Goal:** Make image selection and navigation obvious and fast for PACS users.

**Status:** ✅ Partially Complete (Series Browser in v0.5.1-phase6-viewer)

**Remaining Work:**

| Feature | Status | Notes |
|---------|--------|-------|
| Series grouping | ✅ Done | `viewer_state.py` |
| Stack navigation | ✅ Done | ◀/▶ + slider |
| Auto-select first series | ⬜ TODO | On load |
| Larger clickable series rows | ⬜ TODO | CSS enhancement |
| Keyboard shortcuts (← / →) | ⬜ TODO | With fallback note |
| Thumbnail strip | ⬜ Optional | Nice-to-have |

**Keyboard Navigation Note:**

Keyboard handling via JS injection is optional. Add fallback:

> "Keyboard navigation available when supported by browser/session. Buttons and slider remain primary controls."

---

## Implementation Checklist

### Phase 6.1 — Exported HTML Viewer

- [ ] Add `generate_viewer_index()` to export pipeline (conditional)
- [ ] Add check: only generate when HTML viewer export selected
- [ ] Create `viewer.html` template with series browser
- [ ] Create `viewer.js` with navigation logic (no frameworks)
- [ ] Add toggle for non-image objects (default: hidden)
- [ ] Add footer: "View-only. This viewer does not reflect DICOM series structure."
- [ ] Add graceful fallback when `viewer_index.json` missing
- [ ] Test with multi-series study

### Phase 6.2 — In-App Viewer UX Polish

- [ ] Auto-select first series with images on load
- [ ] Larger clickable series rows with hover states
- [ ] Add keyboard navigation with fallback note
- [ ] Clear "empty state" message when no files loaded

---

## Test Requirements

| Test Case | Description |
|-----------|-------------|
| `test_viewer_index_schema` | Validate JSON schema compliance |
| `test_viewer_index_ordering_matches_export` | Instance order must match export manifest |
| `test_html_viewer_graceful_fallback` | Viewer handles missing index gracefully |
| `test_auto_select_first_series` | First series selected on load |
| `test_keyboard_navigation_optional` | App works without keyboard support |

---

## Files Changed

| File | Change |
|------|--------|
| `src/viewer_state.py` | ✅ Already created |
| `src/app.py` | ✅ Series browser added, polish pending |
| `src/export/viewer_index.py` | NEW: Index generator |
| `static/viewer.html` | NEW: Enhanced HTML viewer |
| `static/viewer.js` | NEW: Navigation logic |
| `tests/test_viewer_index.py` | NEW: Index schema tests |

---

## Sign-Off Criteria

Phase 6 is complete when:

1. ✅ Exported HTML viewer has series browser (when enabled)
2. ✅ In-app viewer auto-selects first series
3. ✅ All presentation changes are logged in FREEZE_LOG
4. ✅ No processing, masking, or audit behaviour changed
5. ✅ All new tests passing

---

*This document defines Phase 6 scope. Bulk apply and document review are deferred to Phase 7.*
