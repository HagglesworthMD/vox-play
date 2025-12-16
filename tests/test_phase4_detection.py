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

