"""
Tests for ReviewSession accept gating (PR 5)
============================================
Sprint 2: Accept Gating + Export Integration

Tests the accept() method, can_accept() logic, and integration
with DecisionTraceCollector via record_region_decisions().
"""

import pytest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from review_session import (
    ReviewSession, 
    ReviewRegion, 
    RegionSource, 
    RegionAction
)
from decision_trace import (
    DecisionTraceCollector,
    record_region_decisions,
    ActionType,
    ReasonCode
)


class TestAcceptGating:
    """Tests for review accept gating logic."""
    
    def test_new_session_cannot_accept(self):
        """New session cannot be accepted (review not started)."""
        session = ReviewSession.create(sop_instance_uid="1.2.3.4.5")
        assert session.can_accept() == False
        assert session.review_accepted == False
    
    def test_started_session_can_accept(self):
        """Started session can be accepted."""
        session = ReviewSession.create(sop_instance_uid="1.2.3.4.5")
        session.start_review()
        assert session.can_accept() == True
    
    def test_accept_seals_session(self):
        """Accepting seals the session."""
        session = ReviewSession.create(sop_instance_uid="1.2.3.4.5")
        session.start_review()
        session.accept()
        
        assert session.review_accepted == True
        assert session.is_sealed() == True
    
    def test_cannot_accept_twice(self):
        """Cannot accept a session that's already accepted."""
        session = ReviewSession.create(sop_instance_uid="1.2.3.4.5")
        session.start_review()
        session.accept()
        
        with pytest.raises(RuntimeError, match="already accepted"):
            session.accept()
    
    def test_cannot_accept_without_starting(self):
        """Cannot accept a session that hasn't been started."""
        session = ReviewSession.create(sop_instance_uid="1.2.3.4.5")
        
        with pytest.raises(RuntimeError, match="not started"):
            session.accept()
    
    def test_sealed_session_cannot_be_modified(self):
        """Sealed session rejects modifications."""
        session = ReviewSession.create(sop_instance_uid="1.2.3.4.5")
        session.start_review()
        session.add_ocr_region(10, 20, 100, 50)
        session.accept()
        
        # Should raise on any modification
        with pytest.raises(RuntimeError, match="sealed"):
            session.add_ocr_region(30, 40, 100, 50)
        
        with pytest.raises(RuntimeError, match="sealed"):
            session.add_manual_region(50, 60, 100, 50)


class TestDecisionTraceIntegration:
    """Tests for record_region_decisions() integration."""
    
    def test_record_regions_creates_decisions(self):
        """Recording regions creates decision records."""
        session = ReviewSession.create(sop_instance_uid="1.2.3.4.5")
        session.start_review()
        
        # Add regions
        session.add_ocr_region(10, 20, 100, 50)  # Will be MASK by default
        session.add_manual_region(150, 200, 80, 40)  # Will be MASK by default
        
        session.accept()
        
        # Create collector and record
        collector = DecisionTraceCollector()
        active_regions = session.get_active_regions()
        
        count = record_region_decisions(
            collector=collector,
            regions=active_regions,
            sop_instance_uid=session.sop_instance_uid
        )
        
        assert count == 2  # Both regions recorded
        assert collector.count() == 2
    
    def test_record_regions_respects_reviewer_override(self):
        """Overrides are recorded with appropriate reason codes."""
        session = ReviewSession.create(sop_instance_uid="1.2.3.4.5")
        session.start_review()
        
        # Add and override an OCR region
        region = session.add_ocr_region(10, 20, 100, 50)
        session.toggle_region(region.region_id)  # Toggle to UNMASK
        
        session.accept()
        
        # Create collector and record
        collector = DecisionTraceCollector()
        active_regions = session.get_active_regions()
        
        record_region_decisions(
            collector=collector,
            regions=active_regions,
            sop_instance_uid=session.sop_instance_uid
        )
        
        # Check decision
        decisions = collector.get_decisions()
        assert len(decisions) == 1
        assert decisions[0].action_type == ActionType.RETAINED
        assert decisions[0].reason_code == ReasonCode.USER_OVERRIDE_RETAIN
    
    def test_record_regions_skips_deleted(self):
        """Deleted regions are not recorded."""
        session = ReviewSession.create(sop_instance_uid="1.2.3.4.5")
        session.start_review()
        
        # Add regions
        session.add_ocr_region(10, 20, 100, 50)  # Keep
        manual = session.add_manual_region(150, 200, 80, 40)  # Will delete
        session.delete_region(manual.region_id)
        
        session.accept()
        
        # Create collector and record
        collector = DecisionTraceCollector()
        active_regions = session.get_active_regions()  # Already filters deleted
        
        count = record_region_decisions(
            collector=collector,
            regions=active_regions,
            sop_instance_uid=session.sop_instance_uid
        )
        
        assert count == 1  # Only OCR region recorded
    
    def test_collector_locks_after_record(self):
        """Collector can be locked after recording."""
        session = ReviewSession.create(sop_instance_uid="1.2.3.4.5")
        session.start_review()
        session.add_ocr_region(10, 20, 100, 50)
        session.accept()
        
        collector = DecisionTraceCollector()
        active_regions = session.get_active_regions()
        
        record_region_decisions(
            collector=collector,
            regions=active_regions,
            sop_instance_uid=session.sop_instance_uid
        )
        
        # Lock the collector
        collector.lock()
        assert collector.is_locked() == True
        
        # Cannot add after lock
        with pytest.raises(RuntimeError, match="locked"):
            collector.add(
                scope_level="INSTANCE",
                action_type="MASKED",
                target_type="PIXEL_REGION",
                target_name="Test",
                reason_code="TEST",
                rule_source="TEST"
            )


class TestSummaryStatistics:
    """Tests for get_summary() used in PDF reports."""
    
    def test_summary_counts_regions(self):
        """Summary correctly counts regions by type and action."""
        session = ReviewSession.create(sop_instance_uid="1.2.3.4.5")
        session.start_review()
        
        # Add OCR regions
        ocr1 = session.add_ocr_region(10, 20, 100, 50)  # Default MASK
        ocr2 = session.add_ocr_region(120, 20, 100, 50)  # Will toggle to UNMASK
        session.toggle_region(ocr2.region_id)
        
        # Add manual region
        session.add_manual_region(10, 200, 80, 40)  # Default MASK
        
        summary = session.get_summary()
        
        assert summary['ocr_regions'] == 2
        assert summary['manual_regions'] == 1
        assert summary['will_mask'] == 2  # 1 OCR + 1 manual
        assert summary['will_unmask'] == 1  # 1 OCR override
        assert summary['total_regions'] == 3
    
    def test_summary_excludes_deleted(self):
        """Summary excludes deleted regions from counts."""
        session = ReviewSession.create(sop_instance_uid="1.2.3.4.5")
        session.start_review()
        
        # Add and delete a manual region
        manual = session.add_manual_region(10, 200, 80, 40)
        session.delete_region(manual.region_id)
        
        # Add OCR region
        session.add_ocr_region(10, 20, 100, 50)
        
        summary = session.get_summary()
        
        # Deleted manual region should not be in active counts
        assert summary['manual_regions'] == 0
        assert summary['ocr_regions'] == 1
        # But total_regions includes all (even deleted) - this is intentional
        # for audit trail (shows 1 region was added then deleted)
        # Actually let's verify this behavior
        assert summary['total_regions'] == 2  # Shows history


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
