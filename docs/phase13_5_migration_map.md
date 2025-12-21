# VoxelMask Core Extraction - Migration Map

## Phase 13.5: Decoupling Refactor

**Date:** 2025-12-21  
**Goal:** Move ALL non-UI logic out of Streamlit (src/app.py) into plain Python modules

---

## Package Structure

```
src/voxelmask_core/
├── __init__.py          # Package exports (NO streamlit)
├── model.py             # DraftState, CoreState, ViewModel dataclasses
├── viewmodel.py         # compute_view_model() - pure state computation
├── actions.py           # Action types + apply_action() reducer
├── pipeline.py          # Processing orchestration (uses callbacks)
├── selection.py         # File/study selection logic
├── classify.py          # DICOM classification (image/document/unsupported)
├── export.py            # ZIP bundle construction helpers
└── audit.py             # PHI-free audit event structures
```

---

## Functions Moved from app.py

| Original Location | New Location | Notes |
|-------------------|--------------|-------|
| `compute_view_model()` | `voxelmask_core/viewmodel.py` | Pure function, no streamlit |
| `_get_memory_mb()` | `voxelmask_core/viewmodel.py` | Linux-only memory check |
| `analyze_dicom_context()` | Similar logic in `voxelmask_core/classify.py` | New implementation |
| File bucketing logic | `voxelmask_core/selection.py` → `apply_selection_scope()` | Extracted |
| `PIXEL_CLEAN_MODALITIES` | `voxelmask_core/classify.py` | Canonical set |
| `PREVIEW_REQUIRED_MODALITIES` | `voxelmask_core/classify.py` | Canonical set |
| `generate_repair_filename()` | `voxelmask_core/export.py` | Moved |
| `_build_viewer_ordered_entries()` | `voxelmask_core/export.py` → `build_viewer_ordered_entries()` | Moved |
| Selection scope audit block | `voxelmask_core/audit.py` → `create_scope_audit_block()` | New implementation |
| Processing stats computation | `voxelmask_core/audit.py` → `create_processing_stats()` | Extracted |

---

## Session State Key Mapping

### DraftState (UI widget-driven, safe to mutate during render)

| Key | Type | Description |
|-----|------|-------------|
| `us_mx_manual` | int | Manual mask X coordinate input |
| `us_my_manual` | int | Manual mask Y coordinate input |
| `us_mw_manual` | int | Manual mask width input |
| `us_mh_manual` | int | Manual mask height input |
| `selected_series_uid` | str | Currently selected series UID |
| `selected_instance_idx` | int | Currently selected instance index |
| `manual_x_val` | int | Manual region X input |
| `manual_y_val` | int | Manual region Y input |
| `manual_w_val` | int | Manual region width input |
| `manual_h_val` | int | Manual region height input |
| `viewer_show_non_image` | bool | Show non-image objects toggle |

### CoreState (Committed run state, modify via apply_action only)

| Key | Type | Description |
|-----|------|-------------|
| `run_id` | str | Unique run identifier |
| `run_paths` | RunPaths | Paths for current run |
| `processing_complete` | bool | True when processing finished |
| `output_zip_path` | str | Path to output ZIP file |
| `output_zip_buffer` | bytes | ZIP data buffer |
| `uploaded_dicom_files` | list | Uploaded file buffers |
| `file_info_cache` | dict | Classification cache by filename |
| `processed_files` | list | List of processed file dicts |
| `combined_audit_logs` | list | Audit log strings |
| `processing_stats` | dict | Timing/size statistics |
| `mask_candidates_ready` | bool | PHI detection complete |
| `mask_review_accepted` | bool | Review accepted by user |
| `us_shared_mask` | tuple | Shared mask coords (x,y,w,h) |
| `batch_mask` | tuple | Batch mask coords |
| `phi_review_session` | ReviewSession | Region review state |
| `gateway_profile` | str | Processing profile |

### ViewModel (Computed every render, never stored)

| Field | Type | Source Computation |
|-------|------|-------------------|
| `can_process` | bool | mask_ready AND review_accepted AND NOT complete |
| `processing_complete` | bool | Direct from CoreState |
| `has_review_session` | bool | phi_review_session is not None |
| `review_accepted` | bool | session.review_accepted |
| `review_sealed` | bool | session.is_sealed() |
| `file_count` | int | len(uploaded_dicom_files) |
| `has_files` | bool | file_count > 0 |
| `has_output` | bool | zip_path or buffer exists |
| `rss_mb` | float | Current memory usage |

---

## What Remains in app.py and Why

| Component | Reason |
|-----------|--------|
| `st.set_page_config()` | Must be first Streamlit call |
| Layout & CSS | Pure presentation |
| Widget declarations | Streamlit widgets read/write `st.session_state` |
| `on_click` callbacks | Bridge between Streamlit events and core actions |
| `st.rerun()` calls | Trigger Streamlit lifecycle |
| Debug panel (`DEBUG_UI`) | Streamlit UI for debugging |
| Build stamp display | `st.caption()` for debug |
| Progress bars | `st.progress()` for processing feedback |
| Error/warning displays | `st.error()`, `st.warning()`, `st.info()` |
| File uploader | `st.file_uploader()` |
| Action consumption | Read pending_action, call `apply_action()`, update ss |

---

## Confirmations

### ✅ No streamlit import in core package

```bash
$ grep -rn "import streamlit" src/voxelmask_core/
# (no output)
```

### ✅ No changes to anonymisation/masking/OCR outputs

- `run_on_dicom.py`: Untouched
- `audit_manager.py`: Untouched
- `compliance_engine.py`: Untouched
- `foi_engine.py`: Untouched
- `review_session.py`: Untouched
- `pixel_invariant.py`: Untouched

### ✅ Rerun storms reduced

The action/reducer pattern in `voxelmask_core/actions.py` ensures:
- State changes are explicit via `apply_action()`
- CoreState updates are atomic
- Side effects are descriptions, not direct mutations
- No committed-state mutation during render phase

---

## Unit Tests

**File:** `tests/test_voxelmask_core.py`

- 53 tests covering:
  - ViewModel computation
  - DraftState/CoreState creation
  - Selection scope filtering
  - Classification buckets
  - Audit block generation
  - Action creation and apply_action reducer
  - **No-streamlit verification** for all core modules

**Why pipeline.py is not unit-tested:**
- Contains file I/O orchestration
- Uses callbacks for actual processing
- Integration-tested via existing run_on_dicom tests

---

## Next Steps (Future Phases)

1. **Replace inline `compute_view_model()` in app.py** with direct call to `_core_compute_view_model()`
2. **Wire action consumption** to use `apply_action()` and handle `SideEffect` returns
3. **Extract processing loop** from app.py form handler into `pipeline.run_pipeline()`
4. **Migrate file classification** to use `classify_dicom_file()` from core
5. **Move ZIP creation** to use `build_zip_bundle()` from core

---

## Processing Action Wiring (Completed)

### One-Shot Trigger Pattern

The "Process Selected Studies" button is now wired to the action consumer pattern:

```
Button click → enqueue pending_action="start_processing" + payload → st.rerun()
    ↓
Action consumer reads pending_action → clears it → sets _run_processing_once=True → st.rerun()
    ↓
Processing block checks _run_processing_once → clears it → executes processing once
    ↓
Processing complete → clears _processing_payload → sets processing_complete=True
```

### Why This Pattern?

- **No 1000-line block move**: Keeps the massive processing block in place
- **Action semantics enforced**: enqueue → rerun → consume → execute
- **One-shot guarantee**: Trigger cleared immediately, prevents re-entry
- **Payload validation**: Processing fails safely if payload missing
- **Stale replay prevention**: Payload cleared after successful completion

### Debug Panel Indicators

| Field | Meaning |
|-------|---------|
| `pending_action` | Currently enqueued action (should be `None` most of the time) |
| `action_consumed_this_run` | `True` if an action was consumed this render cycle |
| `explicit_rerun_called` | `True` if `st.rerun()` was called explicitly |
| `executed_action` | Last action that was executed (for fuse comparison) |

### Committed State Keys (Modified Only by Processing)

| Key | Set By | Cleared By |
|-----|--------|------------|
| `_run_processing_once` | Action consumer | Processing block (immediately) |
| `_processing_payload` | Form submit | Processing completion |
| `processing_complete` | Processing block | `reset_run_state()` |
| `processed_files` | Processing block | `reset_run_state()` |
