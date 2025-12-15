"""
Unit Tests for Review Session Module
=====================================
Sprint 2: Burned-In PHI Review Overlay

Tests for ReviewRegion and ReviewSession state management.

Run: PYTHONPATH=src pytest tests/test_review_session_unit.py -v
"""

import pytest
import uuid
from datetime import datetime, timezone

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from review_session import (
    ReviewRegion,
    ReviewSession,
    RegionSource,
    RegionAction,
    DetectionStrength,
)


# ═══════════════════════════════════════════════════════════════════════════════
# REVIEWREGION CREATION TESTS
# ═══════════════════════════════════════════════════════════════════════════════

class TestReviewRegionCreation:
    """Tests for ReviewRegion dataclass creation."""
    
    def test_create_ocr_region_with_defaults(self):
        """OCR region should be created with MASK default."""
        region = ReviewRegion.create_ocr_region(
            x=50, y=100, w=400, h=80
        )
        
        assert region.x == 50
        assert region.y == 100
        assert region.w == 400
        assert region.h == 80
        assert region.source == RegionSource.OCR
        assert region.default_action == RegionAction.MASK
        assert region.reviewer_action is None
        assert region.frame_index == -1  # All frames
        assert region.region_id.startswith("r-")
    
    def test_create_ocr_region_with_detection_strength(self):
        """OCR region can have detection strength."""
        region = ReviewRegion.create_ocr_region(
            x=50, y=100, w=400, h=80,
            detection_strength=DetectionStrength.HIGH
        )
        
        assert region.detection_strength == DetectionStrength.HIGH
    
    def test_create_ocr_region_specific_frame(self):
        """OCR region can target specific frame."""
        region = ReviewRegion.create_ocr_region(
            x=50, y=100, w=400, h=80,
            frame_index=5
        )
        
        assert region.frame_index == 5
    
    def test_create_manual_region(self):
        """Manual region should be created with MASK default."""
        region = ReviewRegion.create_manual_region(
            x=200, y=300, w=150, h=40
        )
        
        assert region.x == 200
        assert region.y == 300
        assert region.w == 150
        assert region.h == 40
        assert region.source == RegionSource.MANUAL
        assert region.default_action == RegionAction.MASK
        assert region.reviewer_action is None
        assert region.detection_strength is None
    
    def test_region_id_is_unique(self):
        """Each region should get a unique ID."""
        region1 = ReviewRegion.create_ocr_region(x=10, y=10, w=100, h=50)
        region2 = ReviewRegion.create_ocr_region(x=20, y=20, w=100, h=50)
        
        assert region1.region_id != region2.region_id
    
    def test_frame_index_negative_one_means_all_frames(self):
        """frame_index = -1 should mean all frames."""
        region = ReviewRegion.create_ocr_region(x=10, y=10, w=100, h=50)
        
        assert region.frame_index == -1
        assert region.applies_to_all_frames()
    
    def test_frame_index_zero_or_positive_means_specific_frame(self):
        """frame_index >= 0 should mean specific frame."""
        region = ReviewRegion.create_ocr_region(
            x=10, y=10, w=100, h=50,
            frame_index=0
        )
        
        assert region.frame_index == 0
        assert not region.applies_to_all_frames()


# ═══════════════════════════════════════════════════════════════════════════════
# REVIEWREGION TOGGLE LOGIC TESTS
# ═══════════════════════════════════════════════════════════════════════════════

class TestReviewRegionToggle:
    """Tests for ReviewRegion action toggling."""
    
    def test_toggle_from_default_mask_to_unmask(self):
        """Toggling default MASK should set reviewer_action to UNMASK."""
        region = ReviewRegion.create_ocr_region(x=10, y=10, w=100, h=50)
        assert region.get_effective_action() == RegionAction.MASK
        
        region.toggle()
        
        assert region.reviewer_action == RegionAction.UNMASK
        assert region.get_effective_action() == RegionAction.UNMASK
    
    def test_toggle_from_unmask_back_to_mask(self):
        """Toggling UNMASK should set reviewer_action to MASK."""
        region = ReviewRegion.create_ocr_region(x=10, y=10, w=100, h=50)
        region.toggle()  # Now UNMASK
        
        region.toggle()  # Back to MASK
        
        assert region.reviewer_action == RegionAction.MASK
        assert region.get_effective_action() == RegionAction.MASK
    
    def test_effective_action_uses_reviewer_action_if_set(self):
        """get_effective_action should prefer reviewer_action over default."""
        region = ReviewRegion.create_ocr_region(x=10, y=10, w=100, h=50)
        assert region.get_effective_action() == RegionAction.MASK  # Default
        
        region.reviewer_action = RegionAction.UNMASK
        assert region.get_effective_action() == RegionAction.UNMASK
    
    def test_effective_action_uses_default_if_no_reviewer_action(self):
        """get_effective_action should use default_action if reviewer_action is None."""
        region = ReviewRegion.create_ocr_region(x=10, y=10, w=100, h=50)
        region.reviewer_action = None
        
        assert region.get_effective_action() == region.default_action
    
    def test_set_mask_explicitly(self):
        """set_mask should set reviewer_action to MASK."""
        region = ReviewRegion.create_ocr_region(x=10, y=10, w=100, h=50)
        region.set_mask()
        
        assert region.reviewer_action == RegionAction.MASK
    
    def test_set_unmask_explicitly(self):
        """set_unmask should set reviewer_action to UNMASK."""
        region = ReviewRegion.create_ocr_region(x=10, y=10, w=100, h=50)
        region.set_unmask()
        
        assert region.reviewer_action == RegionAction.UNMASK
    
    def test_reset_clears_reviewer_action(self):
        """reset should clear reviewer_action back to None."""
        region = ReviewRegion.create_ocr_region(x=10, y=10, w=100, h=50)
        region.toggle()  # Set reviewer_action
        assert region.reviewer_action is not None
        
        region.reset()
        
        assert region.reviewer_action is None
    
    def test_is_modified_returns_true_if_reviewer_action_set(self):
        """is_modified should return True if reviewer changed the action."""
        region = ReviewRegion.create_ocr_region(x=10, y=10, w=100, h=50)
        assert not region.is_modified()
        
        region.toggle()
        assert region.is_modified()


# ═══════════════════════════════════════════════════════════════════════════════
# MANUAL REGION DELETION TESTS
# ═══════════════════════════════════════════════════════════════════════════════

class TestManualRegionDeletion:
    """Tests for manual region deletion."""
    
    def test_mark_deleted_sets_reviewer_action(self):
        """mark_deleted should set reviewer_action to DELETED."""
        region = ReviewRegion.create_manual_region(x=10, y=10, w=100, h=50)
        region.mark_deleted()
        
        assert region.reviewer_action == RegionAction.DELETED
    
    def test_is_deleted_returns_true_after_mark_deleted(self):
        """is_deleted should return True after mark_deleted."""
        region = ReviewRegion.create_manual_region(x=10, y=10, w=100, h=50)
        assert not region.is_deleted()
        
        region.mark_deleted()
        
        assert region.is_deleted()
    
    def test_ocr_region_cannot_be_deleted(self):
        """OCR regions should not be deletable."""
        region = ReviewRegion.create_ocr_region(x=10, y=10, w=100, h=50)
        
        with pytest.raises(ValueError, match="OCR regions cannot be deleted"):
            region.mark_deleted()
    
    def test_can_delete_returns_true_for_manual(self):
        """can_delete should return True for manual regions."""
        region = ReviewRegion.create_manual_region(x=10, y=10, w=100, h=50)
        assert region.can_delete()
    
    def test_can_delete_returns_false_for_ocr(self):
        """can_delete should return False for OCR regions."""
        region = ReviewRegion.create_ocr_region(x=10, y=10, w=100, h=50)
        assert not region.can_delete()


# ═══════════════════════════════════════════════════════════════════════════════
# REVIEWSESSION CREATION TESTS
# ═══════════════════════════════════════════════════════════════════════════════

class TestReviewSessionCreation:
    """Tests for ReviewSession lifecycle."""
    
    def test_create_session_with_sop_uid(self):
        """Session should be created with SOP Instance UID."""
        session = ReviewSession.create(sop_instance_uid="1.2.3.4.5")
        
        assert session.sop_instance_uid == "1.2.3.4.5"
        assert session.session_id is not None
        assert len(session.regions) == 0
        assert not session.review_started
        assert not session.review_accepted
        assert session.created_at is not None
    
    def test_add_ocr_region(self):
        """add_ocr_region should append to regions list."""
        session = ReviewSession.create(sop_instance_uid="1.2.3.4.5")
        session.add_ocr_region(x=50, y=100, w=400, h=80)
        
        assert len(session.regions) == 1
        assert session.regions[0].source == RegionSource.OCR
    
    def test_add_manual_region(self):
        """add_manual_region should append to regions list."""
        session = ReviewSession.create(sop_instance_uid="1.2.3.4.5")
        session.add_manual_region(x=200, y=300, w=150, h=40)
        
        assert len(session.regions) == 1
        assert session.regions[0].source == RegionSource.MANUAL


# ═══════════════════════════════════════════════════════════════════════════════
# ACCEPT GATING TESTS
# ═══════════════════════════════════════════════════════════════════════════════

class TestAcceptGating:
    """Tests for Accept & Continue gating logic."""
    
    def test_can_accept_requires_review_started(self):
        """Cannot accept if review has not started."""
        session = ReviewSession.create(sop_instance_uid="1.2.3.4.5")
        session.add_ocr_region(x=50, y=100, w=400, h=80)
        
        assert not session.can_accept()
    
    def test_can_accept_after_review_started(self):
        """Can accept after review_started is True."""
        session = ReviewSession.create(sop_instance_uid="1.2.3.4.5")
        session.add_ocr_region(x=50, y=100, w=400, h=80)
        session.start_review()
        
        assert session.can_accept()
    
    def test_start_review_sets_flag(self):
        """start_review should set review_started to True."""
        session = ReviewSession.create(sop_instance_uid="1.2.3.4.5")
        assert not session.review_started
        
        session.start_review()
        
        assert session.review_started
    
    def test_accept_sets_flag(self):
        """accept should set review_accepted to True."""
        session = ReviewSession.create(sop_instance_uid="1.2.3.4.5")
        session.start_review()
        
        session.accept()
        
        assert session.review_accepted
    
    def test_accept_raises_if_not_started(self):
        """accept should raise if review not started."""
        session = ReviewSession.create(sop_instance_uid="1.2.3.4.5")
        
        with pytest.raises(RuntimeError, match="not started"):
            session.accept()
    
    def test_accept_with_no_regions_still_works(self):
        """Accept should work even with zero regions (edge case)."""
        session = ReviewSession.create(sop_instance_uid="1.2.3.4.5")
        session.start_review()
        
        session.accept()
        
        assert session.review_accepted
    
    def test_accept_with_no_modifications_still_works(self):
        """Accept should work even if reviewer made no changes."""
        session = ReviewSession.create(sop_instance_uid="1.2.3.4.5")
        session.add_ocr_region(x=50, y=100, w=400, h=80)
        session.start_review()
        # No toggles or changes made
        
        session.accept()
        
        assert session.review_accepted


# ═══════════════════════════════════════════════════════════════════════════════
# SESSION SEALING TESTS
# ═══════════════════════════════════════════════════════════════════════════════

class TestSessionSealing:
    """Tests for session sealing after accept."""
    
    def test_session_is_sealed_after_accept(self):
        """Session should be sealed after accept."""
        session = ReviewSession.create(sop_instance_uid="1.2.3.4.5")
        session.start_review()
        session.accept()
        
        assert session.is_sealed()
    
    def test_sealed_session_cannot_add_regions(self):
        """Sealed session should reject new regions."""
        session = ReviewSession.create(sop_instance_uid="1.2.3.4.5")
        session.start_review()
        session.accept()
        
        with pytest.raises(RuntimeError, match="sealed"):
            session.add_ocr_region(x=10, y=10, w=100, h=50)
    
    def test_sealed_session_cannot_add_manual_regions(self):
        """Sealed session should reject manual regions."""
        session = ReviewSession.create(sop_instance_uid="1.2.3.4.5")
        session.start_review()
        session.accept()
        
        with pytest.raises(RuntimeError, match="sealed"):
            session.add_manual_region(x=10, y=10, w=100, h=50)
    
    def test_sealed_session_cannot_toggle_regions(self):
        """Sealed session should prevent region toggles."""
        session = ReviewSession.create(sop_instance_uid="1.2.3.4.5")
        session.add_ocr_region(x=50, y=100, w=400, h=80)
        session.start_review()
        session.accept()
        
        with pytest.raises(RuntimeError, match="sealed"):
            session.toggle_region(session.regions[0].region_id)
    
    def test_sealed_session_allows_read_operations(self):
        """Sealed session should allow reading regions."""
        session = ReviewSession.create(sop_instance_uid="1.2.3.4.5")
        session.add_ocr_region(x=50, y=100, w=400, h=80)
        session.start_review()
        session.accept()
        
        # These should not raise
        regions = session.get_regions()
        assert len(regions) == 1
        
        masked = session.get_masked_regions()
        assert len(masked) == 1
    
    def test_cannot_accept_twice(self):
        """Accepting twice should raise."""
        session = ReviewSession.create(sop_instance_uid="1.2.3.4.5")
        session.start_review()
        session.accept()
        
        with pytest.raises(RuntimeError, match="already accepted"):
            session.accept()


# ═══════════════════════════════════════════════════════════════════════════════
# BULK OPERATIONS TESTS
# ═══════════════════════════════════════════════════════════════════════════════

class TestBulkOperations:
    """Tests for bulk region operations."""
    
    def test_mask_all_detected(self):
        """mask_all_detected should set all OCR regions to MASK."""
        session = ReviewSession.create(sop_instance_uid="1.2.3.4.5")
        session.add_ocr_region(x=50, y=100, w=400, h=80)
        session.add_ocr_region(x=50, y=200, w=300, h=60)
        session.add_manual_region(x=200, y=300, w=150, h=40)
        
        # Toggle one to UNMASK first
        session.regions[0].toggle()
        session.regions[1].toggle()
        
        session.mask_all_detected()
        
        # OCR regions should be MASK
        assert session.regions[0].get_effective_action() == RegionAction.MASK
        assert session.regions[1].get_effective_action() == RegionAction.MASK
        # Manual region unchanged
        assert session.regions[2].get_effective_action() == RegionAction.MASK
    
    def test_unmask_all(self):
        """unmask_all should set all regions to UNMASK."""
        session = ReviewSession.create(sop_instance_uid="1.2.3.4.5")
        session.add_ocr_region(x=50, y=100, w=400, h=80)
        session.add_manual_region(x=200, y=300, w=150, h=40)
        
        session.unmask_all()
        
        assert session.regions[0].get_effective_action() == RegionAction.UNMASK
        assert session.regions[1].get_effective_action() == RegionAction.UNMASK
    
    def test_reset_to_defaults(self):
        """reset_to_defaults should reset OCR and delete manual regions."""
        session = ReviewSession.create(sop_instance_uid="1.2.3.4.5")
        session.add_ocr_region(x=50, y=100, w=400, h=80)
        session.add_manual_region(x=200, y=300, w=150, h=40)
        
        # Modify OCR region
        session.regions[0].toggle()
        
        session.reset_to_defaults()
        
        # OCR region reset
        assert session.regions[0].reviewer_action is None
        # Manual region marked deleted
        assert session.regions[1].is_deleted()
    
    def test_clear_manual_regions(self):
        """clear_manual_regions should mark all manual regions as deleted."""
        session = ReviewSession.create(sop_instance_uid="1.2.3.4.5")
        session.add_ocr_region(x=50, y=100, w=400, h=80)
        session.add_manual_region(x=200, y=300, w=150, h=40)
        session.add_manual_region(x=300, y=400, w=100, h=30)
        
        session.clear_manual_regions()
        
        # OCR unchanged
        assert not session.regions[0].is_deleted()
        # Manual regions deleted
        assert session.regions[1].is_deleted()
        assert session.regions[2].is_deleted()


# ═══════════════════════════════════════════════════════════════════════════════
# SUMMARY / STATISTICS TESTS
# ═══════════════════════════════════════════════════════════════════════════════

class TestSessionStatistics:
    """Tests for session statistics and summaries."""
    
    def test_get_masked_regions(self):
        """get_masked_regions should return only MASK regions."""
        session = ReviewSession.create(sop_instance_uid="1.2.3.4.5")
        session.add_ocr_region(x=50, y=100, w=400, h=80)  # MASK
        session.add_ocr_region(x=50, y=200, w=300, h=60)  # Will toggle
        session.add_manual_region(x=200, y=300, w=150, h=40)  # MASK
        
        session.regions[1].toggle()  # Now UNMASK
        
        masked = session.get_masked_regions()
        
        assert len(masked) == 2
        assert all(r.get_effective_action() == RegionAction.MASK for r in masked)
    
    def test_get_unmasked_regions(self):
        """get_unmasked_regions should return only UNMASK regions."""
        session = ReviewSession.create(sop_instance_uid="1.2.3.4.5")
        session.add_ocr_region(x=50, y=100, w=400, h=80)
        session.add_ocr_region(x=50, y=200, w=300, h=60)
        
        session.regions[1].toggle()  # Now UNMASK
        
        unmasked = session.get_unmasked_regions()
        
        assert len(unmasked) == 1
        assert unmasked[0].get_effective_action() == RegionAction.UNMASK
    
    def test_get_active_regions_excludes_deleted(self):
        """get_active_regions should exclude deleted regions."""
        session = ReviewSession.create(sop_instance_uid="1.2.3.4.5")
        session.add_ocr_region(x=50, y=100, w=400, h=80)
        session.add_manual_region(x=200, y=300, w=150, h=40)
        
        session.regions[1].mark_deleted()
        
        active = session.get_active_regions()
        
        assert len(active) == 1
        assert active[0].source == RegionSource.OCR
    
    def test_get_summary(self):
        """get_summary should return correct counts."""
        session = ReviewSession.create(sop_instance_uid="1.2.3.4.5")
        session.add_ocr_region(x=50, y=100, w=400, h=80)
        session.add_ocr_region(x=50, y=200, w=300, h=60)
        session.add_manual_region(x=200, y=300, w=150, h=40)
        
        session.regions[1].toggle()  # UNMASK
        
        summary = session.get_summary()
        
        assert summary["total_regions"] == 3
        assert summary["ocr_regions"] == 2
        assert summary["manual_regions"] == 1
        assert summary["will_mask"] == 2
        assert summary["will_unmask"] == 1
