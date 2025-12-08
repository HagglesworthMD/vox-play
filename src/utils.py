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
