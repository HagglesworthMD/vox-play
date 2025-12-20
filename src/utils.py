#!/usr/bin/env python3
"""
Shared utilities for DICOM anonymization.

This module provides unified functions for deterministic sanitization
that are applied across all processing paths (Clinical, Research, Single, Bulk).
"""

import hashlib
import uuid
from datetime import datetime, timedelta
import pydicom


# Namespace for deterministic UID generation
DEID_NAMESPACE = uuid.UUID('a1b2c3d4-e5f6-7890-abcd-ef1234567890')


def generate_deterministic_uid(original_uid: str) -> str:
    """Generate a deterministic new UID from original using uuid5."""
    new_uuid = uuid.uuid5(DEID_NAMESPACE, original_uid)
    uid_int = int(new_uuid.hex, 16)
    new_uid = f"2.25.{uid_int}"
    return new_uid[:64]


def apply_deterministic_sanitization(dataset: pydicom.Dataset, date_shift_days: int = 0) -> None:
    """
    Apply deterministic hashing and sanitization to a DICOM dataset.
    
    This function is called by ALL processing paths to ensure consistent
    treatment of accession numbers, dates, and UIDs.
    
    Args:
        dataset: pydicom Dataset to modify in-place
        date_shift_days: Number of days to shift dates (default: 0)
    """
    # ═════════════════════════════════════════════════════════════════════════
    # ACCESSION NUMBER - DELETE INSTEAD OF HASHING
    # ═════════════════════════════════════════════════════════════════════════
    
    # CRITICAL: DELETE ACCESSION NUMBER INSTEAD OF HASHING
    if (0x0008, 0x0050) in dataset:
        del dataset[0x0008, 0x0050]
    
    # ═════════════════════════════════════════════════════════════════════════
    # DATE SHIFTING - Consistent across all modes
    # ═════════════════════════════════════════════════════════════════════════
    
    if date_shift_days != 0:
        # List of date tags to shift
        date_tags = [
            'StudyDate', 'SeriesDate', 'AcquisitionDate', 
            'ContentDate', 'InstanceCreationDate',
            'PatientBirthDate'  # Also shift birth date for consistency
        ]
        
        for tag_name in date_tags:
            if hasattr(dataset, tag_name):
                try:
                    original_date = str(getattr(dataset, tag_name))
                    if len(original_date) >= 8:
                        # Parse YYYYMMDD format
                        year = int(original_date[:4])
                        month = int(original_date[4:6])
                        day = int(original_date[6:8])
                        
                        # Apply shift
                        original_dt = datetime(year, month, day)
                        shifted_dt = original_dt + timedelta(days=date_shift_days)
                        
                        # Write back in DICOM format
                        setattr(dataset, tag_name, shifted_dt.strftime("%Y%m%d"))
                except Exception:
                    # If date parsing fails, skip this tag
                    pass
    
    # ═════════════════════════════════════════════════════════════════════════
    # UID REMAPPING - Deterministic generation
    # ═════════════════════════════════════════════════════════════════════════
    
    uid_tags = [
        'SOPInstanceUID', 'SeriesInstanceUID', 'StudyInstanceUID',
        'MediaStorageSOPInstanceUID'  # File meta UID
    ]
    
    for tag_name in uid_tags:
        if hasattr(dataset, tag_name):
            try:
                original_uid = str(getattr(dataset, tag_name))
                new_uid = generate_deterministic_uid(original_uid)
                setattr(dataset, tag_name, new_uid)
            except Exception:
                pass
    
    # Handle file meta information separately
    if hasattr(dataset, 'file_meta'):
        if hasattr(dataset.file_meta, 'MediaStorageSOPInstanceUID'):
            try:
                original_uid = str(dataset.file_meta.MediaStorageSOPInstanceUID)
                new_uid = generate_deterministic_uid(original_uid)
                dataset.file_meta.MediaStorageSOPInstanceUID = new_uid
            except Exception:
                pass


def estimate_pixel_memory(ds: pydicom.Dataset) -> int:
    """
    Estimate the uncompressed RAM requirement in bytes.
    
    Args:
        ds: pydicom Dataset
        
    Returns:
        Estimated bytes (int)
    """
    try:
        rows = int(getattr(ds, "Rows", 0) or 0)
        cols = int(getattr(ds, "Columns", 0) or 0)
        frames = int(getattr(ds, "NumberOfFrames", 1) or 1)
        bits = int(getattr(ds, "BitsAllocated", 16) or 16)
        samples = int(getattr(ds, "SamplesPerPixel", 1) or 1)
        
        # Estimate raw size: H * W * Frames * (Bytes/Pixel) * Samples
        # bits // 8 usually gives 1 (8-bit) or 2 (16-bit). 
        # For calculation safety, use at least 1 byte if bits > 0
        bytes_per_sample = max(1, bits // 8)
        
        est_bytes = rows * cols * frames * bytes_per_sample * samples
        return est_bytes
    except Exception:
        return 0


def should_render_pixels(ds: pydicom.Dataset, max_raw_pixel_bytes: int = 75_000_000) -> bool:
    """
    Check if a DICOM dataset is too large for safe pixel rendering.
    
    Estimates the uncompressed RAM requirement.
    
    Args:
        ds: pydicom Dataset
        max_raw_pixel_bytes: Limit (default 75MB - conservative for Steam Deck shared RAM,
                             accounting for decompression overhead and copy operations)
        
    Returns:
        True if safe to render, False if exceeds limit
    """
    est_bytes = estimate_pixel_memory(ds)
    # If estimate is 0 (e.g. no rows/cols), we assume it's safe (likely no pixels)
    # or handle it elsewhere.
    if est_bytes == 0 and (not hasattr(ds, 'PixelData') or not ds.PixelData):
        return True

    return est_bytes <= max_raw_pixel_bytes


def evaluate_us_mask_memory_guard(ds: pydicom.Dataset, max_mb: int) -> tuple[bool, float]:
    """
    Decide whether to skip US masking based on estimated pixel memory.

    Args:
        ds: pydicom Dataset to evaluate (metadata-only read is sufficient).
        max_mb: Threshold in megabytes for US pixel masking.

    Returns:
        Tuple of (should_skip: bool, estimated_mb: float)
    """
    est_bytes = estimate_pixel_memory(ds)
    est_mb = est_bytes / (1024 * 1024)
    return est_mb > max_mb, est_mb


# ═══════════════════════════════════════════════════════════════════════════════
# FILE SIZE PRE-FLIGHT GUARD
# Phase 13: Prevents OOM by checking compressed file size BEFORE pydicom read
# ═══════════════════════════════════════════════════════════════════════════════

# Conservative limit for interactive pilot mode on memory-constrained systems
# This is the COMPRESSED file size - actual decompressed size may be 5-10x larger
MAX_DICOM_FILE_BYTES_INTERACTIVE = 50_000_000  # 50 MB


def check_file_size_limit(
    file_path: str, 
    max_bytes: int = MAX_DICOM_FILE_BYTES_INTERACTIVE
) -> tuple[bool, int]:
    """
    Pre-flight check: Verify file size is within limits BEFORE loading.
    
    This check runs BEFORE any pydicom operations to prevent OOM on
    memory-constrained systems (e.g., Steam Deck with high background load).
    
    Args:
        file_path: Path to DICOM file
        max_bytes: Maximum allowed file size in bytes (default: 50MB)
        
    Returns:
        Tuple of (is_safe: bool, file_size_bytes: int)
        
    Design note:
        This is the FIRST line of defense. It checks compressed file size,
        which is much smaller than decompressed pixel data. If this fails,
        we skip the file entirely without risking OOM.
    """
    import os
    try:
        file_size = os.path.getsize(file_path)
        return file_size <= max_bytes, file_size
    except (OSError, IOError):
        # If we can't stat the file, assume it's safe (will fail on read anyway)
        return True, 0


def require_file_size_limit(
    file_path: str,
    max_bytes: int = MAX_DICOM_FILE_BYTES_INTERACTIVE,
    context: str = "interactive mode"
) -> None:
    """
    Pre-flight check that raises MemoryError if file is too large.
    
    Use this at the top of any function that reads DICOM files interactively.
    
    Args:
        file_path: Path to DICOM file
        max_bytes: Maximum allowed file size in bytes
        context: Description for error message (e.g., "preview", "masking")
        
    Raises:
        MemoryError: If file exceeds size limit
    """
    is_safe, file_size = check_file_size_limit(file_path, max_bytes)
    if not is_safe:
        raise MemoryError(
            f"DICOM file too large for {context} "
            f"({file_size / 1e6:.1f} MB > {max_bytes / 1e6:.0f} MB limit). "
            f"Consider processing in batch mode or reducing background applications."
        )
