# src/voxelmask_core/export.py
"""
Export and packaging logic for VoxelMask.

NO STREAMLIT IMPORTS ALLOWED IN THIS MODULE.

This module handles:
- ZIP bundle construction
- Output path generation
- Viewer index building helpers
"""
from __future__ import annotations

import hashlib
import os
import zipfile
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional


@dataclass
class ExportConfig:
    """Configuration for export generation."""
    include_html_viewer: bool = False
    include_audit_receipt: bool = True
    include_decision_trace: bool = True
    output_as_nifti: bool = False
    folder_name: Optional[str] = None


@dataclass
class ExportResult:
    """Result of export generation."""
    zip_path: Optional[str] = None
    zip_buffer: Optional[bytes] = None
    folder_name: str = ""
    file_count: int = 0
    total_bytes: int = 0
    success: bool = True
    error: Optional[str] = None


def generate_export_folder_name(
    gateway_profile: str,
    timestamp: Optional[datetime] = None,
) -> str:
    """
    Generate a descriptive folder name for the export.
    
    Args:
        gateway_profile: The processing profile (internal_repair, foi_legal, etc.)
        timestamp: Optional timestamp (defaults to now)
        
    Returns:
        Folder name like "VoxelMask_InternalRepair_20241221_185100"
    """
    if timestamp is None:
        timestamp = datetime.now()
    
    # Map profile to display name
    profile_names = {
        'internal_repair': 'InternalRepair',
        'us_research_safe_harbor': 'Research',
        'au_strict_oaic': 'OAIC',
        'foi_legal': 'FOI_Legal',
        'foi_patient': 'FOI_Patient',
    }
    
    profile_name = profile_names.get(gateway_profile, 'Export')
    date_str = timestamp.strftime('%Y%m%d_%H%M%S')
    
    return f"VoxelMask_{profile_name}_{date_str}"


def build_zip_bundle(
    processed_files: List[Dict[str, Any]],
    output_dir: Path,
    folder_name: str,
    *,
    audit_logs: Optional[List[str]] = None,
    viewer_files: Optional[Dict[str, bytes]] = None,
    additional_files: Optional[Dict[str, bytes]] = None,
) -> ExportResult:
    """
    Build a ZIP bundle from processed files.
    
    Args:
        processed_files: List of dicts with 'output_path', 'filename', etc.
        output_dir: Directory to write the ZIP file
        folder_name: Name for the folder inside the ZIP
        audit_logs: Optional list of audit log strings
        viewer_files: Optional dict of {path: content} for viewer files
        additional_files: Optional dict of {path: content} for extra files
        
    Returns:
        ExportResult with zip_path and metadata
    """
    try:
        # Create ZIP path
        zip_filename = f"{folder_name}.zip"
        zip_path = output_dir / zip_filename
        
        total_bytes = 0
        file_count = 0
        
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
            # Add processed DICOM files
            for pf in processed_files:
                output_path = pf.get('output_path')
                filename = pf.get('filename', os.path.basename(output_path))
                
                if output_path and os.path.exists(output_path):
                    arcname = f"{folder_name}/DICOM/{filename}"
                    zf.write(output_path, arcname)
                    total_bytes += os.path.getsize(output_path)
                    file_count += 1
            
            # Add audit logs
            if audit_logs:
                combined_log = '\n\n'.join(audit_logs)
                arcname = f"{folder_name}/audit_log.txt"
                zf.writestr(arcname, combined_log)
            
            # Add viewer files
            if viewer_files:
                for rel_path, content in viewer_files.items():
                    arcname = f"{folder_name}/{rel_path}"
                    if isinstance(content, str):
                        zf.writestr(arcname, content)
                    else:
                        zf.writestr(arcname, content)
            
            # Add additional files
            if additional_files:
                for rel_path, content in additional_files.items():
                    arcname = f"{folder_name}/{rel_path}"
                    if isinstance(content, str):
                        zf.writestr(arcname, content)
                    else:
                        zf.writestr(arcname, content)
        
        return ExportResult(
            zip_path=str(zip_path),
            folder_name=folder_name,
            file_count=file_count,
            total_bytes=total_bytes,
            success=True,
        )
        
    except Exception as e:
        return ExportResult(
            success=False,
            error=str(e),
        )


def compute_file_hash(filepath: str, algorithm: str = 'sha256') -> str:
    """
    Compute hash of a file for integrity verification.
    
    Args:
        filepath: Path to the file
        algorithm: Hash algorithm ('sha256', 'md5')
        
    Returns:
        Hex digest of the file hash
    """
    h = hashlib.new(algorithm)
    with open(filepath, 'rb') as f:
        while chunk := f.read(8192):
            h.update(chunk)
    return h.hexdigest()


def build_viewer_ordered_entries(
    processed_files: List[Dict[str, Any]],
    file_info_cache: Dict[str, Any],
    root_folder: str,
) -> List[Dict[str, Any]]:
    """
    Build ordered_entries for viewer_index.json from processed files.
    
    GOVERNANCE:
    - Read-only assembly from existing state
    - No mutation of processed_files
    - No reordering (preserves export order exactly)
    
    Args:
        processed_files: List of processed file dicts
        file_info_cache: Cache of file info from classification
        root_folder: Export root folder name
        
    Returns:
        List of entry dicts suitable for generate_viewer_index()
    """
    ordered_entries = []
    
    for idx, pf in enumerate(processed_files):
        filename = pf.get('filename', '')
        output_path = pf.get('output_path', '')
        
        # Get cached info
        info = file_info_cache.get(filename, {})
        
        # Build relative path for viewer
        rel_path = f"DICOM/{filename}"
        
        entry = {
            'file_path': rel_path,
            'filename': filename,
            'modality': info.get('Modality', 'Unknown'),
            'series_description': info.get('SeriesDescription', ''),
            'series_uid': info.get('SeriesInstanceUID', ''),
            'sop_uid': info.get('SOPInstanceUID', ''),
            'instance_number': info.get('InstanceNumber', idx + 1),
        }
        ordered_entries.append(entry)
    
    return ordered_entries


def sanitize_filename(filename: str) -> str:
    """
    Sanitize a filename to be filesystem-safe.
    
    Removes or replaces characters that could cause issues.
    """
    # Replace potentially problematic characters
    safe_chars = set('abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._-')
    return ''.join(c if c in safe_chars else '_' for c in filename)


def generate_repair_filename(
    original_filename: str,
    new_patient_id: str,
    series_description: str,
) -> str:
    """
    Generate descriptive filename for internal repair with series description.
    
    Args:
        original_filename: Original DICOM filename
        new_patient_id: New patient ID (sanitized)
        series_description: Series description from DICOM metadata
        
    Returns:
        Descriptive filename in format: [PatientID]_[SeriesDescription]_[OriginalName]_CORRECTED.dcm
    """
    # Sanitize components
    safe_patient_id = sanitize_filename(new_patient_id) if new_patient_id else 'UNKNOWN'
    safe_series = sanitize_filename(series_description) if series_description else ''
    
    # Get base name without extension
    base_name = os.path.splitext(original_filename)[0]
    safe_base = sanitize_filename(base_name)
    
    # Build filename
    parts = [safe_patient_id]
    if safe_series:
        parts.append(safe_series[:30])  # Limit series description length
    parts.append(safe_base[:20])  # Limit original name length
    parts.append('CORRECTED')
    
    return '_'.join(parts) + '.dcm'
