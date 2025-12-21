# src/voxelmask_core/pipeline.py
"""
Processing pipeline orchestration for VoxelMask.

NO STREAMLIT IMPORTS ALLOWED IN THIS MODULE.

This module coordinates the processing pipeline:
- Input preparation
- File-by-file processing orchestration
- Result aggregation
- Export preparation

Note: The actual DICOM processing (masking, anonymization) remains
in run_on_dicom.py. This module only orchestrates the flow.
"""
from __future__ import annotations

import os
import tempfile
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

from .audit import ProcessingAuditSummary, create_processing_stats
from .export import ExportConfig, ExportResult, generate_export_folder_name


@dataclass
class PipelineConfig:
    """Configuration for a processing pipeline run."""
    # Processing mode
    gateway_profile: str = "internal_repair"
    processing_mode: str = "Internal Repair"
    
    # Mask settings
    mask_coords: Optional[Tuple[int, int, int, int]] = None  # (x, y, w, h)
    
    # UIDs
    regenerate_uids: bool = False
    uid_only_mode: bool = False
    
    # Output settings
    include_html_viewer: bool = False
    output_as_nifti: bool = False
    
    # FOI settings (for foi_legal, foi_patient profiles)
    foi_case_ref: str = ""
    foi_requesting_party: str = ""
    foi_facility_name: str = ""
    foi_signatory: str = ""
    foi_recipient: str = ""
    
    # Internal repair settings
    new_patient_name: str = ""
    patient_sex: str = ""
    patient_dob: Optional[str] = None
    study_date: Optional[str] = None
    sonographer_name: str = ""
    referring_physician: str = ""
    reason_for_correction: str = ""
    correction_notes: str = ""
    operator_name: str = ""
    
    # Research settings
    compliance_profile: str = "safe_harbor"
    research_trial_id: str = ""
    research_site_id: str = ""
    research_subject_id: str = ""


@dataclass
class FileProcessingResult:
    """Result of processing a single file."""
    input_filename: str
    output_path: Optional[str] = None
    success: bool = False
    error: Optional[str] = None
    
    # Processing metadata
    modality: str = ""
    was_masked: bool = False
    was_anonymized: bool = False
    
    # Size info
    input_bytes: int = 0
    output_bytes: int = 0


@dataclass 
class PipelineResult:
    """
    Result of running the complete processing pipeline.
    
    Contains all information needed to update session state
    and generate exports.
    """
    success: bool = True
    error: Optional[str] = None
    
    # Processed files
    processed_files: List[FileProcessingResult] = field(default_factory=list)
    
    # Aggregate statistics
    total_input_bytes: int = 0
    total_output_bytes: int = 0
    processing_time_seconds: float = 0.0
    
    # Counts
    files_processed: int = 0
    files_failed: int = 0
    files_masked: int = 0
    
    # Audit data
    audit_logs: List[str] = field(default_factory=list)
    
    # Export paths
    output_folder_name: str = ""
    zip_path: Optional[str] = None
    
    def get_processing_stats(self) -> Dict[str, Any]:
        """Get stats dict for UI display."""
        return create_processing_stats(
            processing_time_seconds=self.processing_time_seconds,
            total_input_bytes=self.total_input_bytes,
            total_output_bytes=self.total_output_bytes,
            file_count=self.files_processed,
            masking_failures=self.files_failed,
        )


def prepare_pipeline_inputs(
    file_buffers: List[Any],
    run_dir: Path,
) -> List[Tuple[str, str]]:
    """
    Prepare input files for pipeline processing.
    
    Writes file buffers to temporary files and returns paths.
    
    Args:
        file_buffers: List of file buffer objects with .getbuffer()
        run_dir: Directory for temporary files
        
    Returns:
        List of (original_filename, temp_input_path) tuples
    """
    inputs = []
    
    for fb in file_buffers:
        # Create temp input file
        temp_input = tempfile.NamedTemporaryFile(
            delete=False, 
            suffix=".dcm",
            dir=str(run_dir) if run_dir else None
        )
        temp_input.write(fb.getbuffer())
        temp_input.close()
        
        inputs.append((fb.name, temp_input.name))
    
    return inputs


def run_pipeline(
    file_inputs: List[Tuple[str, str]],
    config: PipelineConfig,
    *,
    run_id: str,
    run_root: Path,
    file_processor: Callable[[str, str, Dict[str, Any]], bool],
    progress_callback: Optional[Callable[[int, int, str], None]] = None,
) -> PipelineResult:
    """
    Run the complete processing pipeline.
    
    This is the main pipeline orchestration function. It:
    1. Iterates through input files
    2. Calls file_processor for each file
    3. Aggregates results
    4. Returns PipelineResult
    
    IMPORTANT: The actual DICOM processing logic is NOT in this function.
    It's passed in via file_processor callback. This keeps the pipeline
    orchestration separate from the processing implementation.
    
    Args:
        file_inputs: List of (original_filename, input_path) tuples
        config: Pipeline configuration
        run_id: Unique run identifier
        run_root: Root directory for this run
        file_processor: Callback(input_path, output_path, context) -> success
        progress_callback: Optional callback(current, total, filename) for progress
        
    Returns:
        PipelineResult with all processing results
    """
    import time
    
    start_time = time.time()
    
    result = PipelineResult(
        output_folder_name=generate_export_folder_name(config.gateway_profile),
    )
    
    total_files = len(file_inputs)
    
    for idx, (original_filename, input_path) in enumerate(file_inputs):
        # Report progress
        if progress_callback:
            progress_callback(idx, total_files, original_filename)
        
        # Create output path
        output_tmp = tempfile.NamedTemporaryFile(
            delete=False,
            suffix="_processed.dcm",
            dir=str(run_root) if run_root else None
        )
        output_path = output_tmp.name
        output_tmp.close()
        
        # Build processing context
        context = {
            'config': config,
            'run_id': run_id,
            'original_filename': original_filename,
            'mask_coords': config.mask_coords,
        }
        
        # Process file
        file_result = FileProcessingResult(
            input_filename=original_filename,
            input_bytes=os.path.getsize(input_path) if os.path.exists(input_path) else 0,
        )
        
        try:
            success = file_processor(input_path, output_path, context)
            
            if success and os.path.exists(output_path):
                file_result.success = True
                file_result.output_path = output_path
                file_result.output_bytes = os.path.getsize(output_path)
                result.files_processed += 1
            else:
                file_result.success = False
                file_result.error = "Processing returned failure"
                result.files_failed += 1
                
        except Exception as e:
            file_result.success = False
            file_result.error = str(e)
            result.files_failed += 1
        
        result.processed_files.append(file_result)
        result.total_input_bytes += file_result.input_bytes
        result.total_output_bytes += file_result.output_bytes
    
    # Finalize
    result.processing_time_seconds = time.time() - start_time
    result.success = result.files_failed == 0
    
    return result


def cleanup_temp_files(file_inputs: List[Tuple[str, str]]) -> None:
    """
    Clean up temporary input files after processing.
    
    Args:
        file_inputs: List of (original_filename, temp_path) tuples
    """
    for _, temp_path in file_inputs:
        try:
            if os.path.exists(temp_path):
                os.unlink(temp_path)
        except Exception:
            pass  # Best effort cleanup
