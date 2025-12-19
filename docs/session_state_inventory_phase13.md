# Session State Inventory — Phase 13 (UI Predictability)

Scope: `src/app.py` session state usage inventory, focusing on attribute access safety and governance-friendly behavior.

## Keys and Classification
- **Run identity**: `run_id`, `run_paths` — required early; initialized in `init_session_state_defaults()` and `_ensure_early_run_context()` before file work.
- **Processing lifecycle**: `processing_complete`, `processed_files`, `processed_file_path`, `processed_file_data`, `output_zip_buffer`, `processing_stats` — required when rendering post-run UI; now defaulted to safe placeholders to prevent AttributeError if flags are set inconsistently.
- **Audit material**: `audit_text`, `scrub_uuid`, `input_file_hash`, `output_file_hash`, `combined_audit_logs` — required for receipts and downloads; defaults avoid missing-key crashes while still surfacing empty/unknown states.
- **Review session**: `phi_review_session` — optional; always accessed via `.get()`/existence checks.
- **Preferences / scope**: `selection_scope`, `gateway_profile`, `processing_mode`, `uploaded_dicom_files` — required for predictable UI; initialized at start to deterministic defaults.
- **Viewer/selection caches**: `viewer_state`, `viewer_needs_rebuild`, `run_scoped_viewer_path`, `manifest_*`, `per_file_masks`, `us_shared_mask`, `batch_mask` — optional; creation guarded by local checks before attribute reads.
- **Operator identity**: `operator_id` — optional; accessed with `.get()` fallback.

## Risk Points
- Post-run success block reads `st.session_state.processed_files` and `output_zip_buffer` directly after checking only `processing_complete`/`output_zip_buffer` flags. If flags were toggled manually or by a partial failure, missing keys could raise `AttributeError` before the UI can present an audit-safe error.
- Audit download path writes `st.session_state.combined_audit_logs` without verifying presence; a missing key would crash after processing.

## Surgical Fixes (applied)
- Added defensive defaults for `processed_files`, `output_zip_buffer`, `processing_stats`, and `combined_audit_logs` inside `init_session_state_defaults()`. These preserve existing logic while ensuring any malformed/partial session renders predictable UI states instead of exceptions.

## Governance Rationale
- Deterministic defaults keep the UI from masking state errors with crashes, aiding auditability when operators report anomalous runs.
- Explicit initialization aligns with “pilot-safe, no surprises” behavior: unknown/empty states are surfaced via existing `.get()`-guarded messaging rather than implicit failures.
