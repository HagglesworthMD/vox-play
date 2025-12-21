# src/voxelmask_core/__init__.py
"""
VoxelMask Core - Non-UI logic extracted from Streamlit app.

This package contains pure Python logic with ZERO Streamlit dependencies.
All modules here accept/return plain Python objects and file paths.

Architecture:
- model.py: Dataclasses for state representation (DraftState, CoreState, ViewModel)  
- viewmodel.py: compute_view_model() - derive UI state from committed state
- actions.py: Action types and apply_action() reducer
- pipeline.py: Processing orchestration (run_pipeline)
- selection.py: File/study selection and filtering
- classify.py: Object classification helpers (image vs document vs unsupported)
- export.py: ZIP/bundle construction helpers
- audit.py: Audit event structures (no PHI)

HARD RULE: Import of `streamlit` is FORBIDDEN in this package.
"""

# Model types
from .model import DraftState, CoreState, ViewModel

# View model computation
from .viewmodel import compute_view_model, compute_review_summary

# Action system
from .actions import (
    Action,
    ActionType,
    ActionResult,
    SideEffect,
    SideEffectType,
    apply_action,
)

# Classification
from .classify import (
    classify_dicom_file,
    FileClassification,
    FileCategory,
    RiskLevel,
    bucket_classify_files,
    is_pixel_clean_modality,
    PIXEL_CLEAN_MODALITIES,
    PREVIEW_REQUIRED_MODALITIES,
)

# Selection
from .selection import (
    SelectionResult,
    SelectionScope,
    apply_selection_scope,
    compute_bucket_assignment,
    get_selection_summary,
)

# Pipeline
from .pipeline import (
    PipelineConfig,
    PipelineResult,
    FileProcessingResult,
    prepare_pipeline_inputs,
    run_pipeline,
    cleanup_temp_files,
)

# Export
from .export import (
    ExportConfig,
    ExportResult,
    generate_export_folder_name,
    build_zip_bundle,
    compute_file_hash,
    build_viewer_ordered_entries,
    sanitize_filename,
    generate_repair_filename,
)

# Audit
from .audit import (
    AuditEvent,
    AuditEventType,
    ProcessingAuditSummary,
    create_scope_audit_block,
    create_processing_stats,
)

__all__ = [
    # Model
    'DraftState',
    'CoreState', 
    'ViewModel',
    
    # ViewModel
    'compute_view_model',
    'compute_review_summary',
    
    # Actions
    'Action',
    'ActionType',
    'ActionResult',
    'SideEffect',
    'SideEffectType',
    'apply_action',
    
    # Classification
    'classify_dicom_file',
    'FileClassification',
    'FileCategory',
    'RiskLevel',
    'bucket_classify_files',
    'is_pixel_clean_modality',
    'PIXEL_CLEAN_MODALITIES',
    'PREVIEW_REQUIRED_MODALITIES',
    
    # Selection
    'SelectionResult',
    'SelectionScope',
    'apply_selection_scope',
    'compute_bucket_assignment',
    'get_selection_summary',
    
    # Pipeline
    'PipelineConfig',
    'PipelineResult',
    'FileProcessingResult',
    'prepare_pipeline_inputs',
    'run_pipeline',
    'cleanup_temp_files',
    
    # Export
    'ExportConfig',
    'ExportResult',
    'generate_export_folder_name',
    'build_zip_bundle',
    'compute_file_hash',
    'build_viewer_ordered_entries',
    'sanitize_filename',
    'generate_repair_filename',
    
    # Audit
    'AuditEvent',
    'AuditEventType',
    'ProcessingAuditSummary',
    'create_scope_audit_block',
    'create_processing_stats',
]
