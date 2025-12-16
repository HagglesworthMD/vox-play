#!/usr/bin/env python3
"""
Unit Tests for Phase 4 Detection Improvements

Tests for:
- detect_text_box_from_array detection_strength population
- _map_confidence_to_strength threshold mappings
- _aggregate_confidence aggregation logic
- OCR failure explicit uncertainty surfacing

Author: VoxelMask Engineering
Phase: 4 (OCR Detection Hardening)
Post: v0.4.3-phase4-governance-freeze
"""

import pytest
import numpy as np
from unittest.mock import MagicMock, patch


# ═══════════════════════════════════════════════════════════════════════════════
# UNIT TESTS: Confidence Mapping Functions
# ═══════════════════════════════════════════════════════════════════════════════

class TestMapConfidenceToStrength:
    """Tests for _map_confidence_to_strength threshold mappings."""
    
    def test_high_confidence_threshold(self):
        """Confidence >= 0.80 should map to HIGH."""
        from run_on_dicom import _map_confidence_to_strength
        
        assert _map_confidence_to_strength(0.80) == "HIGH"
        assert _map_confidence_to_strength(0.85) == "HIGH"
        assert _map_confidence_to_strength(0.99) == "HIGH"
        assert _map_confidence_to_strength(1.0) == "HIGH"
    
    def test_medium_confidence_threshold(self):
        """Confidence 0.50-0.79 should map to MEDIUM."""
        from run_on_dicom import _map_confidence_to_strength
        
        assert _map_confidence_to_strength(0.50) == "MEDIUM"
        assert _map_confidence_to_strength(0.65) == "MEDIUM"
        assert _map_confidence_to_strength(0.79) == "MEDIUM"
    
    def test_low_confidence_threshold(self):
        """Confidence < 0.50 should map to LOW."""
        from run_on_dicom import _map_confidence_to_strength
        
        assert _map_confidence_to_strength(0.0) == "LOW"
        assert _map_confidence_to_strength(0.25) == "LOW"
        assert _map_confidence_to_strength(0.49) == "LOW"
    
    def test_boundary_at_0_80(self):
        """Test the exact boundary at 0.80."""
        from run_on_dicom import _map_confidence_to_strength
        
        assert _map_confidence_to_strength(0.799) == "MEDIUM"
        assert _map_confidence_to_strength(0.80) == "HIGH"
    
    def test_boundary_at_0_50(self):
        """Test the exact boundary at 0.50."""
        from run_on_dicom import _map_confidence_to_strength
        
        assert _map_confidence_to_strength(0.499) == "LOW"
        assert _map_confidence_to_strength(0.50) == "MEDIUM"


class TestAggregateConfidence:
    """Tests for _aggregate_confidence aggregation logic."""
    
    def test_empty_scores_returns_zero(self):
        """Empty score list should return 0.0."""
        from run_on_dicom import _aggregate_confidence
        
        assert _aggregate_confidence([]) == 0.0
    
    def test_single_score_returns_itself(self):
        """Single score should return itself."""
        from run_on_dicom import _aggregate_confidence
        
        assert _aggregate_confidence([0.75]) == 0.75
    
    def test_multiple_scores_returns_minimum(self):
        """Multiple scores should return minimum (conservative)."""
        from run_on_dicom import _aggregate_confidence
        
        assert _aggregate_confidence([0.9, 0.8, 0.7]) == 0.7
        assert _aggregate_confidence([0.5, 0.95, 0.85]) == 0.5
    
    def test_all_high_scores(self):
        """All high scores should return lowest high score."""
        from run_on_dicom import _aggregate_confidence
        
        assert _aggregate_confidence([0.95, 0.92, 0.88]) == 0.88
    
    def test_mixed_with_low_outlier(self):
        """Low outlier should dominate (pessimistic)."""
        from run_on_dicom import _aggregate_confidence
        
        # Even one low score should pull the aggregate down
        assert _aggregate_confidence([0.95, 0.92, 0.30]) == 0.30


# ═══════════════════════════════════════════════════════════════════════════════
# UNIT TESTS: DetectionResult Dataclass
# ═══════════════════════════════════════════════════════════════════════════════

class TestDetectionResult:
    """Tests for DetectionResult dataclass structure."""
    
    def test_detection_result_creation(self):
        """DetectionResult should be constructable with all fields."""
        from run_on_dicom import DetectionResult
        
        result = DetectionResult(
            static_box=(10, 20, 100, 50),
            all_detected_boxes=[(10, 20, 100, 50), (200, 300, 80, 40)],
            detection_strength="HIGH",
            ocr_failure=False,
            confidence_scores=[0.95, 0.88],
        )
        
        assert result.static_box == (10, 20, 100, 50)
        assert len(result.all_detected_boxes) == 2
        assert result.detection_strength == "HIGH"
        assert result.ocr_failure is False
        assert result.confidence_scores == [0.95, 0.88]
    
    def test_detection_result_with_none_strength(self):
        """DetectionResult should accept None for detection_strength (OCR failure)."""
        from run_on_dicom import DetectionResult
        
        result = DetectionResult(
            static_box=None,
            all_detected_boxes=[],
            detection_strength=None,  # OCR failed
            ocr_failure=True,
            confidence_scores=[],
        )
        
        assert result.detection_strength is None
        assert result.ocr_failure is True


# ═══════════════════════════════════════════════════════════════════════════════
# UNIT TESTS: detect_text_box_from_array with mocked OCR
# ═══════════════════════════════════════════════════════════════════════════════

class TestDetectTextBoxFromArray:
    """Tests for detect_text_box_from_array with Phase 4 enhancements."""
    
    @pytest.fixture
    def dummy_array(self):
        """Create a minimal 4D array for testing."""
        # Shape: (2 frames, 100 height, 200 width, 3 channels)
        return np.zeros((2, 100, 200, 3), dtype=np.uint8)
    
    @pytest.fixture
    def mock_corrector(self):
        """Create a mocked ClinicalCorrector."""
        corrector = MagicMock()
        corrector._preprocess_for_ocr = MagicMock(side_effect=lambda x: x)
        corrector._boxes_overlap = MagicMock(return_value=True)
        return corrector
    
    def test_ocr_success_with_high_confidence(self, dummy_array, mock_corrector):
        """OCR success with high confidence should return HIGH detection_strength."""
        from run_on_dicom import detect_text_box_from_array
        
        # Mock OCR to return high confidence results
        mock_corrector.ocr.predict.return_value = [[
            [[[10, 20], [110, 20], [110, 70], [10, 70]], ("TEXT", 0.95)]
        ]]
        
        result = detect_text_box_from_array(mock_corrector, dummy_array)
        
        assert result.detection_strength == "HIGH"
        assert result.ocr_failure is False
        assert len(result.confidence_scores) > 0
    
    def test_ocr_success_with_medium_confidence(self, dummy_array, mock_corrector):
        """OCR success with medium confidence should return MEDIUM detection_strength."""
        from run_on_dicom import detect_text_box_from_array
        
        # Mock OCR to return medium confidence results
        mock_corrector.ocr.predict.return_value = [[
            [[[10, 20], [110, 20], [110, 70], [10, 70]], ("TEXT", 0.65)]
        ]]
        
        result = detect_text_box_from_array(mock_corrector, dummy_array)
        
        assert result.detection_strength == "MEDIUM"
        assert result.ocr_failure is False
    
    def test_ocr_success_with_low_confidence(self, dummy_array, mock_corrector):
        """OCR success with low confidence should return LOW detection_strength."""
        from run_on_dicom import detect_text_box_from_array
        
        # Mock OCR to return low confidence results
        mock_corrector.ocr.predict.return_value = [[
            [[[10, 20], [110, 20], [110, 70], [10, 70]], ("TEXT", 0.35)]
        ]]
        
        result = detect_text_box_from_array(mock_corrector, dummy_array)
        
        assert result.detection_strength == "LOW"
        assert result.ocr_failure is False
    
    def test_ocr_failure_returns_none_strength(self, dummy_array, mock_corrector):
        """OCR exception should return detection_strength=None (explicit uncertainty)."""
        from run_on_dicom import detect_text_box_from_array
        
        # Mock OCR to throw exception
        mock_corrector.ocr.predict.side_effect = RuntimeError("OCR engine crashed")
        
        result = detect_text_box_from_array(mock_corrector, dummy_array)
        
        assert result.detection_strength is None  # Explicit uncertainty
        assert result.ocr_failure is True
        assert result.static_box is None
    
    def test_no_detection_returns_low_strength(self, dummy_array, mock_corrector):
        """OCR success with no detections should return LOW detection_strength."""
        from run_on_dicom import detect_text_box_from_array
        
        # Mock OCR to return empty results
        mock_corrector.ocr.predict.return_value = [[]]
        
        result = detect_text_box_from_array(mock_corrector, dummy_array)
        
        assert result.detection_strength == "LOW"
        assert result.ocr_failure is False
        assert result.static_box is None
        assert len(result.all_detected_boxes) == 0
    
    def test_ocr_without_confidence_scores_defaults_to_medium(self, dummy_array, mock_corrector):
        """OCR success without confidence scores should default to MEDIUM (conservative)."""
        from run_on_dicom import detect_text_box_from_array
        
        # Mock OCR to return dict format without det_scores
        mock_corrector.ocr.predict.return_value = [{
            'det_boxes': [[[10, 20], [110, 20], [110, 70], [10, 70]]]
            # Note: no 'det_scores' key
        }]
        
        result = detect_text_box_from_array(mock_corrector, dummy_array)
        
        assert result.detection_strength == "MEDIUM"
        assert result.ocr_failure is False
        assert len(result.confidence_scores) == 0  # No scores available
    
    def test_mixed_confidence_uses_minimum(self, dummy_array, mock_corrector):
        """Multiple detections should use minimum confidence (pessimistic)."""
        from run_on_dicom import detect_text_box_from_array
        
        # Mock OCR to return multiple results with varying confidence
        mock_corrector.ocr.predict.return_value = [[
            [[[10, 20], [110, 20], [110, 70], [10, 70]], ("HIGH", 0.95)],
            [[[120, 20], [220, 20], [220, 70], [120, 70]], ("LOW", 0.35)],  # This should dominate
        ]]
        
        result = detect_text_box_from_array(mock_corrector, dummy_array)
        
        # Minimum of [0.95, 0.35] = 0.35 → LOW
        assert result.detection_strength == "LOW"
        assert 0.35 in result.confidence_scores


# ═══════════════════════════════════════════════════════════════════════════════
# INTEGRATION SANITY CHECK
# ═══════════════════════════════════════════════════════════════════════════════

class TestPhase4GovernanceCompliance:
    """Verify Phase 4 changes comply with governance constraints."""
    
    def test_detection_result_has_no_text_content(self):
        """DetectionResult must not contain OCR text (PHI-free by design)."""
        from run_on_dicom import DetectionResult
        import inspect
        
        # Get all field names from the dataclass
        fields = [f.name for f in DetectionResult.__dataclass_fields__.values()]
        
        # Ensure no field stores text content
        text_field_names = ['text', 'ocr_text', 'content', 'recognized_text']
        for forbidden in text_field_names:
            assert forbidden not in fields, f"DetectionResult must not have '{forbidden}' field"
    
    def test_detection_strength_values_are_documented(self):
        """detection_strength values should match documented thresholds."""
        from run_on_dicom import _map_confidence_to_strength
        
        # These are the only valid outputs per Phase 4 documentation
        valid_outputs = {"LOW", "MEDIUM", "HIGH"}
        
        # Test across the full range
        for conf in [0.0, 0.25, 0.49, 0.50, 0.65, 0.79, 0.80, 0.95, 1.0]:
            result = _map_confidence_to_strength(conf)
            assert result in valid_outputs, f"Unexpected strength '{result}' for confidence {conf}"


# ═══════════════════════════════════════════════════════════════════════════════
# PHASE 4: DETECTION → REVIEW SESSION BRIDGE TESTS
# ═══════════════════════════════════════════════════════════════════════════════

class TestPopulateRegionsFromDetection:
    """Tests for populate_regions_from_detection bridge function."""
    
    def test_bridges_detection_strength_to_regions(self):
        """detection_strength should flow from DetectionResult to ReviewRegion."""
        from run_on_dicom import DetectionResult
        from review_session import ReviewSession, populate_regions_from_detection
        
        # Create detection result with HIGH strength
        detection_result = DetectionResult(
            static_box=(10, 20, 100, 50),
            all_detected_boxes=[(10, 20, 100, 50)],
            detection_strength="HIGH",
            ocr_failure=False,
            confidence_scores=[0.95],
        )
        
        session = ReviewSession.create(sop_instance_uid="1.2.3.test")
        count = populate_regions_from_detection(session, detection_result)
        
        assert count == 1
        assert len(session.get_regions()) == 1
        region = session.get_regions()[0]
        assert region.detection_strength == "HIGH"
    
    def test_ocr_failure_surfaces_as_none_strength(self):
        """OCR failure should result in detection_strength=None."""
        from run_on_dicom import DetectionResult
        from review_session import ReviewSession, populate_regions_from_detection
        
        # Create detection result with OCR failure
        detection_result = DetectionResult(
            static_box=None,
            all_detected_boxes=[(10, 20, 100, 50)],  # Still have box from partial detection
            detection_strength=None,  # OCR failed
            ocr_failure=True,
            confidence_scores=[],
        )
        
        session = ReviewSession.create(sop_instance_uid="1.2.3.test")
        count = populate_regions_from_detection(session, detection_result)
        
        assert count == 1
        region = session.get_regions()[0]
        assert region.detection_strength is None  # Explicit uncertainty
    
    def test_multiple_boxes_all_get_same_strength(self):
        """All boxes from single detection should share the same strength."""
        from run_on_dicom import DetectionResult
        from review_session import ReviewSession, populate_regions_from_detection
        
        detection_result = DetectionResult(
            static_box=(10, 20, 100, 50),
            all_detected_boxes=[
                (10, 20, 100, 50),
                (200, 300, 80, 40),
                (400, 500, 60, 30),
            ],
            detection_strength="MEDIUM",
            ocr_failure=False,
            confidence_scores=[0.65, 0.70, 0.75],
        )
        
        session = ReviewSession.create(sop_instance_uid="1.2.3.test")
        count = populate_regions_from_detection(session, detection_result)
        
        assert count == 3
        for region in session.get_regions():
            assert region.detection_strength == "MEDIUM"
    
    def test_empty_detection_adds_no_regions(self):
        """Empty detection should add no regions."""
        from run_on_dicom import DetectionResult
        from review_session import ReviewSession, populate_regions_from_detection
        
        detection_result = DetectionResult(
            static_box=None,
            all_detected_boxes=[],
            detection_strength="LOW",
            ocr_failure=False,
            confidence_scores=[],
        )
        
        session = ReviewSession.create(sop_instance_uid="1.2.3.test")
        count = populate_regions_from_detection(session, detection_result)
        
        assert count == 0
        assert len(session.get_regions()) == 0
    
    def test_sealed_session_rejects_new_regions(self):
        """Sealed session should not accept new regions."""
        from run_on_dicom import DetectionResult
        from review_session import ReviewSession, populate_regions_from_detection
        
        detection_result = DetectionResult(
            static_box=(10, 20, 100, 50),
            all_detected_boxes=[(10, 20, 100, 50)],
            detection_strength="HIGH",
            ocr_failure=False,
            confidence_scores=[0.95],
        )
        
        session = ReviewSession.create(sop_instance_uid="1.2.3.test")
        session.start_review()
        session.accept()  # Seal the session
        
        count = populate_regions_from_detection(session, detection_result)
        
        assert count == 0  # Should not add due to sealed session
        assert len(session.get_regions()) == 0
    
    def test_frame_index_passed_through(self):
        """frame_index should be passed to created regions."""
        from run_on_dicom import DetectionResult
        from review_session import ReviewSession, populate_regions_from_detection
        
        detection_result = DetectionResult(
            static_box=(10, 20, 100, 50),
            all_detected_boxes=[(10, 20, 100, 50)],
            detection_strength="HIGH",
            ocr_failure=False,
            confidence_scores=[0.95],
        )
        
        session = ReviewSession.create(sop_instance_uid="1.2.3.test")
        populate_regions_from_detection(session, detection_result, frame_index=5)
        
        region = session.get_regions()[0]
        assert region.frame_index == 5


# ═══════════════════════════════════════════════════════════════════════════════
# PHASE 4: AUDIT LOG ENRICHMENT TESTS (Option C)
# ═══════════════════════════════════════════════════════════════════════════════

class TestAuditLogEnrichment:
    """Tests for Phase 4 audit log enrichment with OCR detection metadata."""
    
    def test_decision_record_includes_ocr_fields(self):
        """DecisionRecord should have OCR detection metadata fields."""
        from decision_trace import DecisionRecord
        
        record = DecisionRecord(
            scope_level="PIXEL_REGION",
            scope_uid="1.2.3",
            action_type="MASKED",
            target_type="PIXEL_REGION",
            target_name="PixelRegion[0]",
            reason_code="BURNED_IN_TEXT_DETECTED",
            rule_source="MODALITY_SAFETY_PROTOCOL",
            region_x=10,
            region_y=20,
            region_w=100,
            region_h=50,
            detection_strength="HIGH",
            ocr_failure=False,
            confidence_aggregation="min",
            ocr_engine="PaddleOCR",
        )
        
        assert record.detection_strength == "HIGH"
        assert record.ocr_failure is False
        assert record.confidence_aggregation == "min"
        assert record.ocr_engine == "PaddleOCR"
    
    def test_decision_record_defaults_to_none(self):
        """OCR fields should default to None for non-OCR decisions."""
        from decision_trace import DecisionRecord
        
        record = DecisionRecord(
            scope_level="INSTANCE",
            scope_uid="1.2.3",
            action_type="REMOVED",
            target_type="TAG",
            target_name="PatientName",
            reason_code="HIPAA_18_NAME",
            rule_source="HIPAA_SAFE_HARBOR",
        )
        
        assert record.detection_strength is None
        assert record.ocr_failure is None
        assert record.confidence_aggregation is None
        assert record.ocr_engine is None
    
    def test_ocr_failure_recorded_as_none_strength(self):
        """OCR failure should be logged as detection_strength=None."""
        from decision_trace import DecisionRecord
        
        record = DecisionRecord(
            scope_level="PIXEL_REGION",
            scope_uid="1.2.3",
            action_type="MASKED",
            target_type="PIXEL_REGION",
            target_name="PixelRegion[0]",
            reason_code="BURNED_IN_TEXT_DETECTED",
            rule_source="MODALITY_SAFETY_PROTOCOL",
            detection_strength=None,  # OCR failed
            ocr_failure=True,
            confidence_aggregation="min",
            ocr_engine="PaddleOCR",
        )
        
        assert record.detection_strength is None
        assert record.ocr_failure is True
    
    def test_collector_accepts_ocr_metadata(self):
        """DecisionTraceCollector.add() should accept OCR metadata."""
        from decision_trace import DecisionTraceCollector
        
        collector = DecisionTraceCollector()
        collector.add(
            scope_level="PIXEL_REGION",
            action_type="MASKED",
            target_type="PIXEL_REGION",
            target_name="PixelRegion[0]",
            reason_code="BURNED_IN_TEXT_DETECTED",
            rule_source="MODALITY_SAFETY_PROTOCOL",
            scope_uid="1.2.3.test",
            detection_strength="MEDIUM",
            ocr_failure=False,
            confidence_aggregation="min",
            ocr_engine="PaddleOCR",
        )
        
        decisions = collector.get_decisions()
        assert len(decisions) == 1
        assert decisions[0].detection_strength == "MEDIUM"
        assert decisions[0].ocr_failure is False
        assert decisions[0].confidence_aggregation == "min"
    
    def test_record_region_decisions_includes_ocr_metadata(self):
        """record_region_decisions should include OCR metadata for OCR regions."""
        from decision_trace import DecisionTraceCollector, record_region_decisions
        from review_session import ReviewSession, RegionSource
        
        session = ReviewSession.create(sop_instance_uid="1.2.3.test")
        session.add_ocr_region(x=50, y=100, w=400, h=80, detection_strength="HIGH")
        session.start_review()
        
        collector = DecisionTraceCollector()
        count = record_region_decisions(
            collector,
            session.get_active_regions(),
            "1.2.3.test"
        )
        
        assert count == 1
        decisions = collector.get_decisions()
        assert decisions[0].detection_strength == "HIGH"
        assert decisions[0].ocr_failure is False  # HIGH means OCR succeeded
        assert decisions[0].confidence_aggregation == "min"
        assert decisions[0].ocr_engine == "PaddleOCR"
    
    def test_record_region_decisions_ocr_failure_logged(self):
        """record_region_decisions should log OCR failure correctly."""
        from decision_trace import DecisionTraceCollector, record_region_decisions
        from review_session import ReviewSession
        
        session = ReviewSession.create(sop_instance_uid="1.2.3.test")
        # OCR failure = detection_strength is None
        session.add_ocr_region(x=50, y=100, w=400, h=80, detection_strength=None)
        session.start_review()
        
        collector = DecisionTraceCollector()
        record_region_decisions(
            collector,
            session.get_active_regions(),
            "1.2.3.test"
        )
        
        decisions = collector.get_decisions()
        assert decisions[0].detection_strength is None
        assert decisions[0].ocr_failure is True  # None strength = failure
    
    def test_manual_region_no_ocr_metadata(self):
        """Manual regions should not have OCR metadata."""
        from decision_trace import DecisionTraceCollector, record_region_decisions
        from review_session import ReviewSession
        
        session = ReviewSession.create(sop_instance_uid="1.2.3.test")
        session.add_manual_region(x=50, y=100, w=400, h=80)
        session.start_review()
        
        collector = DecisionTraceCollector()
        record_region_decisions(
            collector,
            session.get_active_regions(),
            "1.2.3.test"
        )
        
        decisions = collector.get_decisions()
        assert decisions[0].detection_strength is None
        assert decisions[0].ocr_failure is None  # None, not False
        assert decisions[0].confidence_aggregation is None
        assert decisions[0].ocr_engine is None


# ═══════════════════════════════════════════════════════════════════════════════
# PHASE 4 OPTION B: HEADER/FOOTER BANDING TESTS
# ═══════════════════════════════════════════════════════════════════════════════

class TestZoneClassification:
    """Tests for Phase 4 Option B static header/footer banding."""
    
    def test_classify_zone_header(self):
        """Box in top 15% should be classified as HEADER."""
        from run_on_dicom import _classify_zone
        
        # Image height 1000, box at y=50 with height 20
        # Center = 60, which is 6% of 1000 (< 15% threshold)
        zone = _classify_zone(y=50, h=20, image_height=1000)
        assert zone == "HEADER"
    
    def test_classify_zone_footer(self):
        """Box in bottom 15% should be classified as FOOTER."""
        from run_on_dicom import _classify_zone
        
        # Image height 1000, box at y=900 with height 50
        # Center = 925, which is 92.5% of 1000 (> 85% threshold)
        zone = _classify_zone(y=900, h=50, image_height=1000)
        assert zone == "FOOTER"
    
    def test_classify_zone_body(self):
        """Box in middle should be classified as BODY."""
        from run_on_dicom import _classify_zone
        
        # Image height 1000, box at y=400 with height 100
        # Center = 450, which is 45% of 1000 (between 15% and 85%)
        zone = _classify_zone(y=400, h=100, image_height=1000)
        assert zone == "BODY"
    
    def test_classify_zone_header_boundary(self):
        """Box exactly at header threshold boundary."""
        from run_on_dicom import _classify_zone
        
        # Image height 1000, box center at exactly 15%
        # y + h/2 = 150, so y=140, h=20
        zone = _classify_zone(y=140, h=20, image_height=1000)
        assert zone == "HEADER"  # <= 0.15 is HEADER
    
    def test_classify_zone_footer_boundary(self):
        """Box exactly at footer threshold boundary."""
        from run_on_dicom import _classify_zone
        
        # Image height 1000, box center at exactly 85%
        # y + h/2 = 850, so y=840, h=20
        zone = _classify_zone(y=840, h=20, image_height=1000)
        assert zone == "FOOTER"  # >= 0.85 is FOOTER
    
    def test_classify_zone_modality_us(self):
        """US modality should use tighter thresholds (12%)."""
        from run_on_dicom import _classify_zone
        
        # Image height 1000, box center at 13% (would be BODY with default 15%)
        # y + h/2 = 130
        zone_default = _classify_zone(y=120, h=20, image_height=1000)
        zone_us = _classify_zone(y=120, h=20, image_height=1000, modality="US")
        
        assert zone_default == "HEADER"  # 13% < 15%
        # For US, 12% threshold means 13% is BODY
        assert zone_us == "BODY"  # 13% > 12%
    
    def test_classify_zone_zero_height_defensive(self):
        """Zero image height should return BODY (defensive)."""
        from run_on_dicom import _classify_zone
        
        zone = _classify_zone(y=50, h=20, image_height=0)
        assert zone == "BODY"
    
    def test_classify_all_zones_multiple_boxes(self):
        """Should classify multiple boxes correctly."""
        from run_on_dicom import _classify_all_zones
        
        boxes = [
            (10, 50, 100, 20),   # Header (center at 60)
            (10, 450, 100, 100),  # Body (center at 500)
            (10, 920, 100, 40),   # Footer (center at 940)
        ]
        
        zones = _classify_all_zones(boxes, image_height=1000)
        
        assert zones == ["HEADER", "BODY", "FOOTER"]
    
    def test_classify_all_zones_empty_list(self):
        """Empty box list should return empty zones."""
        from run_on_dicom import _classify_all_zones
        
        zones = _classify_all_zones([], image_height=1000)
        assert zones == []
    
    def test_detection_result_includes_zones(self):
        """DetectionResult should include zone classification."""
        from run_on_dicom import DetectionResult
        
        result = DetectionResult(
            static_box=(10, 50, 100, 20),
            all_detected_boxes=[(10, 50, 100, 20), (10, 900, 100, 40)],
            detection_strength="HIGH",
            ocr_failure=False,
            confidence_scores=[0.95, 0.92],
            region_zones=["HEADER", "FOOTER"],
            image_height=1000,
        )
        
        assert result.region_zones == ["HEADER", "FOOTER"]
        assert result.image_height == 1000
    
    def test_detection_result_zones_match_boxes_length(self):
        """region_zones should have same length as all_detected_boxes."""
        from run_on_dicom import DetectionResult, _classify_all_zones
        
        boxes = [(10, 50, 100, 20), (10, 450, 100, 100), (10, 920, 100, 40)]
        zones = _classify_all_zones(boxes, image_height=1000)
        
        assert len(zones) == len(boxes)


class TestZoneBandingGovernance:
    """Verify Option B adheres to governance constraints."""
    
    def test_zone_thresholds_are_static(self):
        """Zone thresholds must be static constants, not learned."""
        from run_on_dicom import ZONE_HEADER_THRESHOLD, ZONE_FOOTER_THRESHOLD
        
        # Verify they're floats (not functions or callables)
        assert isinstance(ZONE_HEADER_THRESHOLD, float)
        assert isinstance(ZONE_FOOTER_THRESHOLD, float)
        
        # Verify documented values
        assert ZONE_HEADER_THRESHOLD == 0.15
        assert ZONE_FOOTER_THRESHOLD == 0.85
    
    def test_modality_thresholds_documented(self):
        """Modality-specific thresholds must be documented."""
        from run_on_dicom import MODALITY_ZONE_THRESHOLDS
        
        # US should have tighter bands
        assert "US" in MODALITY_ZONE_THRESHOLDS
        assert MODALITY_ZONE_THRESHOLDS["US"]["header"] == 0.12
        assert MODALITY_ZONE_THRESHOLDS["US"]["footer"] == 0.88
    
    def test_zone_names_are_strings(self):
        """Zone classifications must be plain strings, not enums."""
        from run_on_dicom import _classify_zone
        
        # All possible zone outcomes
        zone_header = _classify_zone(y=0, h=10, image_height=1000)
        zone_footer = _classify_zone(y=950, h=10, image_height=1000)
        zone_body = _classify_zone(y=500, h=10, image_height=1000)
        
        assert isinstance(zone_header, str)
        assert isinstance(zone_footer, str)
        assert isinstance(zone_body, str)
        assert zone_header in ("HEADER", "FOOTER", "BODY")
        assert zone_footer in ("HEADER", "FOOTER", "BODY")
        assert zone_body in ("HEADER", "FOOTER", "BODY")
