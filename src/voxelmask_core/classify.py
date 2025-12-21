# src/voxelmask_core/classify.py
"""
DICOM file classification helpers for VoxelMask.

NO STREAMLIT IMPORTS ALLOWED IN THIS MODULE.

This module provides classification logic for DICOM files:
- Image (CT, MR, XR, US, etc.) 
- Document (SC, OT, SR, PDF)
- Unsupported

Classification determines:
- Which files require pixel masking
- Which files are documents (excluded by default)
- Risk levels for PHI exposure
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional
import os


class FileCategory(Enum):
    """Category of a DICOM file based on content type."""
    IMAGE = "image"
    DOCUMENT = "document"
    UNSUPPORTED = "unsupported"


class RiskLevel(Enum):
    """PHI risk level for a file type."""
    LOW = "low"        # CT, MR, XR - typically pixel-clean
    MEDIUM = "medium"  # SC, OT - may have burned-in PHI
    HIGH = "high"      # US - high risk of burned-in PHI in manufacturer regions


# Modalities that are pixel-clean (no burned-in PHI concerns)
PIXEL_CLEAN_MODALITIES = {
    'CT',    # Computed Tomography - large, pixel-clean
    'MR',    # Magnetic Resonance - large, pixel-clean  
    'XR',    # X-Ray - typically pixel-clean
    'CR',    # Computed Radiography - typically pixel-clean
    'DX',    # Digital X-Ray - typically pixel-clean
    'MG',    # Mammography - large, pixel-clean
    'PT',    # Positron Emission Tomography - large, pixel-clean
    'NM',    # Nuclear Medicine - large, pixel-clean
}

# Modalities requiring visual confirmation/masking
PREVIEW_REQUIRED_MODALITIES = {
    'US',    # Ultrasound - high risk of burned-in PHI
    'SC',    # Secondary Capture - screenshots, annotations
    'OT',    # Other - text-heavy modalities
    'SR',    # Structured Report - text-based
    'KO',    # Key Object Selection - annotations
}

# Modalities that are documents (not images)
DOCUMENT_MODALITIES = {
    'SC',    # Secondary Capture - often worksheets/screenshots
    'OT',    # Other - forms, reports
    'SR',    # Structured Report
}


@dataclass
class FileClassification:
    """
    Classification result for a DICOM file.
    
    Provides all information needed to decide:
    - Whether to include in processing
    - Whether to apply pixel masking
    - Risk assessment for audit
    """
    filepath: str
    filename: str
    modality: str
    sop_class_uid: str
    category: FileCategory
    risk_level: RiskLevel
    include_by_default: bool
    requires_preview: bool
    requires_masking: bool
    is_encapsulated_pdf: bool = False
    
    # Optional metadata extracted during classification
    series_description: Optional[str] = None
    
    @property
    def is_image(self) -> bool:
        return self.category == FileCategory.IMAGE
    
    @property
    def is_document(self) -> bool:
        return self.category == FileCategory.DOCUMENT
    
    @property
    def is_us(self) -> bool:
        return self.modality == 'US'


def classify_dicom_file(filepath: str) -> FileClassification:
    """
    Classify a DICOM file by type and risk level.
    
    This is the main classification entry point. It reads only metadata
    (stop_before_pixels=True) for efficiency.
    
    Args:
        filepath: Path to the DICOM file
        
    Returns:
        FileClassification with all classification results
        
    Raises:
        ValueError: If file cannot be read as DICOM
    """
    import pydicom
    
    try:
        ds = pydicom.dcmread(filepath, stop_before_pixels=True, force=True)
        
        # Add fallback for missing TransferSyntaxUID
        if not hasattr(ds, 'file_meta') or not hasattr(ds.file_meta, 'TransferSyntaxUID'):
            if not hasattr(ds, 'file_meta'):
                ds.file_meta = pydicom.dataset.FileMetaDataset()
            ds.file_meta.TransferSyntaxUID = pydicom.uid.ImplicitVRLittleEndian
    except Exception as e:
        raise ValueError(f"Cannot read DICOM file {filepath}: {e}")
    
    modality = str(getattr(ds, 'Modality', '')).upper()
    sop_class_uid = str(getattr(ds, 'SOPClassUID', ''))
    series_description = str(getattr(ds, 'SeriesDescription', ''))
    
    # Determine category and risk
    category, risk_level, include_by_default = _classify_by_modality_and_sop(
        modality, sop_class_uid
    )
    
    # Determine preview and masking requirements
    requires_preview = modality in PREVIEW_REQUIRED_MODALITIES
    requires_masking = modality == 'US'
    
    # Check for encapsulated PDF
    is_pdf = 'ENCAPSULATED PDF' in sop_class_uid.upper()
    
    return FileClassification(
        filepath=filepath,
        filename=os.path.basename(filepath),
        modality=modality,
        sop_class_uid=sop_class_uid,
        category=category,
        risk_level=risk_level,
        include_by_default=include_by_default,
        requires_preview=requires_preview,
        requires_masking=requires_masking,
        is_encapsulated_pdf=is_pdf,
        series_description=series_description if series_description else None,
    )


def _classify_by_modality_and_sop(
    modality: str, 
    sop_class_uid: str
) -> tuple[FileCategory, RiskLevel, bool]:
    """
    Internal classification logic based on modality and SOP class.
    
    Returns:
        Tuple of (category, risk_level, include_by_default)
    """
    # Check for Structured Report
    if modality == 'SR' or 'STRUCTURED REPORT' in sop_class_uid:
        return FileCategory.DOCUMENT, RiskLevel.HIGH, False
    
    # Check for Encapsulated PDF
    if 'ENCAPSULATED PDF' in sop_class_uid.upper():
        return FileCategory.DOCUMENT, RiskLevel.HIGH, False
    
    # Check for document modalities (SC, OT)
    if modality in DOCUMENT_MODALITIES:
        return FileCategory.DOCUMENT, RiskLevel.MEDIUM, False
    
    # Check for pixel-clean imaging modalities
    if modality in PIXEL_CLEAN_MODALITIES:
        return FileCategory.IMAGE, RiskLevel.LOW, True
    
    # Ultrasound - image but high risk
    if modality == 'US':
        return FileCategory.IMAGE, RiskLevel.HIGH, True
    
    # Unknown modality - default to image with medium risk
    return FileCategory.IMAGE, RiskLevel.MEDIUM, True


def should_show_preview(classification: FileClassification) -> bool:
    """
    Determine if a preview should be shown for this file.
    
    Previews are shown for modalities with PHI risk but skipped
    for large, pixel-clean modalities to save resources.
    """
    return classification.requires_preview


def is_pixel_clean_modality(modality: str) -> bool:
    """Check if a modality is considered pixel-clean (no burned-in PHI)."""
    return modality.upper() in PIXEL_CLEAN_MODALITIES


def bucket_classify_files(
    classifications: list[FileClassification]
) -> tuple[list[FileClassification], list[FileClassification], list[FileClassification], list[FileClassification]]:
    """
    Sort classified files into processing buckets.
    
    Returns:
        Tuple of (bucket_us, bucket_safe, bucket_docs, bucket_skip)
        - bucket_us: Ultrasound files requiring masking
        - bucket_safe: Pixel-clean imaging files
        - bucket_docs: Document files (SC, OT, SR, PDF)
        - bucket_skip: Files to skip (SR, PDF by default)
    """
    bucket_us = []
    bucket_safe = []
    bucket_docs = []
    bucket_skip = []
    
    for clf in classifications:
        if clf.modality == 'US':
            bucket_us.append(clf)
        elif clf.modality in PIXEL_CLEAN_MODALITIES:
            bucket_safe.append(clf)
        elif clf.category == FileCategory.DOCUMENT:
            if clf.modality in ('SR',) or clf.is_encapsulated_pdf:
                bucket_skip.append(clf)
            else:
                bucket_docs.append(clf)
        else:
            # Unknown - treat as safe
            bucket_safe.append(clf)
    
    return bucket_us, bucket_safe, bucket_docs, bucket_skip
