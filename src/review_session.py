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
    """
    session_id: str
    sop_instance_uid: str
    regions: List[ReviewRegion]
    review_started: bool
    review_accepted: bool
    created_at: str
    
    @classmethod
    def create(cls, sop_instance_uid: str) -> "ReviewSession":
        """Create a new review session."""
        return cls(
            session_id=str(uuid.uuid4()),
            sop_instance_uid=sop_instance_uid,
            regions=[],
            review_started=False,
            review_accepted=False,
            created_at=datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
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
            Dictionary with region counts
        """
        active = self.get_active_regions()
        return {
            "total_regions": len(self.regions),
            "ocr_regions": len([r for r in active if r.source == RegionSource.OCR]),
            "manual_regions": len([r for r in active if r.source == RegionSource.MANUAL]),
            "will_mask": len(self.get_masked_regions()),
            "will_unmask": len(self.get_unmasked_regions()),
        }
