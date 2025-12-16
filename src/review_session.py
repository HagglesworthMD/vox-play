"""
Review Session Module for VoxelMask
====================================
Sprint 2: Burned-In PHI Review Overlay

Manages review state for burned-in PHI regions. Provides:
- ReviewRegion: Single reviewable region (OCR or manual)
- ReviewSession: Session state for the review workflow

Contains ONLY geometric and action state — never text content.
PHI-free by design.

Author: VoxelMask Engineering
Version: 0.4.0
"""

from dataclasses import dataclass, field
from typing import List, Optional, Dict
from datetime import datetime, timezone
import uuid


# ═══════════════════════════════════════════════════════════════════════════════
# ENUMERATIONS
# ═══════════════════════════════════════════════════════════════════════════════

class RegionSource:
    """Source of a review region."""
    OCR = "OCR"
    MANUAL = "MANUAL"


class RegionAction:
    """Possible actions for a region."""
    MASK = "MASK"
    UNMASK = "UNMASK"
    DELETED = "DELETED"


class DetectionStrength:
    """
    Detection strength levels (non-statistical).
    
    Never display as percentages or "confidence" to avoid clinical implications.
    """
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class FindingType:
    """
    Types of findings identified during preflight scan.
    
    Used to classify DICOM objects that require review attention.
    """
    SECONDARY_CAPTURE = "SECONDARY_CAPTURE"
    ENCAPSULATED_PDF = "ENCAPSULATED_PDF"


# ═══════════════════════════════════════════════════════════════════════════════
# SOP CLASS UIDs FOR PREFLIGHT DETECTION
# ═══════════════════════════════════════════════════════════════════════════════

# Standard DICOM SOP Class UIDs for preflight detection
SOP_CLASS_UIDS = {
    "SECONDARY_CAPTURE": "1.2.840.10008.5.1.4.1.1.7",       # Secondary Capture Image Storage
    "ENCAPSULATED_PDF": "1.2.840.10008.5.1.4.1.1.104.1",   # Encapsulated PDF Storage
}


# ═══════════════════════════════════════════════════════════════════════════════
# REVIEW FINDING
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class ReviewFinding:
    """
    Represents a finding identified during preflight scan.
    
    This is a deterministic, reproducible record of DICOM objects that
    require review attention (e.g., Secondary Capture, Encapsulated PDF).
    
    Contains ONLY UIDs and classification — no PHI.
    """
    sop_instance_uid: str
    sop_class_uid: str
    series_instance_uid: str
    finding_type: str  # FindingType.SECONDARY_CAPTURE or FindingType.ENCAPSULATED_PDF
    modality: Optional[str]  # DICOM Modality tag value (e.g., "SC", "DOC")
    description: str  # Human-readable description
    excluded: bool = False  # User-driven exclusion flag (default: included)
    excluded_at: Optional[str] = None  # UTC timestamp when exclusion was set
    
    @classmethod
    def from_sop_class(
        cls,
        sop_instance_uid: str,
        sop_class_uid: str,
        series_instance_uid: str,
        modality: Optional[str] = None,
    ) -> Optional["ReviewFinding"]:
        """
        Create a ReviewFinding based on SOP Class UID classification.
        
        Returns None if the SOP Class UID is not a reviewable type.
        
        Args:
            sop_instance_uid: SOP Instance UID of the DICOM object
            sop_class_uid: SOP Class UID for classification
            series_instance_uid: Series Instance UID
            modality: Optional DICOM Modality tag value
            
        Returns:
            ReviewFinding if classifiable, None otherwise
        """
        if sop_class_uid == SOP_CLASS_UIDS["SECONDARY_CAPTURE"]:
            return cls(
                sop_instance_uid=sop_instance_uid,
                sop_class_uid=sop_class_uid,
                series_instance_uid=series_instance_uid,
                finding_type=FindingType.SECONDARY_CAPTURE,
                modality=modality,
                description="Secondary Capture image detected - may contain scanned documents or screenshots",
            )
        elif sop_class_uid == SOP_CLASS_UIDS["ENCAPSULATED_PDF"]:
            return cls(
                sop_instance_uid=sop_instance_uid,
                sop_class_uid=sop_class_uid,
                series_instance_uid=series_instance_uid,
                finding_type=FindingType.ENCAPSULATED_PDF,
                modality=modality,
                description="Encapsulated PDF detected - document embedded in DICOM wrapper",
            )
        return None
    
    def to_dict(self) -> Dict[str, Optional[str]]:
        """
        Convert to dictionary for serialization.
        
        Returns:
            Dictionary representation of the finding
        """
        return {
            "sop_instance_uid": self.sop_instance_uid,
            "sop_class_uid": self.sop_class_uid,
            "series_instance_uid": self.series_instance_uid,
            "finding_type": self.finding_type,
            "modality": self.modality,
            "description": self.description,
            "excluded": self.excluded,
            "excluded_at": self.excluded_at,
        }
    
    def set_excluded(self, excluded: bool) -> None:
        """
        Set the exclusion state for this finding.
        
        Args:
            excluded: True to exclude from export, False to include
        """
        self.excluded = excluded
        if excluded:
            self.excluded_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        else:
            self.excluded_at = None


# ═══════════════════════════════════════════════════════════════════════════════
# REVIEW REGION
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class ReviewRegion:
    """
    Represents a single reviewable region in the burned-in PHI workflow.
    
    Contains ONLY geometric and action state — never text content.
    This is enforced by design: there is no field for OCR text.
    """
    region_id: str
    x: int
    y: int
    w: int
    h: int
    source: str  # RegionSource.OCR or RegionSource.MANUAL
    default_action: str  # RegionAction.MASK or RegionAction.UNMASK
    reviewer_action: Optional[str] = None  # None, MASK, UNMASK, or DELETED
    detection_strength: Optional[str] = None  # LOW, MEDIUM, HIGH (for OCR)
    frame_index: int = -1  # -1 = all frames, >= 0 = specific frame
    
    @classmethod
    def create_ocr_region(
        cls,
        x: int,
        y: int,
        w: int,
        h: int,
        detection_strength: Optional[str] = None,
        frame_index: int = -1
    ) -> "ReviewRegion":
        """
        Create an OCR-detected region.
        
        Default action is MASK (conservative).
        """
        return cls(
            region_id=f"r-{uuid.uuid4().hex[:8]}",
            x=x,
            y=y,
            w=w,
            h=h,
            source=RegionSource.OCR,
            default_action=RegionAction.MASK,
            reviewer_action=None,
            detection_strength=detection_strength,
            frame_index=frame_index
        )
    
    @classmethod
    def create_manual_region(
        cls,
        x: int,
        y: int,
        w: int,
        h: int,
        frame_index: int = -1
    ) -> "ReviewRegion":
        """
        Create a manually-drawn region.
        
        Default action is MASK. Detection strength is always None.
        """
        return cls(
            region_id=f"r-{uuid.uuid4().hex[:8]}",
            x=x,
            y=y,
            w=w,
            h=h,
            source=RegionSource.MANUAL,
            default_action=RegionAction.MASK,
            reviewer_action=None,
            detection_strength=None,
            frame_index=frame_index
        )
    
    def get_effective_action(self) -> str:
        """
        Return the effective action (reviewer override or default).
        
        Returns:
            RegionAction.MASK, UNMASK, or DELETED
        """
        if self.reviewer_action is not None:
            return self.reviewer_action
        return self.default_action
    
    def toggle(self) -> None:
        """Toggle between MASK and UNMASK."""
        current = self.get_effective_action()
        if current == RegionAction.MASK:
            self.reviewer_action = RegionAction.UNMASK
        else:
            self.reviewer_action = RegionAction.MASK
    
    def set_mask(self) -> None:
        """Explicitly set to MASK."""
        self.reviewer_action = RegionAction.MASK
    
    def set_unmask(self) -> None:
        """Explicitly set to UNMASK."""
        self.reviewer_action = RegionAction.UNMASK
    
    def reset(self) -> None:
        """Reset reviewer_action to None (use default)."""
        self.reviewer_action = None
    
    def mark_deleted(self) -> None:
        """
        Mark this region as deleted.
        
        Raises:
            ValueError: If this is an OCR region (cannot delete OCR regions)
        """
        if self.source == RegionSource.OCR:
            raise ValueError("OCR regions cannot be deleted")
        self.reviewer_action = RegionAction.DELETED
    
    def is_deleted(self) -> bool:
        """Check if region is marked as deleted."""
        return self.reviewer_action == RegionAction.DELETED
    
    def can_delete(self) -> bool:
        """Check if this region can be deleted."""
        return self.source == RegionSource.MANUAL
    
    def is_modified(self) -> bool:
        """Check if reviewer has modified this region."""
        return self.reviewer_action is not None
    
    def applies_to_all_frames(self) -> bool:
        """Check if this region applies to all frames."""
        return self.frame_index == -1


# ═══════════════════════════════════════════════════════════════════════════════
# REVIEW SESSION
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class ReviewSession:
    """
    Session state for the burned-in PHI review workflow.
    
    Stored in Streamlit session_state, never persisted to database.
    Once accepted, the session is sealed and no further modifications are allowed.
    
    Attributes:
        review_findings: List of ReviewFinding objects from preflight scan.
                         These are informational records and do NOT affect processing.
        file_uid_mapping: Deterministic mapping of filename → SOPInstanceUID.
                         Populated once at preflight scan time, used for export filtering.
    """
    session_id: str
    sop_instance_uid: str
    regions: List[ReviewRegion]
    review_started: bool
    review_accepted: bool
    created_at: str
    review_findings: List[ReviewFinding] = field(default_factory=list)
    file_uid_mapping: Dict[str, str] = field(default_factory=dict)  # filename → SOPInstanceUID
    
    @classmethod
    def create(cls, sop_instance_uid: str) -> "ReviewSession":
        """Create a new review session."""
        return cls(
            session_id=str(uuid.uuid4()),
            sop_instance_uid=sop_instance_uid,
            regions=[],
            review_started=False,
            review_accepted=False,
            created_at=datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            review_findings=[],
            file_uid_mapping={},
        )
    
    def _check_not_sealed(self) -> None:
        """Raise if session is sealed."""
        if self.review_accepted:
            raise RuntimeError("Session is sealed after accept")
    
    def is_sealed(self) -> bool:
        """Check if session is sealed (accepted)."""
        return self.review_accepted
    
    def add_ocr_region(
        self,
        x: int,
        y: int,
        w: int,
        h: int,
        detection_strength: Optional[str] = None,
        frame_index: int = -1
    ) -> ReviewRegion:
        """Add an OCR-detected region."""
        self._check_not_sealed()
        region = ReviewRegion.create_ocr_region(
            x=x, y=y, w=w, h=h,
            detection_strength=detection_strength,
            frame_index=frame_index
        )
        self.regions.append(region)
        return region
    
    def add_manual_region(
        self,
        x: int,
        y: int,
        w: int,
        h: int,
        frame_index: int = -1
    ) -> ReviewRegion:
        """Add a manually-drawn region."""
        self._check_not_sealed()
        region = ReviewRegion.create_manual_region(
            x=x, y=y, w=w, h=h,
            frame_index=frame_index
        )
        self.regions.append(region)
        return region
    
    def start_review(self) -> None:
        """Mark the review as started (user has entered review mode)."""
        self.review_started = True
    
    def can_accept(self) -> bool:
        """Check if the session can be accepted."""
        return self.review_started and not self.review_accepted
    
    def accept(self) -> None:
        """
        Accept the review and seal the session.
        
        After this, no modifications are allowed.
        
        Raises:
            RuntimeError: If review not started or already accepted
        """
        if not self.review_started:
            raise RuntimeError("Cannot accept: review not started")
        if self.review_accepted:
            raise RuntimeError("Cannot accept: already accepted")
        self.review_accepted = True
    
    def toggle_region(self, region_id: str) -> None:
        """Toggle a region by ID."""
        self._check_not_sealed()
        for region in self.regions:
            if region.region_id == region_id:
                region.toggle()
                return
        raise ValueError(f"Region not found: {region_id}")
    
    def delete_region(self, region_id: str) -> None:
        """Delete a manual region by ID."""
        self._check_not_sealed()
        for region in self.regions:
            if region.region_id == region_id:
                region.mark_deleted()
                return
        raise ValueError(f"Region not found: {region_id}")
    
    def mask_all_detected(self) -> None:
        """Set all OCR regions to MASK."""
        self._check_not_sealed()
        for region in self.regions:
            if region.source == RegionSource.OCR and not region.is_deleted():
                region.set_mask()
    
    def unmask_all(self) -> None:
        """Set all regions to UNMASK."""
        self._check_not_sealed()
        for region in self.regions:
            if not region.is_deleted():
                region.set_unmask()
    
    def reset_to_defaults(self) -> None:
        """
        Reset OCR regions to defaults and mark manual regions as deleted.
        """
        self._check_not_sealed()
        for region in self.regions:
            if region.source == RegionSource.OCR:
                region.reset()
            elif region.source == RegionSource.MANUAL:
                region.mark_deleted()
    
    def clear_manual_regions(self) -> None:
        """Mark all manual regions as deleted."""
        self._check_not_sealed()
        for region in self.regions:
            if region.source == RegionSource.MANUAL:
                region.mark_deleted()
    
    def get_regions(self) -> List[ReviewRegion]:
        """Get all regions (including deleted)."""
        return list(self.regions)
    
    def get_active_regions(self) -> List[ReviewRegion]:
        """Get all non-deleted regions."""
        return [r for r in self.regions if not r.is_deleted()]
    
    def get_masked_regions(self) -> List[ReviewRegion]:
        """Get all regions that will be masked."""
        return [
            r for r in self.regions
            if not r.is_deleted() and r.get_effective_action() == RegionAction.MASK
        ]
    
    def get_unmasked_regions(self) -> List[ReviewRegion]:
        """Get all regions that will NOT be masked (overrides)."""
        return [
            r for r in self.regions
            if not r.is_deleted() and r.get_effective_action() == RegionAction.UNMASK
        ]
    
    def get_summary(self) -> Dict[str, int]:
        """
        Get summary statistics.
        
        Returns:
            Dictionary with region counts and findings count
        """
        active = self.get_active_regions()
        return {
            "total_regions": len(self.regions),
            "ocr_regions": len([r for r in active if r.source == RegionSource.OCR]),
            "manual_regions": len([r for r in active if r.source == RegionSource.MANUAL]),
            "will_mask": len(self.get_masked_regions()),
            "will_unmask": len(self.get_unmasked_regions()),
            "review_findings": len(self.review_findings),
        }
    
    # ═══════════════════════════════════════════════════════════════════════════
    # PREFLIGHT SCAN FINDINGS
    # ═══════════════════════════════════════════════════════════════════════════
    
    def add_finding(self, finding: ReviewFinding) -> None:
        """
        Add a preflight scan finding to the session.
        
        Findings are informational records that do NOT affect processing.
        They can be added even after the session is sealed (read-only additions).
        
        Args:
            finding: ReviewFinding to add
        """
        self.review_findings.append(finding)
    
    def get_findings(self) -> List[ReviewFinding]:
        """
        Get all preflight scan findings.
        
        Returns:
            List of ReviewFinding objects
        """
        return list(self.review_findings)
    
    def get_findings_by_type(self, finding_type: str) -> List[ReviewFinding]:
        """
        Get findings filtered by type.
        
        Args:
            finding_type: FindingType.SECONDARY_CAPTURE or FindingType.ENCAPSULATED_PDF
            
        Returns:
            Filtered list of ReviewFinding objects
        """
        return [f for f in self.review_findings if f.finding_type == finding_type]
    
    def has_findings(self) -> bool:
        """
        Check if session has any preflight findings.
        
        Returns:
            True if there are any findings, False otherwise
        """
        return len(self.review_findings) > 0
    
    def get_findings_summary(self) -> Dict[str, int]:
        """
        Get summary of findings by type.
        
        Returns:
            Dictionary with finding type counts
        """
        pdf_findings = self.get_findings_by_type(FindingType.ENCAPSULATED_PDF)
        return {
            "total_findings": len(self.review_findings),
            "secondary_capture": len(self.get_findings_by_type(FindingType.SECONDARY_CAPTURE)),
            "encapsulated_pdf": len(pdf_findings),
            "excluded_pdf": len([f for f in pdf_findings if f.excluded]),
        }
    
    # ═══════════════════════════════════════════════════════════════════════════
    # PDF EXCLUSION (User-Driven, Logged)
    # Phase 2: Manual exclusion of Encapsulated PDFs from export
    # ═══════════════════════════════════════════════════════════════════════════
    
    def set_pdf_excluded(self, sop_instance_uid: str, excluded: bool) -> bool:
        """
        Set exclusion state for an Encapsulated PDF finding.
        
        This is a user-driven action that marks a PDF for exclusion from export.
        The PDF is NOT deleted — it simply won't be included in the export manifest.
        
        This method can be called until the session is sealed (accept).
        
        Args:
            sop_instance_uid: SOP Instance UID of the PDF to exclude/include
            excluded: True to exclude from export, False to include
            
        Returns:
            True if the finding was found and updated, False otherwise
        """
        # Allow modification until sealed
        if self.is_sealed():
            return False
        
        for finding in self.review_findings:
            if (finding.sop_instance_uid == sop_instance_uid and 
                finding.finding_type == FindingType.ENCAPSULATED_PDF):
                finding.set_excluded(excluded)
                return True
        return False
    
    def get_excluded_pdf_uids(self) -> List[str]:
        """
        Get SOP Instance UIDs of all excluded PDFs.
        
        These UIDs should be filtered from the export manifest.
        
        Returns:
            List of SOP Instance UIDs marked for exclusion
        """
        return [
            f.sop_instance_uid 
            for f in self.review_findings 
            if f.finding_type == FindingType.ENCAPSULATED_PDF and f.excluded
        ]
    
    def get_pdf_findings(self) -> List[ReviewFinding]:
        """
        Get all Encapsulated PDF findings.
        
        Returns:
            List of PDF findings (both excluded and included)
        """
        return self.get_findings_by_type(FindingType.ENCAPSULATED_PDF)
    
    # ═══════════════════════════════════════════════════════════════════════════
    # FILE UID MAPPING (Deterministic, Hardened)
    # Phase 2 Safety: Reliable filename ↔ SOPInstanceUID resolution
    # ═══════════════════════════════════════════════════════════════════════════
    
    def register_file_uid(self, filename: str, sop_instance_uid: str, sop_class_uid: str) -> None:
        """
        Register a deterministic mapping from filename to SOP Instance UID.
        
        This is called ONCE during preflight scan when the dataset is read.
        The mapping is used later for reliable export filtering.
        
        Args:
            filename: The file name (not path) to register
            sop_instance_uid: The SOP Instance UID from the DICOM dataset
            sop_class_uid: The SOP Class UID for type verification
        """
        # Store as tuple (sop_instance_uid, sop_class_uid) for verification
        self.file_uid_mapping[filename] = (sop_instance_uid, sop_class_uid)
    
    def get_excluded_filenames(self) -> List[str]:
        """
        Get filenames of files that should be excluded from export.
        
        Uses the stored deterministic mapping to resolve SOP Instance UIDs
        to filenames. Only Encapsulated PDFs can be excluded.
        
        Returns:
            List of filenames to exclude from export manifest
        """
        excluded_uids = set(self.get_excluded_pdf_uids())
        if not excluded_uids:
            return []
        
        result = []
        for filename, (sop_uid, sop_class) in self.file_uid_mapping.items():
            # Only exclude if:
            # 1. UID matches an excluded PDF
            # 2. SOP Class confirms it's an Encapsulated PDF (safety check)
            if (sop_uid in excluded_uids and 
                sop_class == SOP_CLASS_UIDS["ENCAPSULATED_PDF"]):
                result.append(filename)
        
        return result
    
    def get_sop_uid_for_file(self, filename: str) -> Optional[str]:
        """
        Get the SOP Instance UID for a registered filename.
        
        Args:
            filename: The file name to look up
            
        Returns:
            SOP Instance UID if found, None otherwise
        """
        mapping = self.file_uid_mapping.get(filename)
        return mapping[0] if mapping else None
    
    def has_file_uid_mapping(self) -> bool:
        """Check if any file UID mappings have been registered."""
        return len(self.file_uid_mapping) > 0


# ═══════════════════════════════════════════════════════════════════════════════
# PREFLIGHT SCAN UTILITY FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════════════

def preflight_scan_dataset(
    ds,  # pydicom.Dataset - not typed to avoid import dependency
) -> Optional[ReviewFinding]:
    """
    Perform preflight scan on a single DICOM dataset.
    
    Identifies Secondary Capture and Encapsulated PDF instances based on
    SOP Class UID. This is a passive detection function that does NOT
    modify the dataset or affect processing behavior.
    
    This function is deterministic and reproducible - the same dataset
    will always produce the same finding (or None).
    
    Args:
        ds: pydicom Dataset object
        
    Returns:
        ReviewFinding if the dataset is a reviewable type, None otherwise
        
    Example:
        >>> import pydicom
        >>> ds = pydicom.dcmread("secondary_capture.dcm")
        >>> finding = preflight_scan_dataset(ds)
        >>> if finding:
        ...     session.add_finding(finding)
    """
    # Extract required UIDs with safe defaults
    sop_class_uid = getattr(ds, "SOPClassUID", None)
    if sop_class_uid is None:
        return None
    
    # Convert to string if pydicom UID object
    sop_class_uid = str(sop_class_uid)
    
    sop_instance_uid = str(getattr(ds, "SOPInstanceUID", "UNKNOWN"))
    series_instance_uid = str(getattr(ds, "SeriesInstanceUID", "UNKNOWN"))
    modality = getattr(ds, "Modality", None)
    if modality is not None:
        modality = str(modality)
    
    # Use ReviewFinding.from_sop_class for classification
    return ReviewFinding.from_sop_class(
        sop_instance_uid=sop_instance_uid,
        sop_class_uid=sop_class_uid,
        series_instance_uid=series_instance_uid,
        modality=modality,
    )


def preflight_scan_datasets(
    datasets: list,  # List of pydicom.Dataset
) -> List[ReviewFinding]:
    """
    Perform preflight scan on multiple DICOM datasets.
    
    Convenience function for batch processing.
    
    Args:
        datasets: List of pydicom Dataset objects
        
    Returns:
        List of ReviewFinding objects for all reviewable datasets
    """
    findings = []
    for ds in datasets:
        finding = preflight_scan_dataset(ds)
        if finding is not None:
            findings.append(finding)
    return findings


# ═══════════════════════════════════════════════════════════════════════════════
# PHASE 4: DETECTION RESULT → REVIEW SESSION BRIDGE
# Wires OCR detection strength into review workflow
# ═══════════════════════════════════════════════════════════════════════════════

def populate_regions_from_detection(
    session: ReviewSession,
    detection_result,  # DetectionResult from run_on_dicom (not typed to avoid circular import)
    frame_index: int = -1,
) -> int:
    """
    Populate ReviewSession with detected regions from OCR output.
    
    Phase 4: Wires detection_strength from OCR engine to review regions.
    This is a plumbing function — no behavior change, purely data flow.
    
    Args:
        session: ReviewSession to populate
        detection_result: DetectionResult from detect_text_box_from_array()
        frame_index: Frame index for regions (-1 = all frames)
        
    Returns:
        Number of regions added
        
    Example:
        >>> from run_on_dicom import detect_text_box_from_array, DetectionResult
        >>> from review_session import ReviewSession, populate_regions_from_detection
        >>> 
        >>> result = detect_text_box_from_array(corrector, arr)
        >>> session = ReviewSession.create(sop_instance_uid="1.2.3")
        >>> count = populate_regions_from_detection(session, result)
        >>> print(f"Added {count} regions with strength={result.detection_strength}")
    """
    if session.is_sealed():
        return 0
    
    # Extract detection strength from result
    # None = OCR failure (explicit uncertainty)
    detection_strength = getattr(detection_result, 'detection_strength', None)
    
    # Get all detected boxes
    all_boxes = getattr(detection_result, 'all_detected_boxes', [])
    
    count = 0
    for box in all_boxes:
        if len(box) == 4:
            x, y, w, h = box
            session.add_ocr_region(
                x=int(x),
                y=int(y),
                w=int(w),
                h=int(h),
                detection_strength=detection_strength,
                frame_index=frame_index,
            )
            count += 1
    
    return count
