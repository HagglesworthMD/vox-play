"""
Unit tests for nifti_handler.py - High-ROI Coverage

Focuses on pure functions, data classes, and core converter logic.
Uses mocking to avoid real DICOM/NIfTI processing.

Target coverage gain: 52% → 85%+
"""
import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch, mock_open

import numpy as np
import pytest

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))


# ============================================================================
# FIXTURES
# ============================================================================

@pytest.fixture
def mock_nifti_settings():
    """Mock nifti_settings to avoid real dicom2nifti configuration."""
    mock_settings = MagicMock()
    return mock_settings


@pytest.fixture
def minimal_conversion_result():
    """Create a minimal NIfTIConversionResult for testing."""
    from nifti_handler import NIfTIConversionResult, QualityAudit
    
    result = NIfTIConversionResult()
    result.success = True
    result.mode = "3D"
    result.converted_files = ["/path/to/output.nii.gz"]
    result.quality_audit = QualityAudit()
    result.quality_audit.input_dicom_count = 10
    result.quality_audit.input_frame_count = 100
    result.quality_audit.output_file_count = 1
    result.quality_audit.output_slice_count = 100
    
    return result


@pytest.fixture
def failed_conversion_result():
    """Create a failed NIfTIConversionResult for testing."""
    from nifti_handler import NIfTIConversionResult, QualityAudit
    
    result = NIfTIConversionResult()
    result.success = False
    result.mode = "failed"
    result.error_message = "Test error message"
    result.warnings = ["Warning 1", "Warning 2"]
    result.quality_audit = QualityAudit()
    
    return result


# ============================================================================
# TEST CLASS: generate_nifti_readme (Pure Function)
# ============================================================================

class TestGenerateNiftiReadme:
    """Tests for generate_nifti_readme() function."""
    
    def test_minimal_result(self, minimal_conversion_result):
        """Should generate valid README with minimal result."""
        from nifti_handler import generate_nifti_readme
        
        readme = generate_nifti_readme(minimal_conversion_result)
        
        assert isinstance(readme, str)
        assert len(readme) > 100
        assert "VoxelMask" in readme
        assert "SUCCESS" in readme
        assert "3D" in readme or "Volumetric" in readme
    
    def test_with_quality_audit(self, minimal_conversion_result):
        """Should include quality audit section when present."""
        from nifti_handler import generate_nifti_readme
        
        readme = generate_nifti_readme(minimal_conversion_result)
        
        assert "QUALITY AUDIT" in readme
        assert "Input DICOMs: 10" in readme
        assert "Input Frames: 100" in readme
        assert "Output Slices: 100" in readme
    
    def test_with_warnings_and_error(self, failed_conversion_result):
        """Should include warnings and error sections."""
        from nifti_handler import generate_nifti_readme
        
        readme = generate_nifti_readme(failed_conversion_result)
        
        assert "FAILED" in readme
        assert "ERROR" in readme
        assert "Test error message" in readme
        assert "CONVERSION LOG" in readme
        assert "Warning 1" in readme
    
    def test_includes_converted_files_list(self, minimal_conversion_result):
        """Should list converted files."""
        from nifti_handler import generate_nifti_readme
        
        readme = generate_nifti_readme(minimal_conversion_result)
        
        assert "CONVERTED FILES" in readme
        assert "output.nii.gz" in readme
    
    def test_includes_mode_descriptions(self):
        """Should include mode-specific descriptions for all modes."""
        from nifti_handler import generate_nifti_readme, NIfTIConversionResult
        
        for mode in ["3D", "4D", "4D_cine", "2D", "failed"]:
            result = NIfTIConversionResult()
            result.mode = mode
            result.success = mode != "failed"
            
            readme = generate_nifti_readme(result)
            assert isinstance(readme, str)
            assert len(readme) > 50
    
    def test_custom_mode_and_profile(self, minimal_conversion_result):
        """Should include custom mode and compliance profile."""
        from nifti_handler import generate_nifti_readme
        
        readme = generate_nifti_readme(
            minimal_conversion_result,
            original_mode="FOI Legal",
            compliance_profile="HIPAA Safe Harbor"
        )
        
        assert "FOI Legal" in readme
        assert "HIPAA Safe Harbor" in readme


# ============================================================================
# TEST CLASS: generate_fallback_warning_file (Pure Function)
# ============================================================================

class TestGenerateFallbackWarningFile:
    """Tests for generate_fallback_warning_file() function."""
    
    def test_minimal_content(self):
        """Should generate valid warning content with minimal input."""
        from nifti_handler import generate_fallback_warning_file
        
        content = generate_fallback_warning_file(
            error_message="Test error",
            warnings=[]
        )
        
        assert isinstance(content, str)
        assert "NIFTI CONVERSION FAILED" in content
        assert "Test error" in content
        assert "YOUR DATA IS SAFE" in content
    
    def test_with_warnings_list(self):
        """Should include warnings in output."""
        from nifti_handler import generate_fallback_warning_file
        
        warnings = ["3D conversion failed", "Multi-frame fallback failed"]
        content = generate_fallback_warning_file(
            error_message="Complete failure",
            warnings=warnings
        )
        
        assert "CONVERSION LOG" in content
        assert "3D conversion failed" in content
        assert "Multi-frame fallback failed" in content
    
    def test_includes_attempted_methods(self):
        """Should document attempted conversion methods."""
        from nifti_handler import generate_fallback_warning_file
        
        content = generate_fallback_warning_file(
            error_message="Test",
            warnings=[]
        )
        
        assert "ATTEMPTED METHODS" in content
        assert "3D/4D volumetric" in content
        assert "Multi-frame cine" in content


# ============================================================================
# TEST CLASS: check_dicom2nifti_available (Pure Function)
# ============================================================================

class TestCheckDicom2NiftiAvailable:
    """Tests for check_dicom2nifti_available() function."""
    
    def test_returns_boolean(self):
        """Should return a boolean value."""
        from nifti_handler import check_dicom2nifti_available
        
        result = check_dicom2nifti_available()
        
        assert isinstance(result, bool)
    
    def test_matches_nifti_available_flag(self):
        """Should match the NIFTI_AVAILABLE module flag."""
        from nifti_handler import check_dicom2nifti_available, NIFTI_AVAILABLE
        
        result = check_dicom2nifti_available()
        
        assert result == NIFTI_AVAILABLE


# ============================================================================
# TEST CLASS: QualityAudit (Data Class)
# ============================================================================

class TestQualityAudit:
    """Tests for QualityAudit class."""
    
    def test_default_values(self):
        """Should initialize with zero counts."""
        from nifti_handler import QualityAudit
        
        audit = QualityAudit()
        
        assert audit.input_dicom_count == 0
        assert audit.input_frame_count == 0
        assert audit.output_file_count == 0
        assert audit.output_slice_count == 0
        assert audit.warnings == []
    
    def test_retention_zero_frames(self):
        """Should handle zero input frames gracefully."""
        from nifti_handler import QualityAudit
        
        audit = QualityAudit()
        audit.input_frame_count = 0
        
        retention, status = audit.calculate_retention()
        
        assert retention == 100.0
        assert "No input frames" in status
    
    def test_retention_excellent(self):
        """Should report EXCELLENT for >=99% retention."""
        from nifti_handler import QualityAudit
        
        audit = QualityAudit()
        audit.input_frame_count = 100
        audit.output_slice_count = 100
        
        retention, status = audit.calculate_retention()
        
        assert retention == 100.0
        assert "EXCELLENT" in status
        assert "100/100" in status
    
    def test_retention_good(self):
        """Should report GOOD for 90-99% retention."""
        from nifti_handler import QualityAudit
        
        audit = QualityAudit()
        audit.input_frame_count = 100
        audit.output_slice_count = 95
        
        retention, status = audit.calculate_retention()
        
        assert retention == 95.0
        assert "GOOD" in status
    
    def test_retention_warning(self):
        """Should report WARNING for <90% retention and add to warnings list."""
        from nifti_handler import QualityAudit
        
        audit = QualityAudit()
        audit.input_frame_count = 100
        audit.output_slice_count = 80
        
        retention, status = audit.calculate_retention()
        
        assert retention == 80.0
        assert "WARNING" in status
        assert len(audit.warnings) == 1
        assert "slice loss" in audit.warnings[0].lower()


# ============================================================================
# TEST CLASS: NIfTIConversionResult (Data Class)
# ============================================================================

class TestNIfTIConversionResult:
    """Tests for NIfTIConversionResult class."""
    
    def test_default_values(self):
        """Should initialize with expected defaults."""
        from nifti_handler import NIfTIConversionResult
        
        result = NIfTIConversionResult()
        
        assert result.success is False
        assert result.mode == "unknown"
        assert result.converted_files == []
        assert result.failed_files == []
        assert result.warnings == []
        assert result.error_message is None
        assert result.output_folder is None
        assert result.quality_audit is None
    
    def test_to_dict_minimal(self):
        """Should serialize to dict with minimal data."""
        from nifti_handler import NIfTIConversionResult
        
        result = NIfTIConversionResult()
        result_dict = result.to_dict()
        
        assert isinstance(result_dict, dict)
        assert result_dict['success'] is False
        assert result_dict['mode'] == "unknown"
        assert result_dict['converted_count'] == 0
        assert result_dict['quality'] == "N/A"
    
    def test_to_dict_with_quality_audit(self, minimal_conversion_result):
        """Should include quality audit in dict."""
        result_dict = minimal_conversion_result.to_dict()
        
        assert result_dict['success'] is True
        assert result_dict['converted_count'] == 1
        assert "EXCELLENT" in result_dict['quality'] or "100" in result_dict['quality']


# ============================================================================
# TEST CLASS: NiftiConverter - Input Validation
# ============================================================================

class TestNiftiConverterValidation:
    """Tests for NiftiConverter input validation."""
    
    def test_input_folder_not_found(self, tmp_path):
        """Should return failed result when input folder doesn't exist."""
        # Skip if nifti libs not available
        pytest.importorskip("dicom2nifti")
        
        from nifti_handler import NiftiConverter
        
        converter = NiftiConverter()
        result = converter.convert_to_nifti(
            "/nonexistent/path/to/dicoms",
            str(tmp_path / "output")
        )
        
        assert result.success is False
        assert result.mode == "failed"
        assert "not found" in result.error_message.lower()
    
    def test_no_dicom_files_found(self, tmp_path):
        """Should return failed result when no DICOM files in folder."""
        pytest.importorskip("dicom2nifti")
        
        from nifti_handler import NiftiConverter
        
        # Create empty input folder
        input_dir = tmp_path / "empty_input"
        input_dir.mkdir()
        
        converter = NiftiConverter()
        result = converter.convert_to_nifti(
            str(input_dir),
            str(tmp_path / "output")
        )
        
        assert result.success is False
        assert result.mode == "failed"
        assert "no dicom" in result.error_message.lower()
    
    def test_creates_output_directory(self, tmp_path):
        """Should create output directory if it doesn't exist."""
        pytest.importorskip("dicom2nifti")
        
        from nifti_handler import NiftiConverter
        
        # Empty input - will fail, but output dir should still be created
        input_dir = tmp_path / "input"
        input_dir.mkdir()
        output_dir = tmp_path / "nested" / "output"
        
        converter = NiftiConverter()
        converter.convert_to_nifti(str(input_dir), str(output_dir))
        
        assert output_dir.exists()


# ============================================================================
# TEST CLASS: NiftiConverter - _find_dicom_files
# ============================================================================

class TestFindDicomFiles:
    """Tests for NiftiConverter._find_dicom_files() method."""
    
    def test_finds_dicom_by_magic_bytes(self, tmp_path):
        """Should find DICOM files by DICM magic bytes at offset 128."""
        pytest.importorskip("dicom2nifti")
        
        from nifti_handler import NiftiConverter
        
        # Create file with DICM magic bytes
        dicom_file = tmp_path / "test.dcm"
        with open(dicom_file, 'wb') as f:
            f.write(b'\x00' * 128)  # Preamble
            f.write(b'DICM')        # Magic bytes
            f.write(b'\x00' * 100)  # Some data
        
        converter = NiftiConverter()
        files = converter._find_dicom_files(str(tmp_path))
        
        assert len(files) == 1
        assert str(dicom_file) in files[0]
    
    def test_ignores_hidden_files(self, tmp_path):
        """Should ignore files starting with dot."""
        pytest.importorskip("dicom2nifti")
        
        from nifti_handler import NiftiConverter
        
        # Create hidden file with DICM magic
        hidden_file = tmp_path / ".hidden.dcm"
        with open(hidden_file, 'wb') as f:
            f.write(b'\x00' * 128 + b'DICM' + b'\x00' * 100)
        
        converter = NiftiConverter()
        files = converter._find_dicom_files(str(tmp_path))
        
        assert len(files) == 0
    
    def test_recursive_search(self, tmp_path):
        """Should find DICOM files in subdirectories."""
        pytest.importorskip("dicom2nifti")
        
        from nifti_handler import NiftiConverter
        
        # Create nested structure
        subdir = tmp_path / "subdir" / "nested"
        subdir.mkdir(parents=True)
        
        dicom_file = subdir / "image.dcm"
        with open(dicom_file, 'wb') as f:
            f.write(b'\x00' * 128 + b'DICM' + b'\x00' * 100)
        
        converter = NiftiConverter()
        files = converter._find_dicom_files(str(tmp_path))
        
        assert len(files) == 1


# ============================================================================
# TEST CLASS: NiftiConverter - _count_total_frames
# ============================================================================

class TestCountTotalFrames:
    """Tests for NiftiConverter._count_total_frames() method."""
    
    def test_counts_single_frame_files(self, tmp_path):
        """Should count single-frame DICOMs as 1 frame each."""
        pytest.importorskip("dicom2nifti")
        
        from nifti_handler import NiftiConverter
        import pydicom
        from pydicom.dataset import Dataset, FileDataset
        from pydicom.uid import ExplicitVRLittleEndian
        
        # Create minimal DICOM
        filepath = str(tmp_path / "test.dcm")
        file_meta = Dataset()
        file_meta.MediaStorageSOPClassUID = pydicom.uid.CTImageStorage
        file_meta.MediaStorageSOPInstanceUID = pydicom.uid.generate_uid()
        file_meta.TransferSyntaxUID = ExplicitVRLittleEndian
        
        ds = FileDataset(filepath, {}, file_meta=file_meta, preamble=b"\0" * 128)
        ds.Modality = "CT"
        ds.SOPInstanceUID = file_meta.MediaStorageSOPInstanceUID
        ds.SOPClassUID = file_meta.MediaStorageSOPClassUID
        ds.save_as(filepath, write_like_original=False)
        
        converter = NiftiConverter()
        count = converter._count_total_frames([filepath])
        
        assert count == 1
    
    def test_handles_exception_gracefully(self, tmp_path):
        """Should return 1 frame on exception (fallback)."""
        pytest.importorskip("dicom2nifti")
        
        from nifti_handler import NiftiConverter
        
        # Create invalid file
        bad_file = tmp_path / "bad.dcm"
        bad_file.write_text("not a dicom")
        
        converter = NiftiConverter()
        count = converter._count_total_frames([str(bad_file)])
        
        # Should fall back to 1
        assert count == 1


# ============================================================================
# TEST CLASS: NiftiConverter - _count_nifti_slices
# ============================================================================

class TestCountNiftiSlices:
    """Tests for NiftiConverter._count_nifti_slices() method."""
    
    def test_counts_3d_volume_slices(self, tmp_path):
        """Should count third dimension as slices for 3D volumes."""
        pytest.importorskip("dicom2nifti")
        nib = pytest.importorskip("nibabel")
        
        from nifti_handler import NiftiConverter
        
        # Create 3D NIfTI (10x10x20 = 20 slices)
        data = np.zeros((10, 10, 20), dtype=np.float32)
        img = nib.Nifti1Image(data, np.eye(4))
        nifti_path = str(tmp_path / "test.nii.gz")
        nib.save(img, nifti_path)
        
        converter = NiftiConverter()
        count = converter._count_nifti_slices([nifti_path])
        
        assert count == 20
    
    def test_counts_4d_volume_slices(self, tmp_path):
        """Should count slices * frames for 4D volumes."""
        pytest.importorskip("dicom2nifti")
        nib = pytest.importorskip("nibabel")
        
        from nifti_handler import NiftiConverter
        
        # Create 4D NIfTI (10x10x20x5 = 20*5=100 slices)
        data = np.zeros((10, 10, 20, 5), dtype=np.float32)
        img = nib.Nifti1Image(data, np.eye(4))
        nifti_path = str(tmp_path / "test_4d.nii.gz")
        nib.save(img, nifti_path)
        
        converter = NiftiConverter()
        count = converter._count_nifti_slices([nifti_path])
        
        assert count == 100  # 20 * 5
    
    def test_handles_load_exception(self, tmp_path):
        """Should return 1 on exception (fallback)."""
        pytest.importorskip("dicom2nifti")
        
        from nifti_handler import NiftiConverter
        
        # Create invalid file
        bad_file = tmp_path / "bad.nii.gz"
        bad_file.write_text("not a nifti")
        
        converter = NiftiConverter()
        count = converter._count_nifti_slices([str(bad_file)])
        
        assert count == 1


# ============================================================================
# TEST CLASS: NiftiConverter - _configure_relaxed_settings
# ============================================================================

class TestConfigureRelaxedSettings:
    """Tests for NiftiConverter._configure_relaxed_settings() method."""
    
    def test_attribute_error_handled(self):
        """Should handle AttributeError when enable_resampling not available."""
        pytest.importorskip("dicom2nifti")
        
        from nifti_handler import NiftiConverter
        import nifti_handler
        
        # Mock nifti_settings to raise AttributeError on enable_resampling
        original_settings = nifti_handler.nifti_settings
        
        mock_settings = MagicMock()
        mock_settings.enable_resampling.side_effect = AttributeError("no resampling")
        
        with patch.object(nifti_handler, 'nifti_settings', mock_settings):
            # Should not raise - catches AttributeError internally
            converter = NiftiConverter()
            converter._configure_relaxed_settings()
        
        # Verify the other settings were still called
        mock_settings.disable_validate_slice_increment.assert_called()
        mock_settings.disable_validate_orientation.assert_called()


# ============================================================================
# TEST CLASS: convert_dataset_to_nifti (Convenience Function)
# ============================================================================

class TestConvertDatasetToNifti:
    """Tests for convert_dataset_to_nifti() convenience function."""
    
    def test_returns_conversion_result(self, tmp_path):
        """Should return NIfTIConversionResult object."""
        pytest.importorskip("dicom2nifti")
        
        from nifti_handler import convert_dataset_to_nifti, NIfTIConversionResult
        
        # Empty dirs - will fail but should return proper result
        input_dir = tmp_path / "input"
        input_dir.mkdir()
        output_dir = tmp_path / "output"
        
        result = convert_dataset_to_nifti(str(input_dir), str(output_dir))
        
        assert isinstance(result, NIfTIConversionResult)
        assert hasattr(result, 'success')
        assert hasattr(result, 'mode')
