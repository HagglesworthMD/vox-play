# src/session_state.py
from __future__ import annotations
from typing import Any, MutableMapping
import logging
import uuid

logger = logging.getLogger(__name__)

RUN_ID_KEY = "run_id"

# Only reset what is truly run-scoped.
# These keys are defined in Phase 12 as referencing stale paths, viewer indices, or run data.
RUN_SCOPED_KEYS = {
    # Run identity and paths
    'run_id',
    'run_paths',
    
    # Processing state
    'processing_complete',
    'processed_file_path',
    'processed_file_data',
    'processed_files',
    'output_zip_buffer',
    'combined_audit_logs',
    'processing_stats',
    'output_folder_name',
    'folder_structure_info',
    
    # Phase 12: Run-scoped viewer path (stable file:// link)
    'run_scoped_viewer_path',
    
    # File analysis / caches
    'uploaded_dicom_files',
    'file_info_cache',
    'manifest_selections',
    'manifest_data_cache',
    'manifest_file_hash',
    
    # Review session (contains temp_path references!)
    'phi_review_session',
    
    # Viewer navigation state
    'viewer_state',  # ViewerStudyState with temp_path references
    'viewer_needs_rebuild',  # Phase 13.4: Explicit rebuild flag reset
    'selected_series_uid',
    'selected_instance_idx',
    
    # Mask state (run-dependent for current images)
    'us_shared_mask',
    'per_file_masks',
    'batch_mask',
    'batch_canvas_version',
    'single_file_mask',
    'single_canvas_version',
    
    # Audit/hash state 
    'audit_text',
    'scrub_uuid',
    'input_file_hash',
    'output_file_hash',
}

def new_run_id() -> str:
    """Generate a new unique run identifier."""
    return uuid.uuid4().hex

def reset_run_state(ss: MutableMapping[str, Any], *, reason: str | None = None) -> str | None:
    """
    Clear all run-scoped session state for a clean run boundary.
    
    This function treats the session state as a plain dict-like object to 
    allow testing without a Streamlit runtime.
    
    Args:
        ss: The session state mapping (e.g. st.session_state or a dict)
        reason: Optional human-readable reason for the reset (for audit/tracing)
        
    Returns:
        The previous run_id that was cleared (if any)
    """
    previous_run_id = ss.get(RUN_ID_KEY)
    
    # Identify which keys exist before we clear them
    for k in list(ss.keys()):
        if k in RUN_SCOPED_KEYS:
            ss.pop(k, None)

    # Bump run id so anything created after is definitely new
    ss[RUN_ID_KEY] = new_run_id()
    
    # Set safe defaults if the UI expects them to exist
    ss.setdefault("selected_instance_idx", 0)
    ss.setdefault("selected_series_uid", None)
    ss.setdefault("phi_review_session", None)  # Ensure key exists even if cleared
    ss.setdefault("uploaded_dicom_files", [])  # Ensure list exists

    logger.info(
        "PHASE14: run_state_reset (%s); previous_run_id=%s new_run_id=%s",
        reason or "unspecified",
        previous_run_id or "none",
        ss.get(RUN_ID_KEY),
    )

    return previous_run_id
