"""
Unit tests for src/clinical_corrector.py

Coverage target: Raise from 12% to 45-60%

Test strategy:
1. _boxes_overlap: Pure function tests (no mocks)
2. inject_audit_tags: DICOM fixture tests
3. generate_medical_overlay: Shape/dtype/behavior verification
4. __init__: Mock PaddleOCR for init path coverage
"""
import tempfile
import os

import pytest
import numpy as np
import pydicom
from pydicom.dataset import Dataset, FileDataset
from pydicom.uid import ExplicitVRLittleEndian
from unittest.mock import patch, MagicMock


# ============================================================================
# FIXTURES
# ============================================================================

@pytest.fixture
def minimal_dicom_file():
    """
    Creates a minimal valid DICOM file for inject_audit_tags testing.
    Uses tiny dimensions (2x2) for speed.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        filepath = os.path.join(tmpdir, "test.dcm")
        
        file_meta = pydicom.Dataset()
        file_meta.MediaStorageSOPClassUID = pydicom.uid.CTImageStorage
        file_meta.MediaStorageSOPInstanceUID = pydicom.uid.generate_uid()
        file_meta.TransferSyntaxUID = ExplicitVRLittleEndian
        
        ds = FileDataset(filepath, {}, file_meta=file_meta, preamble=b"\0" * 128)
        ds.PatientName = "Test^Patient"
        ds.PatientID = "TEST001"
        ds.StudyInstanceUID = pydicom.uid.generate_uid()
        ds.SeriesInstanceUID = pydicom.uid.generate_uid()
        ds.SOPInstanceUID = file_meta.MediaStorageSOPInstanceUID
        ds.SOPClassUID = file_meta.MediaStorageSOPClassUID
        ds.Modality = "US"
        ds.StudyDate = "20231201"
        ds.Rows = 2
        ds.Columns = 2
        ds.BitsAllocated = 8
        ds.BitsStored = 8
        ds.HighBit = 7
        ds.PixelRepresentation = 0
        ds.SamplesPerPixel = 1
        ds.PhotometricInterpretation = "MONOCHROME2"
        ds.PixelData = np.zeros((2, 2), dtype=np.uint8).tobytes()
        
        ds.save_as(filepath, write_like_original=False)
        yield filepath


@pytest.fixture
def corrector_with_mock_ocr():
    """
    Creates a ClinicalCorrector instance with mocked PaddleOCR.
    This avoids loading the actual PaddleOCR which is slow/unavailable.
    """
    with patch('src.clinical_corrector.PaddleOCR') as MockPaddleOCR:
        mock_ocr_instance = MagicMock()
        mock_ocr_instance.predict.return_value = []
        MockPaddleOCR.return_value = mock_ocr_instance
        
        from src.clinical_corrector import ClinicalCorrector
        corrector = ClinicalCorrector()
        yield corrector


# ============================================================================
# TEST CLASS: _boxes_overlap (Pure Function)
# ============================================================================

class TestBoxesOverlap:
    """
    Tests for ClinicalCorrector._boxes_overlap()
    
    This is a pure function that checks if two bounding boxes (x, y, w, h)
    have centers within a pixel tolerance of each other.
    """
    
    def test_identical_boxes_overlap(self, corrector_with_mock_ocr):
        """Two identical boxes should definitely overlap."""
        corrector = corrector_with_mock_ocr
        box = (10, 20, 100, 50)  # (x, y, w, h)
        
        result = corrector._boxes_overlap(box, box, tolerance=20)
        
        assert result is True
    
    def test_boxes_same_center_different_size_overlap(self, corrector_with_mock_ocr):
        """Boxes with same center but different sizes should overlap."""
        corrector = corrector_with_mock_ocr
        box1 = (10, 10, 100, 100)  # center at (60, 60)
        box2 = (30, 30, 60, 60)    # center at (60, 60)
        
        result = corrector._boxes_overlap(box1, box2, tolerance=20)
        
        assert result is True
    
    def test_boxes_within_tolerance_overlap(self, corrector_with_mock_ocr):
        """Boxes with centers within tolerance should overlap."""
        corrector = corrector_with_mock_ocr
        box1 = (0, 0, 100, 100)    # center at (50, 50)
        box2 = (10, 10, 100, 100)  # center at (60, 60) - 14px away diagonally
        
        result = corrector._boxes_overlap(box1, box2, tolerance=20)
        
        assert result is True
    
    def test_boxes_outside_tolerance_no_overlap(self, corrector_with_mock_ocr):
        """Boxes with centers outside tolerance should not overlap."""
        corrector = corrector_with_mock_ocr
        box1 = (0, 0, 100, 100)      # center at (50, 50)
        box2 = (100, 100, 100, 100)  # center at (150, 150) - 141px away
        
        result = corrector._boxes_overlap(box1, box2, tolerance=20)
        
        assert result is False
    
    def test_boxes_exactly_at_tolerance_boundary(self, corrector_with_mock_ocr):
        """Boxes with centers exactly at tolerance should overlap (<=)."""
        corrector = corrector_with_mock_ocr
        box1 = (0, 0, 100, 100)     # center at (50, 50)
        box2 = (20, 0, 100, 100)    # center at (70, 50) - exactly 20px away in X
        
        result = corrector._boxes_overlap(box1, box2, tolerance=20)
        
        assert result is True
    
    def test_boxes_one_pixel_past_tolerance(self, corrector_with_mock_ocr):
        """Boxes with centers 1px past tolerance should not overlap."""
        corrector = corrector_with_mock_ocr
        box1 = (0, 0, 100, 100)     # center at (50, 50)
        box2 = (21, 0, 100, 100)    # center at (71, 50) - 21px away in X
        
        result = corrector._boxes_overlap(box1, box2, tolerance=20)
        
        assert result is False
    
    def test_zero_tolerance_exact_match_required(self, corrector_with_mock_ocr):
        """With zero tolerance, only identical centers should match."""
        corrector = corrector_with_mock_ocr
        box1 = (0, 0, 100, 100)
        box2 = (1, 0, 100, 100)  # 1px offset
        
        result = corrector._boxes_overlap(box1, box2, tolerance=0)
        
        assert result is False
    
    def test_small_boxes_at_origin(self, corrector_with_mock_ocr):
        """Test with minimal 1x1 boxes at origin."""
        corrector = corrector_with_mock_ocr
        box1 = (0, 0, 1, 1)  # center at (0, 0)
        box2 = (0, 0, 1, 1)  # same center
        
        result = corrector._boxes_overlap(box1, box2, tolerance=1)
        
        assert result is True


# ============================================================================
# TEST CLASS: inject_audit_tags (DICOM Integration)
# ============================================================================

class TestInjectAuditTags:
    """
    Tests for ClinicalCorrector.inject_audit_tags()
    
    This method injects private audit tags into a DICOM file for
    APP 10 compliance tracking.
    """
    
    def test_inject_tags_returns_true_on_success(
        self, corrector_with_mock_ocr, minimal_dicom_file
    ):
        """Successful injection should return True."""
        corrector = corrector_with_mock_ocr
        
        result = corrector.inject_audit_tags(
            minimal_dicom_file,
            original_text="ORIGINAL^PATIENT",
            new_text="ANON^PATIENT"
        )
        
        assert result is True
    
    def test_injected_tags_are_readable(
        self, corrector_with_mock_ocr, minimal_dicom_file
    ):
        """Injected private tags should be readable from the file."""
        corrector = corrector_with_mock_ocr
        
        corrector.inject_audit_tags(
            minimal_dicom_file,
            original_text="ORIGINAL^PATIENT",
            new_text="ANON^PATIENT"
        )
        
        # Read back and verify
        ds = pydicom.dcmread(minimal_dicom_file)
        block = ds.private_block(0x0009, "ClinicalCorrector")
        
        # Element 0x01 = original text
        assert block[0x01].value == "ORIGINAL^PATIENT"
        # Element 0x02 = new text
        assert block[0x02].value == "ANON^PATIENT"
    
    def test_injected_timestamp_format(
        self, corrector_with_mock_ocr, minimal_dicom_file
    ):
        """Timestamp should be in YYYYMMDDHHMMSS format (DT VR)."""
        corrector = corrector_with_mock_ocr
        
        corrector.inject_audit_tags(
            minimal_dicom_file,
            original_text="TEST",
            new_text="ANON"
        )
        
        ds = pydicom.dcmread(minimal_dicom_file)
        block = ds.private_block(0x0009, "ClinicalCorrector")
        
        # Element 0x03 = timestamp
        timestamp = block[0x03].value
        assert len(timestamp) == 14  # YYYYMMDDHHMMSS
        assert timestamp.isdigit()
    
    def test_software_version_tag(
        self, corrector_with_mock_ocr, minimal_dicom_file
    ):
        """Software version tag should be set."""
        corrector = corrector_with_mock_ocr
        
        corrector.inject_audit_tags(
            minimal_dicom_file,
            original_text="TEST",
            new_text="ANON"
        )
        
        ds = pydicom.dcmread(minimal_dicom_file)
        block = ds.private_block(0x0009, "ClinicalCorrector")
        
        # Element 0x04 = software version
        version = block[0x04].value
        assert "ClinicalCorrector" in version
        assert "v1.0" in version
    
    def test_long_text_truncated_to_64_chars(
        self, corrector_with_mock_ocr, minimal_dicom_file
    ):
        """Text longer than 64 chars should be truncated (LO VR limit)."""
        corrector = corrector_with_mock_ocr
        long_text = "A" * 100  # 100 chars
        
        corrector.inject_audit_tags(
            minimal_dicom_file,
            original_text=long_text,
            new_text="SHORT"
        )
        
        ds = pydicom.dcmread(minimal_dicom_file)
        block = ds.private_block(0x0009, "ClinicalCorrector")
        
        # Should be truncated to 64 chars
        assert len(block[0x01].value) == 64
    
    def test_returns_false_on_invalid_path(self, corrector_with_mock_ocr):
        """Should return False for non-existent file."""
        corrector = corrector_with_mock_ocr
        
        result = corrector.inject_audit_tags(
            "/nonexistent/path/file.dcm",
            original_text="TEST",
            new_text="ANON"
        )
        
        assert result is False
    
    def test_empty_text_values(
        self, corrector_with_mock_ocr, minimal_dicom_file
    ):
        """Should handle empty text values."""
        corrector = corrector_with_mock_ocr
        
        result = corrector.inject_audit_tags(
            minimal_dicom_file,
            original_text="",
            new_text=""
        )
        
        assert result is True
        
        ds = pydicom.dcmread(minimal_dicom_file)
        block = ds.private_block(0x0009, "ClinicalCorrector")
        assert block[0x01].value == ""


# ============================================================================
# TEST CLASS: generate_medical_overlay
# ============================================================================

class TestGenerateMedicalOverlay:
    """
    Tests for ClinicalCorrector.generate_medical_overlay()
    
    This method creates a noisy text overlay mimicking ultrasound display.
    Uses cv2 which is generally available, and returns a numpy array.
    """
    
    def test_output_shape_matches_input_dimensions(self, corrector_with_mock_ocr):
        """Output should have correct height x width x 3 channels."""
        corrector = corrector_with_mock_ocr
        
        overlay = corrector.generate_medical_overlay(
            text="TEST",
            width=100,
            height=50
        )
        
        assert overlay.shape == (50, 100, 3)
    
    def test_output_dtype_is_uint8(self, corrector_with_mock_ocr):
        """Output should be uint8 (0-255 range)."""
        corrector = corrector_with_mock_ocr
        
        overlay = corrector.generate_medical_overlay(
            text="TEST",
            width=100,
            height=50
        )
        
        assert overlay.dtype == np.uint8
    
    def test_output_has_nonzero_content(self, corrector_with_mock_ocr):
        """Overlay should contain visible content (not all black)."""
        corrector = corrector_with_mock_ocr
        
        overlay = corrector.generate_medical_overlay(
            text="TEST TEXT",
            width=200,
            height=100
        )
        
        # Should have some non-zero pixels from text and noise
        assert np.sum(overlay) > 0
    
    def test_multiline_text_supported(self, corrector_with_mock_ocr):
        """Should handle multi-line text with newlines."""
        corrector = corrector_with_mock_ocr
        
        overlay = corrector.generate_medical_overlay(
            text="LINE1\nLINE2\nLINE3",
            width=200,
            height=150
        )
        
        assert overlay.shape == (150, 200, 3)
        assert np.sum(overlay) > 0
    
    def test_auto_scale_mode(self, corrector_with_mock_ocr):
        """Auto-scale mode should produce valid output for long text."""
        corrector = corrector_with_mock_ocr
        
        long_text = "VERY LONG PATIENT NAME THAT WOULD OVERFLOW"
        overlay = corrector.generate_medical_overlay(
            text=long_text,
            width=100,
            height=50,
            auto_scale=True
        )
        
        assert overlay.shape == (50, 100, 3)
        assert overlay.dtype == np.uint8
    
    def test_minimal_dimensions(self, corrector_with_mock_ocr):
        """Should handle very small dimensions (edge case)."""
        corrector = corrector_with_mock_ocr
        
        overlay = corrector.generate_medical_overlay(
            text="X",
            width=10,
            height=10
        )
        
        assert overlay.shape == (10, 10, 3)
    
    def test_empty_text_produces_output(self, corrector_with_mock_ocr):
        """Empty text should still produce valid (possibly noisy) output."""
        corrector = corrector_with_mock_ocr
        
        overlay = corrector.generate_medical_overlay(
            text="",
            width=50,
            height=50
        )
        
        assert overlay.shape == (50, 50, 3)
        assert overlay.dtype == np.uint8
    
    def test_whitespace_only_lines_skipped(self, corrector_with_mock_ocr):
        """Lines with only whitespace should be skipped gracefully."""
        corrector = corrector_with_mock_ocr
        
        overlay = corrector.generate_medical_overlay(
            text="LINE1\n   \nLINE3",
            width=100,
            height=100
        )
        
        assert overlay.shape == (100, 100, 3)
    
    def test_output_values_in_valid_range(self, corrector_with_mock_ocr):
        """All pixel values should be in 0-255 range."""
        corrector = corrector_with_mock_ocr
        
        overlay = corrector.generate_medical_overlay(
            text="TEST",
            width=100,
            height=50
        )
        
        assert overlay.min() >= 0
        assert overlay.max() <= 255


# ============================================================================
# TEST CLASS: __init__ (Initialization)
# ============================================================================

class TestClinicalCorrectorInit:
    """
    Tests for ClinicalCorrector.__init__()
    """
    
    def test_init_sets_cuda_environment_variable(self):
        """Initialization should set CUDA_VISIBLE_DEVICES to empty."""
        with patch('src.clinical_corrector.PaddleOCR') as MockPaddleOCR:
            MockPaddleOCR.return_value = MagicMock()
            
            from src.clinical_corrector import ClinicalCorrector
            corrector = ClinicalCorrector()
            
            # Check that CUDA is disabled
            assert os.environ.get("CUDA_VISIBLE_DEVICES") == ""
    
    def test_init_creates_ocr_with_english_lang(self):
        """OCR should be initialized with lang='en'."""
        with patch('src.clinical_corrector.PaddleOCR') as MockPaddleOCR:
            mock_instance = MagicMock()
            MockPaddleOCR.return_value = mock_instance
            
            from src.clinical_corrector import ClinicalCorrector
            corrector = ClinicalCorrector()
            
            # Verify PaddleOCR was called with expected params
            MockPaddleOCR.assert_called_once()
            call_kwargs = MockPaddleOCR.call_args[1]
            assert call_kwargs.get('lang') == 'en'
            assert call_kwargs.get('det_db_thresh') == 0.1
    
    def test_init_exposes_ocr_attribute(self):
        """Initialized corrector should have .ocr attribute."""
        with patch('src.clinical_corrector.PaddleOCR') as MockPaddleOCR:
            mock_instance = MagicMock()
            MockPaddleOCR.return_value = mock_instance
            
            from src.clinical_corrector import ClinicalCorrector
            corrector = ClinicalCorrector()
            
            assert hasattr(corrector, 'ocr')
            assert corrector.ocr is mock_instance


# ============================================================================
# TEST CLASS: _preprocess_for_ocr
# ============================================================================

class TestPreprocessForOcr:
    """
    Tests for ClinicalCorrector._preprocess_for_ocr()
    
    This method prepares frames for OCR by upscaling and thresholding.
    """
    
    def test_output_is_upscaled_2x(self, corrector_with_mock_ocr):
        """Output should be 2x the input dimensions."""
        corrector = corrector_with_mock_ocr
        
        # Create a small BGR input frame (10x10)
        input_frame = np.zeros((10, 10, 3), dtype=np.uint8)
        
        result = corrector._preprocess_for_ocr(input_frame)
        
        # Should be 20x20
        assert result.shape == (20, 20, 3)
    
    def test_output_is_3_channel_bgr(self, corrector_with_mock_ocr):
        """Output should be 3-channel for PaddleOCR compatibility."""
        corrector = corrector_with_mock_ocr
        
        input_frame = np.zeros((10, 15, 3), dtype=np.uint8)
        
        result = corrector._preprocess_for_ocr(input_frame)
        
        assert result.shape[2] == 3
    
    def test_white_pixels_preserved_above_threshold(self, corrector_with_mock_ocr):
        """Pixels with value > 200 should become white (255)."""
        corrector = corrector_with_mock_ocr
        
        # Create frame with white patch
        input_frame = np.zeros((10, 10, 3), dtype=np.uint8)
        input_frame[4:6, 4:6] = 255  # White square in center
        
        result = corrector._preprocess_for_ocr(input_frame)
        
        # After thresholding, white areas should still be white
        # Check center of upscaled image (8:12, 8:12)
        center_region = result[8:12, 8:12]
        assert np.max(center_region) == 255
    
    def test_dark_pixels_become_black(self, corrector_with_mock_ocr):
        """Pixels with value <= 200 should become black (0)."""
        corrector = corrector_with_mock_ocr
        
        # Create frame with mid-gray value (< 200)
        input_frame = np.full((10, 10, 3), 150, dtype=np.uint8)
        
        result = corrector._preprocess_for_ocr(input_frame)
        
        # All pixels should be 0 after thresholding
        assert np.max(result) == 0
