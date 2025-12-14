"""
Unit tests for clinical_corrector.py - UNCOVERED METHODS

Focuses on detect_static_text() and process_video().
Uses mocking extensively to avoid filesystem/video I/O.

Target coverage gain: +35-40%
"""
import pytest
import numpy as np
import os
import sys
from unittest.mock import MagicMock, patch, call

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))


# ============================================================================
# FIXTURES
# ============================================================================

@pytest.fixture
def corrector_with_mock_ocr():
    """
    Creates a ClinicalCorrector instance with mocked PaddleOCR.
    This avoids loading the actual PaddleOCR which is slow/unavailable.
    """
    with patch('clinical_corrector.PaddleOCR') as MockPaddleOCR:
        mock_ocr_instance = MagicMock()
        mock_ocr_instance.predict.return_value = []
        MockPaddleOCR.return_value = mock_ocr_instance
        
        from clinical_corrector import ClinicalCorrector
        corrector = ClinicalCorrector()
        yield corrector


@pytest.fixture
def mock_video_capture():
    """
    Factory fixture for creating mock VideoCapture objects.
    """
    def _create_mock(total_frames=10, frame_width=640, frame_height=480, fps=30.0):
        mock_cap = MagicMock()
        mock_cap.isOpened.return_value = True
        
        def get_side_effect(prop):
            # cv2.CAP_PROP_FRAME_COUNT = 7
            # cv2.CAP_PROP_FRAME_WIDTH = 3
            # cv2.CAP_PROP_FRAME_HEIGHT = 4
            # cv2.CAP_PROP_FPS = 5
            prop_map = {
                7: total_frames,   # CAP_PROP_FRAME_COUNT
                3: frame_width,    # CAP_PROP_FRAME_WIDTH
                4: frame_height,   # CAP_PROP_FRAME_HEIGHT
                5: fps,            # CAP_PROP_FPS
            }
            return prop_map.get(prop, 0)
        
        mock_cap.get.side_effect = get_side_effect
        mock_cap.read.return_value = (True, np.zeros((frame_height, frame_width, 3), dtype=np.uint8))
        
        return mock_cap
    
    return _create_mock


# ============================================================================
# TEST CLASS: detect_static_text - Early Exit & Validation
# ============================================================================

class TestDetectStaticTextValidation:
    """Tests for early exit and validation branches in detect_static_text()."""
    
    def test_cannot_open_video_raises_error(self, corrector_with_mock_ocr):
        """Should raise ValueError if video file cannot be opened."""
        corrector = corrector_with_mock_ocr
        
        # Mock cv2.VideoCapture to return unopened capture
        mock_cap = MagicMock()
        mock_cap.isOpened.return_value = False
        
        with patch('clinical_corrector.cv2.VideoCapture', return_value=mock_cap):
            with pytest.raises(ValueError, match="Cannot open video file"):
                corrector.detect_static_text("/fake/video.mp4")
    
    def test_no_boxes_detected_returns_none(self, corrector_with_mock_ocr, mock_video_capture):
        """Should return None when OCR finds no text in any frame."""
        corrector = corrector_with_mock_ocr
        mock_cap = mock_video_capture(total_frames=10)
        
        # Mock OCR to return no detections
        corrector.ocr.predict.return_value = []
        
        with patch('clinical_corrector.cv2.VideoCapture', return_value=mock_cap):
            result = corrector.detect_static_text("/fake/video.mp4")
        
        assert result is None
        mock_cap.release.assert_called_once()
    
    def test_empty_first_frame_boxes_returns_none(self, corrector_with_mock_ocr, mock_video_capture):
        """Should return None if reference frame has no detected boxes."""
        corrector = corrector_with_mock_ocr
        mock_cap = mock_video_capture(total_frames=10)
        
        # OCR returns empty results for all frames
        corrector.ocr.predict.return_value = []
        
        with patch('clinical_corrector.cv2.VideoCapture', return_value=mock_cap):
            result = corrector.detect_static_text("/fake/video.mp4")
        
        assert result is None


# ============================================================================
# TEST CLASS: detect_static_text - Frame Sampling Logic
# ============================================================================

class TestDetectStaticTextFrameSampling:
    """Tests for frame sampling logic (short vs long videos)."""
    
    def test_short_video_scans_all_frames(self, corrector_with_mock_ocr, mock_video_capture):
        """For videos < 10 frames, should scan ALL frames."""
        corrector = corrector_with_mock_ocr
        mock_cap = mock_video_capture(total_frames=8)
        corrector.ocr.predict.return_value = []
        
        with patch('clinical_corrector.cv2.VideoCapture', return_value=mock_cap):
            corrector.detect_static_text("/fake/video.mp4")
        
        # Should call set() for frames 0-7 (8 times)
        # cv2.CAP_PROP_POS_FRAMES = 1
        set_calls = [c for c in mock_cap.set.call_args_list if c[0][0] == 1]
        assert len(set_calls) == 8
        
        # Verify all frames 0-7 were requested
        requested_frames = sorted([c[0][1] for c in set_calls])
        assert requested_frames == list(range(8))
    
    def test_long_video_samples_first_and_last_5(self, corrector_with_mock_ocr, mock_video_capture):
        """For videos >= 10 frames, should only sample first 5 + last 5."""
        corrector = corrector_with_mock_ocr
        mock_cap = mock_video_capture(total_frames=50)
        corrector.ocr.predict.return_value = []
        
        with patch('clinical_corrector.cv2.VideoCapture', return_value=mock_cap):
            corrector.detect_static_text("/fake/video.mp4")
        
        # Should sample frames: 0,1,2,3,4, 45,46,47,48,49 (10 total)
        expected_indices = [0, 1, 2, 3, 4, 45, 46, 47, 48, 49]
        
        # cv2.CAP_PROP_POS_FRAMES = 1
        set_calls = [c for c in mock_cap.set.call_args_list if c[0][0] == 1]
        actual_indices = [int(c[0][1]) for c in set_calls]
        
        assert actual_indices == expected_indices
    
    def test_exactly_10_frames_samples_first_and_last_5(self, corrector_with_mock_ocr, mock_video_capture):
        """For exactly 10 frames, should sample first 5 + last 5."""
        corrector = corrector_with_mock_ocr
        mock_cap = mock_video_capture(total_frames=10)
        corrector.ocr.predict.return_value = []
        
        with patch('clinical_corrector.cv2.VideoCapture', return_value=mock_cap):
            corrector.detect_static_text("/fake/video.mp4")
        
        # For 10 frames: first 5 = [0,1,2,3,4], last 5 = [5,6,7,8,9]
        expected_indices = [0, 1, 2, 3, 4, 5, 6, 7, 8, 9]
        
        set_calls = [c for c in mock_cap.set.call_args_list if c[0][0] == 1]
        actual_indices = [int(c[0][1]) for c in set_calls]
        
        assert actual_indices == expected_indices


# ============================================================================
# TEST CLASS: detect_static_text - OCR API Format Handling
# ============================================================================

class TestDetectStaticTextOcrApiFormats:
    """Tests for parsing both new and old PaddleOCR API formats."""
    
    def test_new_api_dict_format_with_det_boxes(self, corrector_with_mock_ocr, mock_video_capture):
        """Should parse new PaddleOCR API format (dict with 'det_boxes')."""
        corrector = corrector_with_mock_ocr
        mock_cap = mock_video_capture(total_frames=10)
        
        # Mock OCR returning new API format
        # Box coordinates are at 2x scale (preprocessor upscales)
        # Box: [[20,20], [120,20], [120,60], [20,60]] -> (10,10,50,20) after /2
        corrector.ocr.predict.return_value = [
            {
                'det_boxes': [
                    [[20, 20], [120, 20], [120, 60], [20, 60]]
                ]
            }
        ]
        
        with patch('clinical_corrector.cv2.VideoCapture', return_value=mock_cap):
            result = corrector.detect_static_text("/fake/video.mp4")
        
        # Should return scaled-down box (divided by 2)
        assert result is not None
        x, y, w, h = result
        assert x == 10
        assert y == 10
        assert w == 50
        assert h == 20
    
    def test_old_api_list_format(self, corrector_with_mock_ocr, mock_video_capture):
        """Should parse old PaddleOCR API format (list of [box, (text, score)])."""
        corrector = corrector_with_mock_ocr
        mock_cap = mock_video_capture(total_frames=10)
        
        # Mock OCR returning old API format
        # Box: [[40,40], [140,40], [140,80], [40,80]] -> (20,20,50,20) after /2
        corrector.ocr.predict.return_value = [
            [
                [[[40, 40], [140, 40], [140, 80], [40, 80]], ("PATIENT", 0.95)]
            ]
        ]
        
        with patch('clinical_corrector.cv2.VideoCapture', return_value=mock_cap):
            result = corrector.detect_static_text("/fake/video.mp4")
        
        # Scaled-down box
        assert result is not None
        x, y, w, h = result
        assert x == 20
        assert y == 20
        assert w == 50
        assert h == 20
    
    def test_empty_det_boxes_list(self, corrector_with_mock_ocr, mock_video_capture):
        """Should handle empty det_boxes list gracefully."""
        corrector = corrector_with_mock_ocr
        mock_cap = mock_video_capture(total_frames=10)
        
        # Empty det_boxes
        corrector.ocr.predict.return_value = [{'det_boxes': []}]
        
        with patch('clinical_corrector.cv2.VideoCapture', return_value=mock_cap):
            result = corrector.detect_static_text("/fake/video.mp4")
        
        assert result is None


# ============================================================================
# TEST CLASS: detect_static_text - Box Consistency Logic
# ============================================================================

class TestDetectStaticTextConsistency:
    """Tests for box consistency threshold (>=50% of frames)."""
    
    def test_box_in_all_frames_is_returned(self, corrector_with_mock_ocr, mock_video_capture):
        """Box appearing in all frames should definitely be returned."""
        corrector = corrector_with_mock_ocr
        mock_cap = mock_video_capture(total_frames=10)
        
        # Always return the same box
        corrector.ocr.predict.return_value = [
            {'det_boxes': [[[20, 20], [120, 20], [120, 60], [20, 60]]]}
        ]
        
        with patch('clinical_corrector.cv2.VideoCapture', return_value=mock_cap):
            result = corrector.detect_static_text("/fake/video.mp4")
        
        assert result is not None
    
    def test_box_in_half_frames_is_returned(self, corrector_with_mock_ocr, mock_video_capture):
        """Box appearing in >=50% of frames should be returned."""
        corrector = corrector_with_mock_ocr
        mock_cap = mock_video_capture(total_frames=10)
        
        # Track call count
        call_count = [0]
        
        def ocr_side_effect(img):
            call_count[0] += 1
            # Return box for first 6 frames (60% > 50%)
            if call_count[0] <= 6:
                return [{'det_boxes': [[[20, 20], [120, 20], [120, 60], [20, 60]]]}]
            return []
        
        corrector.ocr.predict.side_effect = ocr_side_effect
        
        with patch('clinical_corrector.cv2.VideoCapture', return_value=mock_cap):
            result = corrector.detect_static_text("/fake/video.mp4")
        
        # Should return the box (appears in >50% of frames)
        assert result is not None
    
    def test_inconsistent_box_returns_none(self, corrector_with_mock_ocr, mock_video_capture):
        """Box appearing in <50% of frames should be rejected."""
        corrector = corrector_with_mock_ocr
        mock_cap = mock_video_capture(total_frames=10)
        
        call_count = [0]
        
        def ocr_side_effect(img):
            call_count[0] += 1
            # Return box only in first 3 frames (30% < 50%)
            if call_count[0] <= 3:
                return [{'det_boxes': [[[20, 20], [120, 20], [120, 60], [20, 60]]]}]
            return []
        
        corrector.ocr.predict.side_effect = ocr_side_effect
        
        with patch('clinical_corrector.cv2.VideoCapture', return_value=mock_cap):
            result = corrector.detect_static_text("/fake/video.mp4")
        
        # Should return None (box not consistent enough)
        assert result is None
    
    def test_multiple_boxes_selects_most_consistent(self, corrector_with_mock_ocr, mock_video_capture):
        """When multiple boxes detected, should select the most consistent one."""
        corrector = corrector_with_mock_ocr
        mock_cap = mock_video_capture(total_frames=10)
        
        call_count = [0]
        
        def ocr_side_effect(img):
            call_count[0] += 1
            # Box A appears in all frames, Box B appears in 6 frames
            boxes = [[[20, 20], [120, 20], [120, 60], [20, 60]]]  # Box A
            if call_count[0] <= 6:
                boxes.append([[200, 200], [300, 200], [300, 240], [200, 240]])  # Box B
            return [{'det_boxes': boxes}]
        
        corrector.ocr.predict.side_effect = ocr_side_effect
        
        with patch('clinical_corrector.cv2.VideoCapture', return_value=mock_cap):
            result = corrector.detect_static_text("/fake/video.mp4")
        
        # Should return Box A (more consistent)
        assert result is not None
        x, y, w, h = result
        assert x == 10  # Box A scaled down


# ============================================================================
# TEST CLASS: detect_static_text - Edge Cases
# ============================================================================

class TestDetectStaticTextEdgeCases:
    """Tests for edge cases in detect_static_text()."""
    
    def test_read_failure_skips_frame_gracefully(self, corrector_with_mock_ocr, mock_video_capture):
        """Failed frame read should be skipped gracefully."""
        corrector = corrector_with_mock_ocr
        mock_cap = mock_video_capture(total_frames=10)
        
        # Fail on some frames
        read_count = [0]
        
        def read_side_effect():
            read_count[0] += 1
            # Fail on frames 2 and 5
            if read_count[0] in [3, 6]:  # 1-indexed
                return (False, None)
            return (True, np.zeros((480, 640, 3), dtype=np.uint8))
        
        mock_cap.read.side_effect = read_side_effect
        corrector.ocr.predict.return_value = []
        
        with patch('clinical_corrector.cv2.VideoCapture', return_value=mock_cap):
            # Should not crash
            result = corrector.detect_static_text("/fake/video.mp4")
        
        assert result is None
        mock_cap.release.assert_called_once()
    
    def test_single_frame_video(self, corrector_with_mock_ocr, mock_video_capture):
        """Single-frame video returns None - can't determine if text is static."""
        corrector = corrector_with_mock_ocr
        mock_cap = mock_video_capture(total_frames=1)
        
        corrector.ocr.predict.return_value = [
            {'det_boxes': [[[20, 20], [120, 20], [120, 60], [20, 60]]]}
        ]
        
        with patch('clinical_corrector.cv2.VideoCapture', return_value=mock_cap):
            result = corrector.detect_static_text("/fake/video.mp4")
        
        # Single frame = no other frames to compare, cannot verify "static"
        # This is intentional design: static text requires comparison across frames
        assert result is None


# ============================================================================
# TEST CLASS: process_video - Validation
# ============================================================================

class TestProcessVideoValidation:
    """Tests for validation branches in process_video()."""
    
    def test_cannot_open_video_raises_error(self, corrector_with_mock_ocr):
        """Should raise ValueError if input video cannot be opened."""
        corrector = corrector_with_mock_ocr
        
        mock_cap = MagicMock()
        mock_cap.isOpened.return_value = False
        
        with patch.object(corrector, 'detect_static_text', return_value=(10, 10, 100, 50)):
            with patch('clinical_corrector.cv2.VideoCapture', return_value=mock_cap):
                with pytest.raises(ValueError, match="Cannot open video file"):
                    corrector.process_video("/fake/in.mp4", "/fake/out.mp4", "ANON")


# ============================================================================
# TEST CLASS: process_video - Default Box Path
# ============================================================================

class TestProcessVideoDefaultBox:
    """Tests for default box path when no text detected."""
    
    def test_uses_default_box_when_no_text_detected(self, corrector_with_mock_ocr, mock_video_capture):
        """When detect_static_text returns None, should use default top-left box."""
        corrector = corrector_with_mock_ocr
        mock_cap = mock_video_capture(total_frames=10, frame_width=640, frame_height=480)
        
        # Return 3 frames then stop
        read_count = [0]
        
        def read_side_effect():
            read_count[0] += 1
            if read_count[0] <= 3:
                return (True, np.zeros((480, 640, 3), dtype=np.uint8))
            return (False, None)
        
        mock_cap.read.side_effect = read_side_effect
        
        mock_writer = MagicMock()
        
        with patch.object(corrector, 'detect_static_text', return_value=None):
            with patch('clinical_corrector.cv2.VideoCapture', return_value=mock_cap):
                with patch('clinical_corrector.cv2.VideoWriter', return_value=mock_writer):
                    with patch('clinical_corrector.os.path.exists', return_value=True):
                        result = corrector.process_video(
                            "/fake/in.mp4",
                            "/fake/out.mp4",
                            "ANON^PATIENT"
                        )
        
        assert result is True
        # Verify 3 frames were written
        assert mock_writer.write.call_count == 3
        mock_writer.release.assert_called_once()


# ============================================================================
# TEST CLASS: process_video - Bounding Box Clipping
# ============================================================================

class TestProcessVideoBoundingBoxClipping:
    """Tests for bounding box clipping to frame bounds."""
    
    def test_box_clipped_to_frame_bounds(self, corrector_with_mock_ocr, mock_video_capture):
        """Bounding box should be clipped to frame dimensions."""
        corrector = corrector_with_mock_ocr
        mock_cap = mock_video_capture(total_frames=10, frame_width=640, frame_height=480)
        
        # Return 1 frame then stop
        mock_cap.read.side_effect = [
            (True, np.zeros((480, 640, 3), dtype=np.uint8)),
            (False, None)
        ]
        
        mock_writer = MagicMock()
        
        # Box that would overflow with padding: near edge
        edge_box = (635, 475, 100, 50)  # x+w+padding would exceed 640
        
        with patch.object(corrector, 'detect_static_text', return_value=edge_box):
            with patch('clinical_corrector.cv2.VideoCapture', return_value=mock_cap):
                with patch('clinical_corrector.cv2.VideoWriter', return_value=mock_writer):
                    with patch('clinical_corrector.os.path.exists', return_value=True):
                        result = corrector.process_video(
                            "/fake/in.mp4",
                            "/fake/out.mp4", 
                            "ANON"
                        )
        
        # Should not crash - box is clipped
        assert result is True
    
    def test_negative_coordinates_clamped_to_zero(self, corrector_with_mock_ocr, mock_video_capture):
        """Negative coordinates after padding should be clamped to 0."""
        corrector = corrector_with_mock_ocr
        mock_cap = mock_video_capture(total_frames=10, frame_width=640, frame_height=480)
        
        mock_cap.read.side_effect = [
            (True, np.zeros((480, 640, 3), dtype=np.uint8)),
            (False, None)
        ]
        
        mock_writer = MagicMock()
        
        # Box at origin - padding would make x,y negative
        origin_box = (0, 0, 100, 50)
        
        with patch.object(corrector, 'detect_static_text', return_value=origin_box):
            with patch('clinical_corrector.cv2.VideoCapture', return_value=mock_cap):
                with patch('clinical_corrector.cv2.VideoWriter', return_value=mock_writer):
                    with patch('clinical_corrector.os.path.exists', return_value=True):
                        result = corrector.process_video(
                            "/fake/in.mp4",
                            "/fake/out.mp4",
                            "ANON"
                        )
        
        # Should not crash - coordinates clamped
        assert result is True


# ============================================================================
# TEST CLASS: process_video - Output Verification
# ============================================================================

class TestProcessVideoOutput:
    """Tests for process_video output verification."""
    
    def test_returns_false_when_output_not_created(self, corrector_with_mock_ocr, mock_video_capture):
        """Should return False when output file doesn't exist after processing."""
        corrector = corrector_with_mock_ocr
        mock_cap = mock_video_capture(total_frames=10)
        
        mock_cap.read.side_effect = [
            (True, np.zeros((480, 640, 3), dtype=np.uint8)),
            (False, None)
        ]
        
        mock_writer = MagicMock()
        
        with patch.object(corrector, 'detect_static_text', return_value=None):
            with patch('clinical_corrector.cv2.VideoCapture', return_value=mock_cap):
                with patch('clinical_corrector.cv2.VideoWriter', return_value=mock_writer):
                    with patch('clinical_corrector.os.path.exists', return_value=False):
                        result = corrector.process_video(
                            "/fake/in.mp4",
                            "/fake/out.mp4",
                            "ANON"
                        )
        
        assert result is False
    
    def test_video_writer_receives_correct_fourcc(self, corrector_with_mock_ocr, mock_video_capture):
        """VideoWriter should be initialized with mp4v codec."""
        corrector = corrector_with_mock_ocr
        mock_cap = mock_video_capture(total_frames=10, frame_width=640, frame_height=480, fps=30.0)
        
        mock_cap.read.side_effect = [(False, None)]  # Immediate end
        
        with patch.object(corrector, 'detect_static_text', return_value=None):
            with patch('clinical_corrector.cv2.VideoCapture', return_value=mock_cap):
                with patch('clinical_corrector.cv2.VideoWriter') as MockWriter:
                    with patch('clinical_corrector.cv2.VideoWriter_fourcc', return_value=12345) as mock_fourcc:
                        with patch('clinical_corrector.os.path.exists', return_value=True):
                            corrector.process_video("/fake/in.mp4", "/fake/out.mp4", "ANON")
        
        # Verify fourcc was called with 'mp4v'
        mock_fourcc.assert_called_once_with(*'mp4v')
