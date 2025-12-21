# src/voxelmask_core/model.py
"""
State models for VoxelMask core logic.

NO STREAMLIT IMPORTS ALLOWED IN THIS MODULE.

State Categories:
-----------------
1. DraftState: Widget-driven values (safe to mutate during render)
   - Manual mask coordinates (us_mx_manual, us_my_manual, etc.)
   - Selection state (selected_series_uid, selected_instance_idx)
   - UI toggles and expander states
   
2. CoreState: Committed state representing the "truth" for a run
   - processing_complete, processed_files, output_zip_path
   - combined_audit_logs, processing_stats
   - mask_candidates_ready, mask_review_accepted
   - phi_review_session
   - Changing these triggers pipeline execution

3. ViewModel: Derived render-only values (never stored; computed each run)
   - Button enabled/disabled states
   - Warning messages
   - Computed display values
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from pathlib import Path


@dataclass
class ViewModel:
    """
    Render-only derived state computed from CoreState.
    
    NEVER store this in session_state; always recompute.
    All fields are read-only indicators for UI rendering.
    """
    # Processing gates
    can_process: bool = False
    processing_complete: bool = False
    
    # Review state
    has_review_session: bool = False
    review_accepted: bool = False
    review_sealed: bool = False
    
    # File state
    file_count: int = 0
    has_files: bool = False
    
    # Output state
    has_output: bool = False
    
    # System state
    rss_mb: float = 0.0
    
    # Additional computed state
    show_process_button: bool = False
    process_button_disabled: bool = True
    process_button_reason: str = ""
    
    # Workflow stage indicators
    detection_done: bool = False
    review_done: bool = False
    export_ready: bool = False


@dataclass 
class DraftState:
    """
    Widget-driven state that is safe to mutate during render.
    
    These values come from user input widgets and don't trigger
    processing side effects until explicitly committed.
    """
    # Manual mask coordinates (from number_input widgets)
    us_mx_manual: int = 0
    us_my_manual: int = 0
    us_mw_manual: int = 0
    us_mh_manual: int = 0
    
    # File/viewer selection
    selected_series_uid: Optional[str] = None
    selected_instance_idx: int = 0
    
    # Manual region input (for adding new regions)
    manual_x: int = 0
    manual_y: int = 0
    manual_w: int = 50
    manual_h: int = 50
    
    # UI toggles
    show_non_image_objects: bool = False
    
    @classmethod
    def from_session_state(cls, ss: Dict[str, Any]) -> 'DraftState':
        """Extract DraftState from session_state dict."""
        return cls(
            us_mx_manual=ss.get('us_mx_manual', 0),
            us_my_manual=ss.get('us_my_manual', 0),
            us_mw_manual=ss.get('us_mw_manual', 0),
            us_mh_manual=ss.get('us_mh_manual', 0),
            selected_series_uid=ss.get('selected_series_uid'),
            selected_instance_idx=ss.get('selected_instance_idx', 0),
            manual_x=ss.get('manual_x_val', 0),
            manual_y=ss.get('manual_y_val', 0),
            manual_w=ss.get('manual_w_val', 50),
            manual_h=ss.get('manual_h_val', 50),
            show_non_image_objects=ss.get('viewer_show_non_image', False),
        )


@dataclass
class CoreState:
    """
    Committed state representing the "truth" for a processing run.
    
    Changes to these values represent meaningful state transitions
    and may trigger side effects (pipeline execution, exports).
    
    Only modify via apply_action() in the action reducer pattern.
    """
    # Run identity
    run_id: Optional[str] = None
    run_paths: Optional[Any] = None  # RunPaths object
    
    # Processing state
    processing_complete: bool = False
    output_zip_path: Optional[str] = None
    output_zip_buffer: Optional[bytes] = None
    
    # File state
    uploaded_dicom_files: List[Any] = field(default_factory=list)
    file_info_cache: Dict[str, Any] = field(default_factory=dict)
    processed_files: List[Dict[str, Any]] = field(default_factory=list)
    
    # Audit state
    combined_audit_logs: List[str] = field(default_factory=list)
    processing_stats: Optional[Dict[str, Any]] = None
    
    # PACS workflow state
    mask_candidates_ready: bool = False
    mask_review_accepted: bool = False
    
    # Mask state
    us_shared_mask: Optional[tuple] = None  # (x, y, w, h)
    batch_mask: Optional[tuple] = None
    
    # Review session (opaque object reference)
    phi_review_session: Optional[Any] = None
    
    # Gateway/profile settings
    gateway_profile: str = "internal_repair"
    
    @classmethod
    def from_session_state(cls, ss: Dict[str, Any]) -> 'CoreState':
        """Extract CoreState from session_state dict."""
        return cls(
            run_id=ss.get('run_id'),
            run_paths=ss.get('run_paths'),
            processing_complete=ss.get('processing_complete', False),
            output_zip_path=ss.get('output_zip_path'),
            output_zip_buffer=ss.get('output_zip_buffer'),
            uploaded_dicom_files=ss.get('uploaded_dicom_files', []),
            file_info_cache=ss.get('file_info_cache', {}),
            processed_files=ss.get('processed_files', []),
            combined_audit_logs=ss.get('combined_audit_logs', []),
            processing_stats=ss.get('processing_stats'),
            mask_candidates_ready=ss.get('mask_candidates_ready', False),
            mask_review_accepted=ss.get('mask_review_accepted', False),
            us_shared_mask=ss.get('us_shared_mask'),
            batch_mask=ss.get('batch_mask'),
            phi_review_session=ss.get('phi_review_session'),
            gateway_profile=ss.get('gateway_profile', 'internal_repair'),
        )
    
    def to_session_state_updates(self) -> Dict[str, Any]:
        """Return dict of updates to apply to session_state."""
        return {
            'run_id': self.run_id,
            'run_paths': self.run_paths,
            'processing_complete': self.processing_complete,
            'output_zip_path': self.output_zip_path,
            'output_zip_buffer': self.output_zip_buffer,
            'uploaded_dicom_files': self.uploaded_dicom_files,
            'file_info_cache': self.file_info_cache,
            'processed_files': self.processed_files,
            'combined_audit_logs': self.combined_audit_logs,
            'processing_stats': self.processing_stats,
            'mask_candidates_ready': self.mask_candidates_ready,
            'mask_review_accepted': self.mask_review_accepted,
            'us_shared_mask': self.us_shared_mask,
            'batch_mask': self.batch_mask,
            'phi_review_session': self.phi_review_session,
            'gateway_profile': self.gateway_profile,
        }
