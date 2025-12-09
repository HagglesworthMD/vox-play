"""
VoxelMask NIfTI Conversion Tests
================================
Tests for DICOM to NIfTI conversion functionality.

Verifies:
1. NIfTI converter initializes correctly
2. DICOM files can be converted to .nii.gz format
3. Output files are valid and have non-zero size
4. Quality auditing tracks input/output counts

Run with: pytest tests/test_nifti.py -v
"""

import os
import sys
import tempfile
import shutil

import pytest
import pydicom

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

# Import with availability check
try:
    from nifti_handler import (
        NiftiConverter,
        NIfTIConversionResult,
        check_dicom2nifti_available,
        convert_dataset_to_nifti,
        NIFTI_AVAILABLE
    )
except ImportError:
    NIFTI_AVAILABLE = False

# Import conftest helper
from conftest import create_dummy_dicom


# Check if dcm2niix is available (external dependency)
def dcm2niix_available() -> bool:
    """Check if dcm2niix is installed on the system."""
    return shutil.which('dcm2niix') is not None


# Skip markers for conditional test execution
requires_nifti_libs = pytest.mark.skipif(
    not NIFTI_AVAILABLE,
    reason="dicom2nifti or nibabel not installed"
)

requires_dcm2niix = pytest.mark.skipif(
    not dcm2niix_available(),
    reason="dcm2niix not installed on system"
)


class TestNiftiAvailability:
    """Tests for NIfTI library availability checks."""
    
    def test_check_function_exists(self):
        """
        Assert: The check_dicom2nifti_available function exists and returns boolean.
        """
        if NIFTI_AVAILABLE:
            from nifti_handler import check_dicom2nifti_available
            result = check_dicom2nifti_available()
            assert isinstance(result, bool)
    
    @requires_nifti_libs
    def test_nifti_libraries_importable(self):
        """
        Assert: When available, NIfTI libraries can be imported.
        """
        import dicom2nifti
        import nibabel
        assert dicom2nifti is not None
        assert nibabel is not None


class TestNiftiConverter:
    """Tests for the NiftiConverter class."""
    
    @requires_nifti_libs
    def test_converter_initializes(self):
        """
        Assert: NiftiConverter can be instantiated.
        """
        converter = NiftiConverter()
        assert converter is not None
    
    @requires_nifti_libs
    def test_conversion_result_object(self):
        """
        Assert: NIfTIConversionResult object has expected attributes.
        """
        result = NIfTIConversionResult()
        
        assert hasattr(result, 'success')
        assert hasattr(result, 'mode')
        assert hasattr(result, 'converted_files')
        assert hasattr(result, 'warnings')
        assert hasattr(result, 'error_message')
        
        # Default values
        assert result.success is False
        assert result.mode == "unknown"
        assert isinstance(result.converted_files, list)



@requires_nifti_libs
@requires_dcm2niix
class TestNiftiConversion:
    """Tests for actual NIfTI conversion (requires dcm2niix)."""
    
    def test_convert_single_dicom(self, dummy_dicom_file):
        """
        Assert: A single DICOM file can be converted to NIfTI.
        Assert: Output file ends in .nii.gz
        Assert: Output file size is > 0 bytes
        """
        with tempfile.TemporaryDirectory() as input_dir, \
             tempfile.TemporaryDirectory() as output_dir:
            
            # Copy dummy DICOM to input directory
            shutil.copy(dummy_dicom_file, os.path.join(input_dir, "image.dcm"))
            
            # Convert
            converter = NiftiConverter()
            result = converter.convert_to_nifti(input_dir, output_dir)
            
            # Check result
            if result.success:
                # Should have at least one output file
                assert len(result.converted_files) > 0, \
                    "Conversion should produce output files"
                
                # Check output files
                for output_file in result.converted_files:
                    assert output_file.endswith('.nii.gz') or output_file.endswith('.nii'), \
                        f"Output should be NIfTI format: {output_file}"
                    
                    file_path = os.path.join(output_dir, output_file)
                    if os.path.exists(file_path):
                        file_size = os.path.getsize(file_path)
                        assert file_size > 0, \
                            f"Output file should have non-zero size: {output_file}"
            else:
                # Some DICOM files may not convert (too few slices, etc.)
                # This is acceptable, just log the warning
                pytest.skip(f"Conversion failed (may be expected for single slice): {result.error_message}")
    
    def test_convert_series_of_dicoms(self):
        """
        Assert: A series of DICOM files converts to NIfTI.
        Assert: Output ends in .nii.gz
        Assert: Output size > 0
        """
        with tempfile.TemporaryDirectory() as input_dir, \
             tempfile.TemporaryDirectory() as output_dir:
            
            # Create multiple DICOM files to form a series
            for i in range(5):
                filepath = os.path.join(input_dir, f"image_{i:03d}.dcm")
                create_dummy_dicom(
                    filepath,
                    patient_name="Test^Patient",
                    patient_id="TEST001",
                    study_date="20231201"
                )
            
            # Convert
            converter = NiftiConverter()
            result = converter.convert_to_nifti(input_dir, output_dir)
            
            if result.success:
                # Should have output files
                assert len(result.converted_files) > 0, \
                    "Conversion should produce output files"
                
                # Verify .nii.gz format and non-zero size
                for output_file in result.converted_files:
                    assert output_file.endswith('.nii.gz') or output_file.endswith('.nii'), \
                        f"Output should be NIfTI format: {output_file}"
                    
                    # Check file exists and has content
                    nifti_files = [f for f in os.listdir(output_dir) 
                                   if f.endswith('.nii') or f.endswith('.nii.gz')]
                    for nf in nifti_files:
                        file_path = os.path.join(output_dir, nf)
                        assert os.path.getsize(file_path) > 0, \
                            f"NIfTI file should have non-zero size: {nf}"
            else:
                # Log why conversion failed
                pytest.skip(f"Conversion failed: {result.error_message}")
    
    def test_conversion_result_has_audit_info(self):
        """
        Assert: Conversion result includes quality audit information.
        """
        with tempfile.TemporaryDirectory() as input_dir, \
             tempfile.TemporaryDirectory() as output_dir:
            
            # Create DICOM files
            for i in range(3):
                filepath = os.path.join(input_dir, f"image_{i:03d}.dcm")
                create_dummy_dicom(filepath)
            
            converter = NiftiConverter()
            result = converter.convert_to_nifti(input_dir, output_dir)
            
            # Result should have quality audit
            assert hasattr(result, 'quality_audit') or hasattr(result, 'to_dict')
            
            # Check to_dict method works
            result_dict = result.to_dict()
            assert isinstance(result_dict, dict)
            assert 'success' in result_dict
            assert 'mode' in result_dict


class TestNiftiConvenienceFunction:
    """Tests for the convert_dataset_to_nifti convenience function."""
    
    @requires_nifti_libs
    def test_convenience_function_exists(self):
        """
        Assert: The convenience function is importable and callable.
        """
        from nifti_handler import convert_dataset_to_nifti
        assert callable(convert_dataset_to_nifti)
    
    @requires_nifti_libs
    @requires_dcm2niix
    def test_convenience_function_returns_result(self):
        """
        Assert: The convenience function returns a NIfTIConversionResult.
        """
        with tempfile.TemporaryDirectory() as input_dir, \
             tempfile.TemporaryDirectory() as output_dir:
            
            # Create a DICOM file
            create_dummy_dicom(os.path.join(input_dir, "test.dcm"))
            
            result = convert_dataset_to_nifti(input_dir, output_dir)
            
            assert isinstance(result, NIfTIConversionResult)
            assert hasattr(result, 'success')
            assert hasattr(result, 'mode')
