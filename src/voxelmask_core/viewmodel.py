# src/voxelmask_core/viewmodel.py
"""
ViewModel computation for VoxelMask.

NO STREAMLIT IMPORTS ALLOWED IN THIS MODULE.

This module contains the pure-function logic for computing derived UI state
from committed state. The ViewModel is never stored; it's computed fresh
each render cycle.
"""
from __future__ import annotations

from typing import Any, Dict, Optional, Protocol

from .model import ViewModel


class ReviewSessionProtocol(Protocol):
    """Protocol for review session objects (duck typing)."""
    review_accepted: bool
    def is_sealed(self) -> bool: ...


def _get_memory_mb() -> float:
    """
    Get current RSS memory usage in MB (Linux only).
    
    Pure helper with no Streamlit dependency.
    """
    try:
        with open('/proc/self/status', 'r') as f:
            for line in f:
                if line.startswith('VmRSS:'):
                    return int(line.split()[1]) / 1024  # kB to MB
    except Exception:
        pass
    return 0.0


def compute_view_model(
    ss: Dict[str, Any],
    *,
    review_session: Optional[Any] = None,
) -> ViewModel:
    """
    Compute derived UI state from committed state.
    
    This function is PURE - it reads state but NEVER writes.
    Call this during render to get button states, warnings, etc.
    
    Args:
        ss: Session state dict (or dict-like object)
        review_session: Optional override for review session object
                       (if None, extracted from ss)
    
    Returns:
        ViewModel with all computed values for rendering
    """
    # Get review session
    if review_session is None:
        review_session = ss.get('phi_review_session')
    
    # Extract core state values
    mask_candidates_ready = ss.get('mask_candidates_ready', False)
    mask_review_accepted = ss.get('mask_review_accepted', False)
    processing_complete = ss.get('processing_complete', False)
    uploaded_files = ss.get('uploaded_dicom_files', [])
    output_zip_path = ss.get('output_zip_path')
    output_zip_buffer = ss.get('output_zip_buffer')
    
    # Compute review state
    has_review_session = review_session is not None
    review_accepted = False
    review_sealed = False
    if has_review_session:
        try:
            review_accepted = getattr(review_session, 'review_accepted', False)
            review_sealed = review_session.is_sealed() if hasattr(review_session, 'is_sealed') else False
        except Exception:
            pass
    
    # File state
    file_count = len(uploaded_files)
    has_files = file_count > 0
    
    # Output state
    has_output = (
        output_zip_path is not None or 
        (output_zip_buffer is not None and output_zip_buffer != b"")
    )
    
    # Processing gate computation
    can_process = (
        mask_candidates_ready and 
        mask_review_accepted and
        not processing_complete
    )
    
    # Workflow stage indicators
    detection_done = mask_candidates_ready
    review_done = mask_review_accepted
    export_ready = processing_complete and has_output
    
    # Process button logic
    show_process_button = has_files and not processing_complete
    
    if not mask_candidates_ready:
        process_button_disabled = True
        process_button_reason = "Run PHI detection first"
    elif not mask_review_accepted:
        process_button_disabled = True  
        process_button_reason = "Complete review and accept regions"
    elif processing_complete:
        process_button_disabled = True
        process_button_reason = "Processing already complete"
    else:
        process_button_disabled = False
        process_button_reason = ""
    
    return ViewModel(
        can_process=can_process,
        processing_complete=processing_complete,
        has_review_session=has_review_session,
        review_accepted=review_accepted,
        review_sealed=review_sealed,
        file_count=file_count,
        has_files=has_files,
        has_output=has_output,
        rss_mb=_get_memory_mb(),
        show_process_button=show_process_button,
        process_button_disabled=process_button_disabled,
        process_button_reason=process_button_reason,
        detection_done=detection_done,
        review_done=review_done,
        export_ready=export_ready,
    )


def compute_review_summary(review_session: Any) -> Dict[str, Any]:
    """
    Compute summary statistics for a review session.
    
    Args:
        review_session: ReviewSession object
        
    Returns:
        Dict with summary stats (total_regions, will_mask, will_keep, etc.)
    """
    if review_session is None:
        return {
            'total_regions': 0,
            'ocr_regions': 0,
            'manual_regions': 0,
            'will_mask': 0,
            'will_keep': 0,
        }
    
    try:
        return review_session.get_summary()
    except Exception:
        return {
            'total_regions': 0,
            'ocr_regions': 0,
            'manual_regions': 0,
            'will_mask': 0,
            'will_keep': 0,
        }
