# src/voxelmask_core/selection.py
"""
File and study selection logic for VoxelMask.

NO STREAMLIT IMPORTS ALLOWED IN THIS MODULE.

This module handles:
- Filtering files by selection scope
- Determining which files to include in processing
- Building file selection state for the manifest
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Set, Tuple

from .classify import FileClassification, FileCategory


@dataclass
class SelectionResult:
    """
    Result of applying selection scope to a list of files.
    
    Tracks included/excluded counts for UI display.
    """
    included_files: List[Any]  # File buffer objects
    excluded_files: List[Any]
    
    # Counts by category
    included_image_count: int = 0
    included_document_count: int = 0
    excluded_document_count: int = 0
    excluded_by_user_count: int = 0
    
    @property
    def total_included(self) -> int:
        return len(self.included_files)
    
    @property
    def total_excluded(self) -> int:
        return len(self.excluded_files)


@dataclass
class SelectionScope:
    """
    Defines what types of objects are included in processing.
    
    This is a simplified version of the SelectionScope in selection_scope.py
    for use in core logic without Streamlit dependencies.
    """
    include_images: bool = True
    include_documents: bool = False
    
    def should_include_category(self, category: FileCategory) -> bool:
        """Check if a file category should be included."""
        if category == FileCategory.IMAGE:
            return self.include_images
        elif category == FileCategory.DOCUMENT:
            return self.include_documents
        return False


def apply_selection_scope(
    all_files: List[Any],
    classifications: Dict[str, FileClassification],
    selection_scope: SelectionScope,
    *,
    excluded_filenames: Optional[Set[str]] = None,
    selected_in_manifest: Optional[Set[str]] = None,
) -> SelectionResult:
    """
    Apply selection scope filtering to a list of files.
    
    Args:
        all_files: List of file buffer objects (with .name attribute)
        classifications: Dict mapping filename to FileClassification
        selection_scope: SelectionScope defining inclusion rules
        excluded_filenames: Optional set of filenames excluded by user (e.g., PDFs)
        selected_in_manifest: Optional set of filenames selected in manifest UI
        
    Returns:
        SelectionResult with included/excluded files and counts
    """
    included = []
    excluded = []
    
    included_image_count = 0
    included_document_count = 0
    excluded_document_count = 0
    excluded_by_user_count = 0
    
    excluded_filenames = excluded_filenames or set()
    
    for fb in all_files:
        filename = fb.name
        
        # Check manifest selection first
        if selected_in_manifest is not None and filename not in selected_in_manifest:
            excluded.append(fb)
            continue
        
        # Check user exclusion (e.g., PDF exclusion checkboxes)
        if filename in excluded_filenames:
            excluded.append(fb)
            excluded_by_user_count += 1
            continue
        
        # Get classification
        clf = classifications.get(filename)
        if clf is None:
            # No classification - include by default
            included.append(fb)
            included_image_count += 1
            continue
        
        # Apply selection scope
        if clf.category == FileCategory.IMAGE:
            if selection_scope.include_images:
                included.append(fb)
                included_image_count += 1
            else:
                excluded.append(fb)
        elif clf.category == FileCategory.DOCUMENT:
            if selection_scope.include_documents:
                included.append(fb)
                included_document_count += 1
            else:
                excluded.append(fb)
                excluded_document_count += 1
        else:
            # Unsupported - exclude
            excluded.append(fb)
    
    return SelectionResult(
        included_files=included,
        excluded_files=excluded,
        included_image_count=included_image_count,
        included_document_count=included_document_count,
        excluded_document_count=excluded_document_count,
        excluded_by_user_count=excluded_by_user_count,
    )


def compute_bucket_assignment(
    files: List[Any],
    classifications: Dict[str, FileClassification],
) -> Dict[str, List[Any]]:
    """
    Assign files to processing buckets based on classification.
    
    Returns:
        Dict with keys: 'us', 'safe', 'docs', 'skip'
    """
    buckets = {
        'us': [],      # Ultrasound files requiring masking
        'safe': [],    # Pixel-clean imaging files  
        'docs': [],    # Document files (SC, OT)
        'skip': [],    # Files to skip (SR, PDF)
    }
    
    for fb in files:
        clf = classifications.get(fb.name)
        if clf is None:
            buckets['safe'].append(fb)
            continue
        
        if clf.modality == 'US':
            buckets['us'].append(fb)
        elif clf.is_encapsulated_pdf or clf.modality == 'SR':
            buckets['skip'].append(fb)
        elif clf.category == FileCategory.DOCUMENT:
            buckets['docs'].append(fb)
        else:
            buckets['safe'].append(fb)
    
    return buckets


def get_selection_summary(
    result: SelectionResult,
    include_documents_enabled: bool,
) -> Dict[str, Any]:
    """
    Get a summary of selection state for display.
    
    Returns dict with keys suitable for UI rendering.
    """
    return {
        'total_selected': result.total_included,
        'total_excluded': result.total_excluded,
        'images_included': result.included_image_count,
        'documents_included': result.included_document_count,
        'documents_excluded': result.excluded_document_count,
        'user_excluded': result.excluded_by_user_count,
        'include_documents_enabled': include_documents_enabled,
        'has_excluded_documents': result.excluded_document_count > 0,
    }
