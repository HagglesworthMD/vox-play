"""
Selection Scope Module for VoxelMask
====================================
Phase 6: Explicit Document Inclusion Semantics

Provides explicit, auditable selection scope for operator intent.
Documents/secondary objects are NEVER included unless explicitly selected.

This is a governance requirement for FOI defensibility.

Author: VoxelMask Engineering
Version: 0.6.0-explicit-selection
"""

from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List
from datetime import datetime, timezone


# ═══════════════════════════════════════════════════════════════════════════════
# SELECTION SCOPE
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class SelectionScope:
    """
    Explicit selection scope for processing.
    
    Defines what categories of objects are included in output.
    Default is conservative: images included, documents excluded.
    
    Attributes:
        include_images: Whether to include imaging series (default True)
        include_documents: Whether to include documents/worksheets/SC (default False)
        
    Audit Requirements:
        - Selection scope MUST be recorded in every audit output
        - When documents are excluded, audit must explicitly state this
        - This protects FOI and vendor review
    """
    include_images: bool = True
    include_documents: bool = False
    
    # Metadata for audit trail
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"))
    modified_at: Optional[str] = None
    
    def set_include_documents(self, value: bool) -> None:
        """Set document inclusion with timestamp."""
        self.include_documents = value
        self.modified_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    
    def set_include_images(self, value: bool) -> None:
        """Set image inclusion with timestamp."""
        self.include_images = value
        self.modified_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert to dictionary for audit logging.
        
        Returns:
            Dictionary suitable for JSON serialization in audit output
        """
        return {
            "include_images": self.include_images,
            "include_documents": self.include_documents,
            "created_at": self.created_at,
            "modified_at": self.modified_at,
        }
    
    def get_exclusion_reason(self) -> Optional[str]:
        """
        Get human-readable exclusion reason for audit log.
        
        Returns:
            String describing what was excluded and why, or None if nothing excluded
        """
        excluded = []
        if not self.include_documents:
            excluded.append("Associated non-image objects were excluded based on explicit user selection.")
        if not self.include_images:
            excluded.append("Imaging series were excluded based on explicit user selection.")
        
        return " ".join(excluded) if excluded else None
    
    @classmethod
    def create_default(cls) -> "SelectionScope":
        """
        Create a new SelectionScope with default conservative settings.
        
        Default: Images included, Documents excluded
        """
        return cls(
            include_images=True,
            include_documents=False
        )


# ═══════════════════════════════════════════════════════════════════════════════
# DOCUMENT CLASSIFICATION
# ═══════════════════════════════════════════════════════════════════════════════

class ObjectCategory:
    """Categories for DICOM object classification."""
    IMAGE = "IMAGE"  # Standard imaging modalities (US, CT, MR, etc.)
    DOCUMENT = "DOCUMENT"  # SC, OT, worksheets, reports
    STRUCTURED_REPORT = "STRUCTURED_REPORT"  # SR modality
    ENCAPSULATED_PDF = "ENCAPSULATED_PDF"  # Encapsulated PDF Storage


# SOP Class UIDs for classification
DOCUMENT_SOP_CLASSES = {
    "1.2.840.10008.5.1.4.1.1.7": ObjectCategory.DOCUMENT,      # Secondary Capture Image Storage
    "1.2.840.10008.5.1.4.1.1.7.1": ObjectCategory.DOCUMENT,    # Multi-frame SC (Grayscale Byte)
    "1.2.840.10008.5.1.4.1.1.7.2": ObjectCategory.DOCUMENT,    # Multi-frame SC (Grayscale Word)
    "1.2.840.10008.5.1.4.1.1.7.3": ObjectCategory.DOCUMENT,    # Multi-frame SC (True Color)
    "1.2.840.10008.5.1.4.1.1.7.4": ObjectCategory.DOCUMENT,    # Multi-frame SC (True Color)
    "1.2.840.10008.5.1.4.1.1.104.1": ObjectCategory.ENCAPSULATED_PDF,  # Encapsulated PDF Storage
    "1.2.840.10008.5.1.4.1.1.88.11": ObjectCategory.STRUCTURED_REPORT,  # Basic Text SR
    "1.2.840.10008.5.1.4.1.1.88.22": ObjectCategory.STRUCTURED_REPORT,  # Enhanced SR
    "1.2.840.10008.5.1.4.1.1.88.33": ObjectCategory.STRUCTURED_REPORT,  # Comprehensive SR
    "1.2.840.10008.5.1.4.1.1.88.34": ObjectCategory.STRUCTURED_REPORT,  # Comprehensive 3D SR
    "1.2.840.10008.5.1.4.1.1.88.35": ObjectCategory.STRUCTURED_REPORT,  # Extensible SR
}

# Modalities that are always classified as documents
DOCUMENT_MODALITIES = {"SC", "OT", "SR", "DOC", "PR"}

# Keywords in SeriesDescription that indicate a document/worksheet
DOCUMENT_KEYWORDS = [
    "WORKSHEET", "REPORT", "SUMMARY", "FORM", "PAGE", 
    "CHART", "GRAPH", "DOCUMENT", "SCREEN", "TEXT", "TABLE",
    "OBSTETRIC", "GENERAL REPORT", "AUTHORISED", "MEASUREMENT"
]


def classify_object(
    modality: str,
    sop_class_uid: str,
    series_description: str = "",
    image_type: str = ""
) -> str:
    """
    Classify a DICOM object into a category.
    
    Args:
        modality: DICOM Modality tag value (e.g., "US", "SC", "OT")
        sop_class_uid: SOP Class UID string
        series_description: SeriesDescription tag value
        image_type: ImageType tag value(s) as string
        
    Returns:
        ObjectCategory constant (IMAGE, DOCUMENT, STRUCTURED_REPORT, or ENCAPSULATED_PDF)
    """
    modality = (modality or "").upper()
    series_description = (series_description or "").upper()
    image_type = (image_type or "").upper()
    
    # 1. Check SOP Class UID first (most reliable)
    if sop_class_uid in DOCUMENT_SOP_CLASSES:
        return DOCUMENT_SOP_CLASSES[sop_class_uid]
    
    # 2. Check modality
    if modality in DOCUMENT_MODALITIES:
        return ObjectCategory.DOCUMENT
    
    # 3. Check for document keywords in series description
    if any(kw in series_description for kw in DOCUMENT_KEYWORDS):
        return ObjectCategory.DOCUMENT
    
    # 4. Check for derived/secondary image type indicators
    if "DERIVED" in image_type and "SECONDARY" in image_type:
        # Check if series description indicates worksheet/report
        if any(kw in series_description for kw in ["REPORT", "WORKSHEET", "SUMMARY", "DOCUMENT"]):
            return ObjectCategory.DOCUMENT
    
    # Default: assume it's an image
    return ObjectCategory.IMAGE


def should_include_object(
    category: str,
    scope: SelectionScope
) -> bool:
    """
    Determine if an object should be included based on selection scope.
    
    Args:
        category: ObjectCategory constant
        scope: SelectionScope defining what to include
        
    Returns:
        True if object should be included, False otherwise
    """
    if category == ObjectCategory.IMAGE:
        return scope.include_images
    elif category in (ObjectCategory.DOCUMENT, ObjectCategory.STRUCTURED_REPORT, ObjectCategory.ENCAPSULATED_PDF):
        return scope.include_documents
    else:
        # Unknown category - conservative default to exclude
        return False


def get_category_label(category: str) -> str:
    """
    Get human-readable label for an object category.
    
    Args:
        category: ObjectCategory constant
        
    Returns:
        Human-readable string for UI display
    """
    labels = {
        ObjectCategory.IMAGE: "Imaging Series",
        ObjectCategory.DOCUMENT: "Associated Object (Worksheet/SC)",
        ObjectCategory.STRUCTURED_REPORT: "Associated Object (Structured Report)",
        ObjectCategory.ENCAPSULATED_PDF: "Associated Object (Encapsulated PDF)",
    }
    return labels.get(category, "Unknown Object Type")


# ═══════════════════════════════════════════════════════════════════════════════
# AUDIT HELPERS
# ═══════════════════════════════════════════════════════════════════════════════

def generate_scope_audit_block(scope: SelectionScope) -> str:
    """
    Generate audit log block for selection scope.
    
    This block MUST appear in every audit output.
    
    Args:
        scope: SelectionScope to document
        
    Returns:
        Multi-line string for inclusion in audit log
    """
    lines = [
        "═" * 60,
        "SELECTION SCOPE",
        "─" * 60,
        "",
        f"Include Imaging Series:      {'YES' if scope.include_images else 'NO'}",
        f"Include Associated Documents: {'YES' if scope.include_documents else 'NO'}",
        "",
    ]
    
    exclusion_reason = scope.get_exclusion_reason()
    if exclusion_reason:
        lines.extend([
            "EXCLUSION NOTE:",
            f"  {exclusion_reason}",
            "",
        ])
    
    lines.extend([
        f"Scope Created:  {scope.created_at}",
    ])
    
    if scope.modified_at:
        lines.append(f"Scope Modified: {scope.modified_at}")
    
    lines.extend([
        "",
        "═" * 60,
    ])
    
    return "\n".join(lines)


def generate_scope_json(scope: SelectionScope) -> Dict[str, Any]:
    """
    Generate JSON-compatible dictionary for evidence bundle.
    
    Args:
        scope: SelectionScope to serialize
        
    Returns:
        Dictionary for JSON serialization
    """
    result = {
        "selection_scope": scope.to_dict(),
    }
    
    exclusion_reason = scope.get_exclusion_reason()
    if exclusion_reason:
        result["exclusion_note"] = exclusion_reason
    
    return result
