"""
Unit Tests for DICOM Anonymizer

Tests HIPAA Safe Harbor and DICOM PS3.15 compliance.
"""

import hashlib
import os
import tempfile
import shutil
from pathlib import Path
from typing import Optional

import pytest
import pydicom
from pydicom.dataset import Dataset, FileDataset
from pydicom.uid import generate_uid, ExplicitVRLittleEndian
import numpy as np

# Add parent to path for imports
import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from research_mode.anonymizer import DicomAnonymizer, AnonymizationConfig
from research_mode.audit import ComplianceReportGenerator
from research_mode.whitelist import (
    SAFE_TAGS, PHI_TAGS, is_private_tag, is_tag_safe
)


# ═══════════════════════════════════════════════════════════════════════════════
# TEST FIXTURES
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.fixture
def sample_dicom_path():
    """Path to the sample DICOM file."""
    # Try multiple possible locations
    possible_paths = [
        Path("/home/deck/CascadeProjects/splitwise/fixed_patient.dcm"),
        Path("/home/deck/CascadeProjects/splitwise/I3200000_fixed.dcm"),
        Path(__file__).parent.parent.parent.parent / "fixed_patient.dcm",
    ]
    
    for path in possible_paths:
        if path.exists():
            return path
    
    pytest.skip("Sample DICOM file not found")


@pytest.fixture
def temp_output_dir():
    """Create a temporary directory for test outputs."""
    temp_dir = tempfile.mkdtemp()
    yield Path(temp_dir)
    shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.fixture
def anonymizer():
    """Create an anonymizer with default config."""
    config = AnonymizationConfig(
        secret_salt=b"test_salt_for_reproducible_tests",
        date_shift_range=(-30, -15),
    )
    return DicomAnonymizer(config)


@pytest.fixture
def create_test_dicom(temp_output_dir):
    """Factory fixture to create test DICOM files."""
    
    def _create(
        patient_name: str = "DOE^JOHN",
        patient_id: str = "12345",
        study_date: str = "20231215",
        add_phi: bool = True,
        add_private_tags: bool = True,
        pixel_data: Optional[np.ndarray] = None,
    ) -> Path:
        """Create a test DICOM file with specified attributes."""
        
        # Create file meta
        file_meta = pydicom.Dataset()
        file_meta.MediaStorageSOPClassUID = "1.2.840.10008.5.1.4.1.1.2"
        file_meta.MediaStorageSOPInstanceUID = generate_uid()
        file_meta.TransferSyntaxUID = ExplicitVRLittleEndian
        file_meta.ImplementationClassUID = "1.2.3.4.5.6.7.8.9"
        
        # Create dataset
        ds = FileDataset(
            None, {}, file_meta=file_meta, preamble=b"\0" * 128
        )
        
        # Required SOP tags
        ds.SOPClassUID = file_meta.MediaStorageSOPClassUID
        ds.SOPInstanceUID = file_meta.MediaStorageSOPInstanceUID
        
        # Study/Series UIDs
        ds.StudyInstanceUID = generate_uid()
        ds.SeriesInstanceUID = generate_uid()
        
        # Dates
        ds.StudyDate = study_date
        ds.SeriesDate = study_date
        ds.ContentDate = study_date
        ds.StudyTime = "120000"
        
        # Modality
        ds.Modality = "CT"
        
        # Image parameters
        ds.Rows = 64
        ds.Columns = 64
        ds.BitsAllocated = 16
        ds.BitsStored = 12
        ds.HighBit = 11
        ds.PixelRepresentation = 0
        ds.SamplesPerPixel = 1
        ds.PhotometricInterpretation = "MONOCHROME2"
        
        # Pixel data
        if pixel_data is None:
            pixel_data = np.random.randint(0, 4096, (64, 64), dtype=np.uint16)
        ds.PixelData = pixel_data.tobytes()
        
        if add_phi:
            # Patient identification (PHI)
            ds.PatientName = patient_name
            ds.PatientID = patient_id
            ds.PatientBirthDate = "19800115"
            ds.PatientSex = "M"
            ds.PatientAge = "043Y"
            ds.PatientAddress = "123 Main St, City, ST 12345"
            ds.PatientTelephoneNumbers = "555-123-4567"
            
            # Institution (PHI)
            ds.InstitutionName = "Test Hospital"
            ds.InstitutionAddress = "456 Hospital Ave"
            ds.ReferringPhysicianName = "SMITH^JANE^DR"
            ds.PerformingPhysicianName = "JONES^BOB^DR"
            ds.OperatorsName = "TECH^MARY"
            
            # Other identifiers
            ds.AccessionNumber = "ACC123456"
            ds.StationName = "CT_SCANNER_1"
            
            # Comments with embedded PHI
            ds.PatientComments = "Patient John Doe, SSN 123-45-6789, MRN: 12345"
            ds.StudyDescription = "CT Abdomen for Dr. Smith, patient DOE"
        
        if add_private_tags:
            # Add private tags (odd group numbers)
            ds.add_new((0x0011, 0x0010), 'LO', 'Private Creator')
            ds.add_new((0x0011, 0x1001), 'LO', 'Private Data Value')
        
        # Save to temp file
        output_path = temp_output_dir / f"test_{generate_uid()[-8:]}.dcm"
        ds.save_as(str(output_path))
        
        return output_path
    
    return _create


# ═══════════════════════════════════════════════════════════════════════════════
# CORE ANONYMIZATION TESTS
# ═══════════════════════════════════════════════════════════════════════════════

class TestPatientNameAnonymization:
    """Tests for patient name anonymization."""
    
    def test_patient_name_is_anonymized(self, create_test_dicom, anonymizer, temp_output_dir):
        """Assert that PatientName is empty or 'ANONYMIZED'."""
        # Create test file
        input_path = create_test_dicom(patient_name="JONES^JOHN^MR")
        output_path = temp_output_dir / "anonymized.dcm"
        
        # Anonymize
        result = anonymizer.anonymize_file(input_path, output_path)
        
        # Verify
        assert result.success, f"Anonymization failed: {result.error_message}"
        
        ds = pydicom.dcmread(str(output_path))
        patient_name = str(getattr(ds, 'PatientName', ''))
        
        assert patient_name in ['', 'ANONYMIZED'], \
            f"PatientName should be empty or 'ANONYMIZED', got: {patient_name}"
    
    def test_patient_name_with_real_file(self, sample_dicom_path, anonymizer, temp_output_dir):
        """Test with the provided sample DICOM file."""
        output_path = temp_output_dir / "anonymized_sample.dcm"
        
        # Get original patient name
        original_ds = pydicom.dcmread(str(sample_dicom_path))
        original_name = str(getattr(original_ds, 'PatientName', 'UNKNOWN'))
        
        # Anonymize
        result = anonymizer.anonymize_file(sample_dicom_path, output_path)
        
        assert result.success, f"Anonymization failed: {result.error_message}"
        
        # Verify patient name is anonymized
        ds = pydicom.dcmread(str(output_path))
        new_name = str(getattr(ds, 'PatientName', ''))
        
        assert new_name in ['', 'ANONYMIZED'], \
            f"PatientName should be empty or 'ANONYMIZED', got: {new_name}"
        assert new_name != original_name, \
            "PatientName should be different from original"


class TestUIDRemapping:
    """Tests for UID remapping with HMAC-SHA256."""
    
    def test_study_instance_uid_is_different(self, create_test_dicom, anonymizer, temp_output_dir):
        """Assert that the original StudyInstanceUID is different from the new one."""
        input_path = create_test_dicom()
        output_path = temp_output_dir / "anonymized.dcm"
        
        # Get original UID
        original_ds = pydicom.dcmread(str(input_path))
        original_uid = str(original_ds.StudyInstanceUID)
        
        # Anonymize
        result = anonymizer.anonymize_file(input_path, output_path)
        
        assert result.success
        
        # Verify UID is different
        ds = pydicom.dcmread(str(output_path))
        new_uid = str(ds.StudyInstanceUID)
        
        assert new_uid != original_uid, \
            "StudyInstanceUID should be different after anonymization"
    
    def test_uid_remapping_is_stable(self, create_test_dicom, temp_output_dir):
        """Same input UID should always produce same output UID."""
        # Create two anonymizers with same salt
        config = AnonymizationConfig(secret_salt=b"stable_test_salt")
        anonymizer1 = DicomAnonymizer(config)
        anonymizer2 = DicomAnonymizer(config)
        
        input_path = create_test_dicom()
        output_path1 = temp_output_dir / "anon1.dcm"
        output_path2 = temp_output_dir / "anon2.dcm"
        
        # Get original UID
        original_ds = pydicom.dcmread(str(input_path))
        original_uid = str(original_ds.StudyInstanceUID)
        
        # Anonymize twice
        anonymizer1.anonymize_file(input_path, output_path1)
        anonymizer2.anonymize_file(input_path, output_path2)
        
        # Both should produce same remapped UID
        ds1 = pydicom.dcmread(str(output_path1))
        ds2 = pydicom.dcmread(str(output_path2))
        
        assert str(ds1.StudyInstanceUID) == str(ds2.StudyInstanceUID), \
            "Same input with same salt should produce same output UID"
    
    def test_uid_remapping_with_real_file(self, sample_dicom_path, anonymizer, temp_output_dir):
        """Test UID remapping with the provided sample file."""
        output_path = temp_output_dir / "anonymized_sample.dcm"
        
        # Get original UID
        original_ds = pydicom.dcmread(str(sample_dicom_path))
        original_uid = str(original_ds.StudyInstanceUID)
        
        # Anonymize
        result = anonymizer.anonymize_file(sample_dicom_path, output_path)
        
        assert result.success
        assert original_uid in result.uids_remapped, \
            "Original StudyInstanceUID should be in remapped UIDs"
        
        # Verify in file
        ds = pydicom.dcmread(str(output_path))
        assert str(ds.StudyInstanceUID) != original_uid


class TestPixelDataIntegrity:
    """Tests for pixel data integrity preservation."""
    
    def test_pixel_data_not_corrupted(self, create_test_dicom, anonymizer, temp_output_dir):
        """Assert that Pixel Data has not been corrupted."""
        # Create test file with known pixel data
        pixel_data = np.arange(64 * 64, dtype=np.uint16).reshape(64, 64)
        input_path = create_test_dicom(pixel_data=pixel_data)
        output_path = temp_output_dir / "anonymized.dcm"
        
        # Get original pixel hash
        original_ds = pydicom.dcmread(str(input_path))
        original_hash = hashlib.sha256(original_ds.PixelData).hexdigest()
        
        # Anonymize
        result = anonymizer.anonymize_file(input_path, output_path)
        
        assert result.success
        assert result.pixel_data_preserved, "Pixel data should be preserved"
        
        # Verify pixel data
        ds = pydicom.dcmread(str(output_path))
        new_hash = hashlib.sha256(ds.PixelData).hexdigest()
        
        assert new_hash == original_hash, \
            "Pixel data hash should match after anonymization"
    
    def test_pixel_data_integrity_with_real_file(self, sample_dicom_path, temp_output_dir):
        """Test pixel data integrity with the provided sample file.
        
        Note: For US modality, pixel masking is applied by default, so we need
        to disable it to test pure pixel data preservation.
        """
        # Disable pixel masking to test pure integrity
        config = AnonymizationConfig(
            secret_salt=b"integrity_test_salt",
            enable_pixel_masking=False,  # Disable masking for this test
        )
        anonymizer = DicomAnonymizer(config)
        
        output_path = temp_output_dir / "anonymized_sample.dcm"
        
        # Get original pixel hash
        original_ds = pydicom.dcmread(str(sample_dicom_path))
        if hasattr(original_ds, 'PixelData'):
            original_hash = hashlib.sha256(original_ds.PixelData).hexdigest()
        else:
            pytest.skip("Sample file has no PixelData")
        
        # Anonymize
        result = anonymizer.anonymize_file(sample_dicom_path, output_path)
        
        assert result.success
        assert result.original_pixel_hash == original_hash
        assert result.anonymized_pixel_hash == original_hash
        assert result.pixel_data_preserved


class TestPrivateTagRemoval:
    """Tests for private tag removal."""
    
    def test_private_tags_removed(self, create_test_dicom, anonymizer, temp_output_dir):
        """Private tags (odd group numbers) should be removed."""
        input_path = create_test_dicom(add_private_tags=True)
        output_path = temp_output_dir / "anonymized.dcm"
        
        # Verify private tags exist in original
        original_ds = pydicom.dcmread(str(input_path))
        has_private = any(
            elem.tag.group % 2 == 1 
            for elem in original_ds 
            if elem.tag.group > 0x0008
        )
        assert has_private, "Test file should have private tags"
        
        # Anonymize
        result = anonymizer.anonymize_file(input_path, output_path)
        
        assert result.success
        assert len(result.private_tags_removed) > 0, \
            "Should have removed private tags"
        
        # Verify no private tags remain
        ds = pydicom.dcmread(str(output_path))
        remaining_private = [
            elem.tag for elem in ds 
            if elem.tag.group % 2 == 1 and elem.tag.group > 0x0008
        ]
        assert len(remaining_private) == 0, \
            f"Private tags should be removed: {remaining_private}"


class TestDateShifting:
    """Tests for date shifting."""
    
    def test_dates_are_shifted(self, create_test_dicom, anonymizer, temp_output_dir):
        """Dates should be shifted by a consistent offset."""
        input_path = create_test_dicom(study_date="20231215")
        output_path = temp_output_dir / "anonymized.dcm"
        
        # Anonymize
        result = anonymizer.anonymize_file(input_path, output_path)
        
        assert result.success
        assert result.date_shift_days != 0, "Date shift should be applied"
        assert len(result.dates_shifted) > 0, "Should have shifted dates"
        
        # Verify dates are different
        ds = pydicom.dcmread(str(output_path))
        assert str(ds.StudyDate) != "20231215", \
            "StudyDate should be shifted"
    
    def test_date_shift_preserves_intervals(self, create_test_dicom, anonymizer, temp_output_dir):
        """All dates in a study should be shifted by the same amount."""
        input_path = create_test_dicom(study_date="20231215")
        output_path = temp_output_dir / "anonymized.dcm"
        
        # Anonymize
        result = anonymizer.anonymize_file(input_path, output_path)
        
        assert result.success
        
        # All dates should be shifted by the same amount
        shift = result.date_shift_days
        for tag, (original, shifted) in result.dates_shifted.items():
            if original and shifted:
                # Calculate actual shift
                from datetime import datetime
                orig_date = datetime.strptime(original, "%Y%m%d")
                new_date = datetime.strptime(shifted, "%Y%m%d")
                actual_shift = (new_date - orig_date).days
                assert actual_shift == shift, \
                    f"All dates should be shifted by {shift} days"


class TestTextScrubbing:
    """Tests for PHI pattern scrubbing in text fields."""
    
    def test_ssn_pattern_scrubbed(self, create_test_dicom, anonymizer, temp_output_dir):
        """SSN patterns should be scrubbed from text fields."""
        input_path = create_test_dicom()
        output_path = temp_output_dir / "anonymized.dcm"
        
        # Anonymize
        result = anonymizer.anonymize_file(input_path, output_path)
        
        assert result.success
        
        # PatientComments should be removed (it's PHI)
        ds = pydicom.dcmread(str(output_path))
        
        # Check that SSN pattern is not in any remaining text
        for elem in ds:
            if elem.VR in ['LO', 'SH', 'LT', 'ST', 'UT']:
                value = str(elem.value)
                assert '123-45-6789' not in value, \
                    f"SSN pattern found in {elem.keyword}"


class TestWhitelistArchitecture:
    """Tests for the whitelist-based tag filtering."""
    
    def test_only_whitelisted_tags_remain(self, create_test_dicom, anonymizer, temp_output_dir):
        """Only whitelisted tags should remain after anonymization."""
        input_path = create_test_dicom(add_phi=True, add_private_tags=True)
        output_path = temp_output_dir / "anonymized.dcm"
        
        # Anonymize
        result = anonymizer.anonymize_file(input_path, output_path)
        
        assert result.success
        
        # Check all remaining tags are on whitelist or are special cases
        ds = pydicom.dcmread(str(output_path))
        
        for elem in ds:
            tag = (elem.tag.group, elem.tag.element)
            
            # Skip file meta tags
            if elem.tag.group == 0x0002:
                continue
            
            # Tag should be on safe list or be a special case
            is_safe = is_tag_safe(tag)
            is_patient_name = tag == (0x0010, 0x0010)  # Anonymized, not removed
            is_patient_id = tag == (0x0010, 0x0020)    # Anonymized, not removed
            is_patient_sex = tag == (0x0010, 0x0040)   # Optionally kept
            
            assert is_safe or is_patient_name or is_patient_id or is_patient_sex, \
                f"Unexpected tag remaining: {elem.tag} {elem.keyword}"
    
    def test_phi_tags_removed(self, create_test_dicom, anonymizer, temp_output_dir):
        """PHI tags should be removed or anonymized."""
        input_path = create_test_dicom(add_phi=True)
        output_path = temp_output_dir / "anonymized.dcm"
        
        # Anonymize
        result = anonymizer.anonymize_file(input_path, output_path)
        
        assert result.success
        
        ds = pydicom.dcmread(str(output_path))
        
        # These PHI tags should be removed
        removed_tags = [
            (0x0010, 0x0030),  # PatientBirthDate
            (0x0010, 0x1040),  # PatientAddress
            (0x0010, 0x2154),  # PatientTelephoneNumbers
            (0x0008, 0x0080),  # InstitutionName
            (0x0008, 0x0090),  # ReferringPhysicianName
            (0x0008, 0x1050),  # PerformingPhysicianName
            (0x0008, 0x1070),  # OperatorsName
        ]
        
        for tag in removed_tags:
            assert tag not in ds, \
                f"PHI tag {tag} should be removed"


class TestComplianceReport:
    """Tests for compliance report generation."""
    
    def test_report_generation(self, create_test_dicom, anonymizer, temp_output_dir):
        """Compliance report should be generated correctly."""
        input_path = create_test_dicom()
        output_path = temp_output_dir / "anonymized.dcm"
        
        # Anonymize
        result = anonymizer.anonymize_file(input_path, output_path)
        
        # Generate report
        generator = ComplianceReportGenerator()
        generator.add_result(result)
        
        report_path = temp_output_dir / "compliance_report.json"
        report = generator.save_report(report_path)
        
        assert report_path.exists()
        assert report.total_files_processed == 1
        assert report.successful_files == 1
        assert report.all_pixel_data_preserved
        
        # Verify JSON structure
        import json
        with open(report_path) as f:
            report_json = json.load(f)
        
        assert "report_metadata" in report_json
        assert "compliance_standards" in report_json
        assert "processing_summary" in report_json
        assert "file_entries" in report_json
        assert len(report_json["file_entries"]) == 1


class TestBatchProcessing:
    """Tests for batch processing."""
    
    def test_batch_anonymization(self, create_test_dicom, anonymizer, temp_output_dir):
        """Batch processing should handle multiple files."""
        # Create multiple test files
        input_paths = [
            create_test_dicom(patient_name=f"PATIENT^{i}")
            for i in range(3)
        ]
        
        output_dir = temp_output_dir / "batch_output"
        output_dir.mkdir()
        
        # Anonymize batch
        results = anonymizer.anonymize_batch(input_paths, output_dir)
        
        assert len(results) == 3
        assert all(r.success for r in results)
        
        # Verify all output files exist
        for input_path in input_paths:
            output_path = output_dir / input_path.name
            assert output_path.exists()


# ═══════════════════════════════════════════════════════════════════════════════
# INTEGRATION TEST WITH REAL FILE
# ═══════════════════════════════════════════════════════════════════════════════

class TestRealFileIntegration:
    """Integration tests with the provided sample DICOM file."""
    
    def test_full_anonymization_workflow(self, sample_dicom_path, temp_output_dir):
        """Full workflow test with real file."""
        # Configure anonymizer
        config = AnonymizationConfig(
            secret_salt=b"integration_test_salt",
            date_shift_range=(-30, -15),
            keep_patient_sex=True,
        )
        anonymizer = DicomAnonymizer(config)
        
        output_path = temp_output_dir / "anonymized_integration.dcm"
        
        # Read original
        original_ds = pydicom.dcmread(str(sample_dicom_path))
        original_name = str(getattr(original_ds, 'PatientName', ''))
        original_uid = str(original_ds.StudyInstanceUID)
        original_pixel_hash = None
        if hasattr(original_ds, 'PixelData'):
            original_pixel_hash = hashlib.sha256(original_ds.PixelData).hexdigest()
        
        # Anonymize
        result = anonymizer.anonymize_file(sample_dicom_path, output_path)
        
        # Assertions
        assert result.success, f"Failed: {result.error_message}"
        
        # Read anonymized
        ds = pydicom.dcmread(str(output_path))
        
        # 1. PatientName is empty or "ANONYMIZED"
        new_name = str(getattr(ds, 'PatientName', ''))
        assert new_name in ['', 'ANONYMIZED'], \
            f"PatientName should be anonymized, got: {new_name}"
        
        # 2. StudyInstanceUID is different
        new_uid = str(ds.StudyInstanceUID)
        assert new_uid != original_uid, \
            "StudyInstanceUID should be remapped"
        
        # 3. Pixel data - for US modality with masking enabled, hash will differ
        #    For non-US modalities, hash should be preserved
        modality = str(getattr(original_ds, 'Modality', '')).upper()
        if original_pixel_hash:
            new_pixel_hash = hashlib.sha256(ds.PixelData).hexdigest()
            if modality in {'US', 'SC', 'OT'}:
                # Masking should have been applied
                assert new_pixel_hash != original_pixel_hash, \
                    f"Pixel data should be modified for {modality} modality"
                assert result.pixel_data_modified, \
                    "pixel_data_modified should be True for masked modalities"
            else:
                assert new_pixel_hash == original_pixel_hash, \
                    "Pixel data should be preserved for non-masked modalities"
        
        # Generate compliance report
        generator = ComplianceReportGenerator()
        generator.add_result(result, "anonymized_integration.dcm")
        
        report_path = temp_output_dir / "compliance_report.json"
        report = generator.save_report(
            report_path,
            config_dict={
                "date_shift_range": config.date_shift_range,
                "keep_patient_sex": config.keep_patient_sex,
            }
        )
        
        assert report_path.exists()
        # For US modality, pixel data is modified (masked), so all_pixel_data_preserved is False
        # But all_pixel_clean should be True (masking was successful)
        if modality in {'US', 'SC', 'OT'}:
            assert not report.all_pixel_data_preserved, \
                "Pixel data should be modified for masked modalities"
            assert report.all_pixel_clean, \
                "All files should be pixel clean after masking"
            assert report.files_with_pixel_masking == 1
        else:
            assert report.all_pixel_data_preserved


# ═══════════════════════════════════════════════════════════════════════════════
# PIXEL MASKING TESTS
# ═══════════════════════════════════════════════════════════════════════════════

class TestPixelMasking:
    """Tests for pixel masking functionality."""
    
    def test_ultrasound_triggers_masking(self, sample_dicom_path, temp_output_dir):
        """
        Test that Ultrasound (US) modality triggers pixel masking.
        The sample file fixed_patient.dcm is an ultrasound.
        """
        # Configure anonymizer with pixel masking enabled
        config = AnonymizationConfig(
            secret_salt=b"pixel_mask_test_salt",
            enable_pixel_masking=True,
            pixel_mask_modalities={'US', 'SC', 'OT'},
            pixel_mask_top_fraction=0.10,
        )
        anonymizer = DicomAnonymizer(config)
        
        output_path = temp_output_dir / "masked_ultrasound.dcm"
        
        # Get original pixel hash
        original_ds = pydicom.dcmread(str(sample_dicom_path))
        original_hash = hashlib.sha256(original_ds.PixelData).hexdigest()
        
        # Verify it's an ultrasound
        modality = str(getattr(original_ds, 'Modality', '')).upper()
        assert modality == 'US', f"Expected US modality, got {modality}"
        
        # Anonymize with masking
        result = anonymizer.anonymize_file(sample_dicom_path, output_path)
        
        assert result.success, f"Anonymization failed: {result.error_message}"
        
        # Verify masking was triggered
        assert result.pixel_mask_triggered_by == 'US', \
            f"Expected masking triggered by US, got {result.pixel_mask_triggered_by}"
        assert result.pixel_data_modified, "Pixel data should be modified"
        assert result.pixel_clean, "Pixel should be marked as clean after masking"
        
        # Verify pixel hash is DIFFERENT (masking occurred)
        new_ds = pydicom.dcmread(str(output_path))
        new_hash = hashlib.sha256(new_ds.PixelData).hexdigest()
        
        assert new_hash != original_hash, \
            "Pixel hash should be different after masking for Ultrasound files"
    
    def test_top_rows_are_masked(self, sample_dicom_path, temp_output_dir):
        """
        Assert that the top rows of pixels in the masked file are all zeros.
        """
        config = AnonymizationConfig(
            secret_salt=b"top_row_test_salt",
            enable_pixel_masking=True,
            pixel_mask_modalities={'US', 'SC', 'OT'},
            pixel_mask_top_fraction=0.10,
            pixel_mask_value=0,
        )
        anonymizer = DicomAnonymizer(config)
        
        output_path = temp_output_dir / "masked_top_rows.dcm"
        
        # Anonymize
        result = anonymizer.anonymize_file(sample_dicom_path, output_path)
        
        assert result.success
        assert result.pixel_data_modified
        
        # Read the masked file and check top rows
        ds = pydicom.dcmread(str(output_path))
        pixel_array = ds.pixel_array
        
        # Get the number of rows that should be masked
        if len(pixel_array.shape) == 2:
            rows = pixel_array.shape[0]
        elif len(pixel_array.shape) == 3:
            if pixel_array.shape[2] in [3, 4]:  # RGB
                rows = pixel_array.shape[0]
            else:  # Multi-frame
                rows = pixel_array.shape[1]
        elif len(pixel_array.shape) == 4:  # Multi-frame RGB
            rows = pixel_array.shape[1]
        else:
            pytest.fail(f"Unexpected pixel array shape: {pixel_array.shape}")
        
        top_mask_rows = int(rows * 0.10)
        
        # Check that top rows are all zeros
        if len(pixel_array.shape) == 2:
            top_region = pixel_array[:top_mask_rows, :]
        elif len(pixel_array.shape) == 3:
            if pixel_array.shape[2] in [3, 4]:
                top_region = pixel_array[:top_mask_rows, :, :]
            else:
                top_region = pixel_array[:, :top_mask_rows, :]
        elif len(pixel_array.shape) == 4:
            top_region = pixel_array[:, :top_mask_rows, :, :]
        
        assert np.all(top_region == 0), \
            f"Top {top_mask_rows} rows should be all zeros (masked)"
    
    def test_pixel_hash_different_for_ultrasound(self, sample_dicom_path, temp_output_dir):
        """
        For Ultrasound files, the original_pixel_hash and anonymized_pixel_hash
        MUST be different. If they are the same, masking failed.
        """
        config = AnonymizationConfig(
            secret_salt=b"hash_diff_test_salt",
            enable_pixel_masking=True,
            pixel_mask_modalities={'US', 'SC', 'OT'},
            pixel_mask_top_fraction=0.10,
        )
        anonymizer = DicomAnonymizer(config)
        
        output_path = temp_output_dir / "hash_test.dcm"
        
        result = anonymizer.anonymize_file(sample_dicom_path, output_path)
        
        assert result.success
        assert result.original_pixel_hash is not None
        assert result.anonymized_pixel_hash is not None
        assert result.original_pixel_hash != result.anonymized_pixel_hash, \
            "For Ultrasound, pixel hashes MUST be different after masking"
        
        # Verify no warning about masking failure
        assert result.pixel_mask_warning is None, \
            f"Should not have masking warning: {result.pixel_mask_warning}"
    
    def test_non_ultrasound_no_masking(self, create_test_dicom, anonymizer, temp_output_dir):
        """
        Non-US/SC/OT modalities should NOT have pixel masking applied.
        """
        # Create a CT test file (not in mask modalities)
        input_path = create_test_dicom()
        
        # Modify to be CT modality
        ds = pydicom.dcmread(str(input_path))
        ds.Modality = 'CT'
        ds.save_as(str(input_path))
        
        output_path = temp_output_dir / "ct_no_mask.dcm"
        
        # Get original hash
        original_ds = pydicom.dcmread(str(input_path))
        original_hash = hashlib.sha256(original_ds.PixelData).hexdigest()
        
        # Anonymize
        result = anonymizer.anonymize_file(input_path, output_path)
        
        assert result.success
        assert not result.pixel_data_modified, "CT should not have pixel masking"
        assert result.pixel_mask_triggered_by is None
        
        # Pixel hash should be preserved
        new_ds = pydicom.dcmread(str(output_path))
        new_hash = hashlib.sha256(new_ds.PixelData).hexdigest()
        assert new_hash == original_hash, "CT pixel data should be preserved"
    
    def test_ct_presentation_tags_preserved(self, create_test_dicom, temp_output_dir):
        """
        Test that critical CT image presentation tags are preserved during anonymization.
        These tags are essential for mapping raw pixel values to Hounsfield Units.
        """
        config = AnonymizationConfig(
            secret_salt=b"ct_presentation_test_salt",
            enable_pixel_masking=False,  # Disable to focus on tag preservation
        )
        anonymizer = DicomAnonymizer(config)
        
        # Create a CT test file with presentation tags
        pixel_data = np.random.randint(0, 4096, (64, 64), dtype=np.uint16)
        ct_path = create_test_dicom(pixel_data=pixel_data)
        
        # Add critical CT presentation tags
        ct_ds = pydicom.dcmread(str(ct_path))
        ct_ds.Modality = 'CT'
        
        # Essential Hounsfield Unit mapping tags
        ct_ds.RescaleIntercept = -1024  # Critical for HU conversion
        ct_ds.RescaleSlope = 1.0        # Critical for HU conversion
        ct_ds.RescaleType = 'HU'
        
        # Window/Level settings
        ct_ds.WindowCenter = 40.0
        ct_ds.WindowWidth = 400.0
        ct_ds.WindowCenterWidthExplanation = 'Soft Tissue'
        
        # Additional VOI LUT tags
        ct_ds.VOILUTFunction = 'LINEAR'
        
        # CT acquisition parameters
        ct_ds.ConvolutionKernel = 'STANDARD'
        ct_ds.KVP = 120
        ct_ds.XRayTubeCurrent = 200
        ct_ds.ExposureTime = 1000
        
        # Image geometry
        ct_ds.SliceThickness = 2.5
        ct_ds.SliceLocation = 100.5
        ct_ds.ImagePositionPatient = [-100.0, -50.0, 100.5]
        ct_ds.ImageOrientationPatient = [1.0, 0.0, 0.0, 0.0, 1.0, 0.0]
        ct_ds.PixelSpacing = [0.5, 0.5]
        
        ct_ds.save_as(str(ct_path))
        
        # Anonymize
        output_path = temp_output_dir / "ct_preserved.dcm"
        result = anonymizer.anonymize_file(ct_path, output_path)
        
        assert result.success, f"Anonymization failed: {result.error_message}"
        
        # Verify critical tags are preserved
        anon_ds = pydicom.dcmread(str(output_path))
        
        # Hounsfield Unit mapping (MOST CRITICAL)
        assert hasattr(anon_ds, 'RescaleIntercept'), "RescaleIntercept must be preserved"
        assert anon_ds.RescaleIntercept == -1024, f"RescaleIntercept should be -1024, got {anon_ds.RescaleIntercept}"
        
        assert hasattr(anon_ds, 'RescaleSlope'), "RescaleSlope must be preserved"
        assert anon_ds.RescaleSlope == 1.0, f"RescaleSlope should be 1.0, got {anon_ds.RescaleSlope}"
        
        assert hasattr(anon_ds, 'RescaleType'), "RescaleType must be preserved"
        assert anon_ds.RescaleType == 'HU', f"RescaleType should be 'HU', got {anon_ds.RescaleType}"
        
        # Window/Level settings
        assert hasattr(anon_ds, 'WindowCenter'), "WindowCenter must be preserved"
        assert anon_ds.WindowCenter == 40.0, f"WindowCenter should be 40.0, got {anon_ds.WindowCenter}"
        
        assert hasattr(anon_ds, 'WindowWidth'), "WindowWidth must be preserved"
        assert anon_ds.WindowWidth == 400.0, f"WindowWidth should be 400.0, got {anon_ds.WindowWidth}"
        
        # CT acquisition parameters
        assert hasattr(anon_ds, 'ConvolutionKernel'), "ConvolutionKernel must be preserved"
        assert anon_ds.ConvolutionKernel == 'STANDARD', f"ConvolutionKernel should be 'STANDARD', got {anon_ds.ConvolutionKernel}"
        
        assert hasattr(anon_ds, 'KVP'), "KVP must be preserved"
        assert anon_ds.KVP == 120, f"KVP should be 120, got {anon_ds.KVP}"
        
        # Image geometry
        assert hasattr(anon_ds, 'SliceThickness'), "SliceThickness must be preserved"
        assert anon_ds.SliceThickness == 2.5, f"SliceThickness should be 2.5, got {anon_ds.SliceThickness}"
        
        assert hasattr(anon_ds, 'PixelSpacing'), "PixelSpacing must be preserved"
        assert anon_ds.PixelSpacing == [0.5, 0.5], f"PixelSpacing should be [0.5, 0.5], got {anon_ds.PixelSpacing}"
        
        # Verify pixel data is preserved
        assert hasattr(anon_ds, 'PixelData'), "PixelData must be preserved"
        assert result.pixel_data_preserved, "Pixel data should be preserved"
        
        # Verify no critical tags were removed
        critical_tags = [
            (0x0028, 0x1052),  # RescaleIntercept
            (0x0028, 0x1053),  # RescaleSlope
            (0x0028, 0x1054),  # RescaleType
            (0x0028, 0x1050),  # WindowCenter
            (0x0028, 0x1051),  # WindowWidth
            (0x0018, 0x1210),  # ConvolutionKernel
            (0x0018, 0x0060),  # KVP
            (0x0018, 0x0050),  # SliceThickness
            (0x0028, 0x0030),  # PixelSpacing
        ]
        
        for tag in critical_tags:
            assert tag not in result.tags_removed, f"Critical tag {tag} should NOT be removed"
        
        print("✅ All critical CT presentation tags preserved successfully!")
    
    def test_masking_disabled_config(self, sample_dicom_path, temp_output_dir):
        """
        When enable_pixel_masking=False, no masking should occur.
        """
        config = AnonymizationConfig(
            secret_salt=b"disabled_mask_test",
            enable_pixel_masking=False,  # Disabled
        )
        anonymizer = DicomAnonymizer(config)
        
        output_path = temp_output_dir / "no_mask.dcm"
        
        # Get original hash
        original_ds = pydicom.dcmread(str(sample_dicom_path))
        original_hash = hashlib.sha256(original_ds.PixelData).hexdigest()
        
        # Anonymize
        result = anonymizer.anonymize_file(sample_dicom_path, output_path)
        
        assert result.success
        assert not result.pixel_data_modified, "Pixel data should not be modified when masking disabled"
        assert result.pixel_mask_triggered_by is None, "No masking should be triggered"
        
        # Pixel hash should be preserved
        new_ds = pydicom.dcmread(str(output_path))
        new_hash = hashlib.sha256(new_ds.PixelData).hexdigest()
        assert new_hash == original_hash, "Pixel data should be preserved when masking disabled"
    
    def test_pixel_architecture_preservation(self, create_test_dicom, temp_output_dir):
        """
        Test that critical Image Pixel tags are preserved during anonymization.
        This prevents the "White Screen" issue by ensuring signed/unsigned pixel
        representation and other pixel architecture tags are maintained.
        """
        config = AnonymizationConfig(
            secret_salt=b"pixel_architecture_test_salt",
            enable_pixel_masking=False,  # Disable to focus on tag preservation
        )
        anonymizer = DicomAnonymizer(config)
        
        # Create a CT test file with specific pixel architecture
        pixel_data = np.random.randint(-2048, 2048, (64, 64), dtype=np.int16)  # Signed data
        ct_path = create_test_dicom(pixel_data=pixel_data)
        
        # Add critical Image Pixel tags
        ct_ds = pydicom.dcmread(str(ct_path))
        ct_ds.Modality = 'CT'
        
        # CRITICAL: Set pixel architecture tags that prevent white screen issues
        ct_ds.PhotometricInterpretation = 'MONOCHROME2'
        ct_ds.BitsAllocated = 16
        ct_ds.BitsStored = 16
        ct_ds.HighBit = 15
        ct_ds.PixelRepresentation = 1  # CRITICAL: 1=signed integers (prevents white screen)
        ct_ds.SamplesPerPixel = 1
        
        # Window/Level settings for proper display
        ct_ds.WindowCenter = 40.0
        ct_ds.WindowWidth = 400.0
        
        # Additional pixel formatting
        ct_ds.PixelSpacing = [0.5, 0.5]
        ct_ds.PixelAspectRatio = [1, 1]
        ct_ds.PixelPaddingValue = -2048
        
        ct_ds.save_as(str(ct_path))
        
        # Anonymize
        output_path = temp_output_dir / "pixel_architecture_preserved.dcm"
        result = anonymizer.anonymize_file(ct_path, output_path)
        
        assert result.success, f"Anonymization failed: {result.error_message}"
        
        # Verify critical pixel architecture tags are preserved
        anon_ds = pydicom.dcmread(str(output_path))
        
        # MOST CRITICAL: PixelRepresentation (prevents signed/unsigned misinterpretation)
        assert hasattr(anon_ds, 'PixelRepresentation'), "PixelRepresentation must be preserved"
        assert anon_ds.PixelRepresentation == 1, f"PixelRepresentation should be 1 (signed), got {anon_ds.PixelRepresentation}"
        
        # Essential pixel data interpretation tags
        assert hasattr(anon_ds, 'PhotometricInterpretation'), "PhotometricInterpretation must be preserved"
        assert anon_ds.PhotometricInterpretation == 'MONOCHROME2', f"PhotometricInterpretation should be 'MONOCHROME2', got {anon_ds.PhotometricInterpretation}"
        
        assert hasattr(anon_ds, 'BitsAllocated'), "BitsAllocated must be preserved"
        assert anon_ds.BitsAllocated == 16, f"BitsAllocated should be 16, got {anon_ds.BitsAllocated}"
        
        assert hasattr(anon_ds, 'BitsStored'), "BitsStored must be preserved"
        assert anon_ds.BitsStored == 16, f"BitsStored should be 16, got {anon_ds.BitsStored}"
        
        assert hasattr(anon_ds, 'HighBit'), "HighBit must be preserved"
        assert anon_ds.HighBit == 15, f"HighBit should be 15, got {anon_ds.HighBit}"
        
        assert hasattr(anon_ds, 'SamplesPerPixel'), "SamplesPerPixel must be preserved"
        assert anon_ds.SamplesPerPixel == 1, f"SamplesPerPixel should be 1, got {anon_ds.SamplesPerPixel}"
        
        # Window/Level settings (prevent white screen by proper contrast)
        assert hasattr(anon_ds, 'WindowCenter'), "WindowCenter must be preserved"
        assert anon_ds.WindowCenter == 40.0, f"WindowCenter should be 40.0, got {anon_ds.WindowCenter}"
        
        assert hasattr(anon_ds, 'WindowWidth'), "WindowWidth must be preserved"
        assert anon_ds.WindowWidth == 400.0, f"WindowWidth should be 400.0, got {anon_ds.WindowWidth}"
        
        # Additional pixel formatting
        assert hasattr(anon_ds, 'PixelSpacing'), "PixelSpacing must be preserved"
        assert anon_ds.PixelSpacing == [0.5, 0.5], f"PixelSpacing should be [0.5, 0.5], got {anon_ds.PixelSpacing}"
        
        assert hasattr(anon_ds, 'PixelAspectRatio'), "PixelAspectRatio must be preserved"
        assert anon_ds.PixelAspectRatio == [1, 1], f"PixelAspectRatio should be [1, 1], got {anon_ds.PixelAspectRatio}"
        
        assert hasattr(anon_ds, 'PixelPaddingValue'), "PixelPaddingValue must be preserved"
        assert anon_ds.PixelPaddingValue == -2048, f"PixelPaddingValue should be -2048, got {anon_ds.PixelPaddingValue}"
        
        # Verify pixel data is preserved and still signed
        assert hasattr(anon_ds, 'PixelData'), "PixelData must be preserved"
        assert result.pixel_data_preserved, "Pixel data should be preserved"
        
        # Verify the pixel array data type is preserved as signed
        pixel_array = anon_ds.pixel_array
        assert pixel_array.dtype == np.int16, f"Pixel array should remain int16 (signed), got {pixel_array.dtype}"
        
        # Verify no critical pixel architecture tags were removed
        critical_pixel_tags = [
            (0x0028, 0x0004),  # PhotometricInterpretation
            (0x0028, 0x0100),  # BitsAllocated
            (0x0028, 0x0101),  # BitsStored
            (0x0028, 0x0102),  # HighBit
            (0x0028, 0x0103),  # PixelRepresentation (CRITICAL)
            (0x0028, 0x0002),  # SamplesPerPixel
            (0x0028, 0x1050),  # WindowCenter
            (0x0028, 0x1051),  # WindowWidth
            (0x0028, 0x0030),  # PixelSpacing
            (0x0028, 0x0034),  # PixelAspectRatio
            (0x0028, 0x0120),  # PixelPaddingValue
        ]
        
        for tag in critical_pixel_tags:
            assert tag not in result.tags_removed, f"Critical pixel architecture tag {tag} should NOT be removed"
        
        print("✅ All critical Image Pixel architecture tags preserved successfully!")
        print("✅ White Screen issue prevention verified - PixelRepresentation=1 (signed) maintained!")
    
    def test_ct_pixel_architecture_preserved(self, create_test_dicom, temp_output_dir):
        """
        Test that PixelRepresentation is preserved.
        Missing this tag causes Signed CT data (-1000) to be read as Unsigned (64536),
        resulting in a white/inverted image.
        """
        config = AnonymizationConfig(
            secret_salt=b"ct_pixel_architecture_test_salt",
            enable_pixel_masking=False,  # Disable to focus on tag preservation
        )
        anonymizer = DicomAnonymizer(config)
        
        # Create a CT test file with signed pixel data
        pixel_data = np.random.randint(-1000, 1000, (64, 64), dtype=np.int16)  # Signed CT data
        ct_path = create_test_dicom(pixel_data=pixel_data)
        
        # Set up CT with signed pixel architecture
        ct_ds = pydicom.dcmread(str(ct_path))
        ct_ds.Modality = 'CT'
        
        # CRITICAL: Simulate CT signed data that causes white screen if stripped
        ct_ds.PixelRepresentation = 1  # 1=signed (CRITICAL for CT)
        ct_ds.BitsAllocated = 16
        ct_ds.BitsStored = 16
        ct_ds.HighBit = 15
        ct_ds.PhotometricInterpretation = 'MONOCHROME2'
        
        ct_ds.save_as(str(ct_path))
        
        # Anonymize
        output_path = temp_output_dir / "ct_white_screen_test.dcm"
        result = anonymizer.anonymize_file(ct_path, output_path)
        
        assert result.success, f"Anonymization failed: {result.error_message}"
        
        # Verify the anonymized dataset has the critical tag
        anon_ds = pydicom.dcmread(str(output_path))
        
        # This tag MUST be present for CTs to display correctly
        assert (0x0028, 0x0103) in anon_ds, "PixelRepresentation missing - will cause White Screen"
        assert anon_ds[0x0028, 0x0103].value == 1, f"PixelRepresentation should be 1 (signed), got {anon_ds[0x0028, 0x0103].value}"
        
        # Verify other critical pixel architecture tags are also present
        assert (0x0028, 0x0100) in anon_ds, "BitsAllocated missing"
        assert anon_ds[0x0028, 0x0100].value == 16, f"BitsAllocated should be 16, got {anon_ds[0x0028, 0x0100].value}"
        
        assert (0x0028, 0x0101) in anon_ds, "BitsStored missing"
        assert anon_ds[0x0028, 0x0101].value == 16, f"BitsStored should be 16, got {anon_ds[0x0028, 0x0101].value}"
        
        assert (0x0028, 0x0102) in anon_ds, "HighBit missing"
        assert anon_ds[0x0028, 0x0102].value == 15, f"HighBit should be 15, got {anon_ds[0x0028, 0x0102].value}"
        
        # Verify pixel data is still signed
        pixel_array = anon_ds.pixel_array
        assert pixel_array.dtype == np.int16, f"Pixel array should remain int16 (signed), got {pixel_array.dtype}"
        
        # Verify no critical pixel architecture tags were removed
        critical_tag = (0x0028, 0x0103)  # PixelRepresentation
        assert critical_tag not in result.tags_removed, f"CRITICAL: PixelRepresentation {critical_tag} was removed - this causes white screen!"
        
        print("✅ CT PixelRepresentation preservation verified - White Screen issue prevented!")
    
    def test_masking_disabled_config(self, sample_dicom_path, temp_output_dir):
        """
        When enable_pixel_masking=False, no masking should occur.
        """
        config = AnonymizationConfig(
            secret_salt=b"disabled_mask_test",
            enable_pixel_masking=False,  # Disabled
        )
        anonymizer = DicomAnonymizer(config)
        
        output_path = temp_output_dir / "no_mask.dcm"
        
        # Get original hash
        original_ds = pydicom.dcmread(str(sample_dicom_path))
        original_hash = hashlib.sha256(original_ds.PixelData).hexdigest()
        
        result = anonymizer.anonymize_file(sample_dicom_path, output_path)
        
        assert result.success
        assert not result.pixel_data_modified, "Masking should be disabled"
        assert result.pixel_mask_triggered_by is None
        
        # Hash should be same
        new_ds = pydicom.dcmread(str(output_path))
        new_hash = hashlib.sha256(new_ds.PixelData).hexdigest()
        assert new_hash == original_hash
    
    def test_compliance_report_pixel_masking(self, sample_dicom_path, temp_output_dir):
        """
        Compliance report should correctly reflect pixel masking status.
        """
        config = AnonymizationConfig(
            secret_salt=b"report_test_salt",
            enable_pixel_masking=True,
            pixel_mask_modalities={'US', 'SC', 'OT'},
            pixel_mask_top_fraction=0.10,
        )
        anonymizer = DicomAnonymizer(config)
        
        output_path = temp_output_dir / "report_test.dcm"
        result = anonymizer.anonymize_file(sample_dicom_path, output_path)
        
        # Generate report
        generator = ComplianceReportGenerator()
        generator.add_result(result, "report_test.dcm")
        
        report_path = temp_output_dir / "pixel_mask_report.json"
        report = generator.save_report(report_path)
        
        # Verify report contents
        assert report.files_with_pixel_masking == 1
        assert report.all_metadata_clean
        assert report.all_pixel_clean
        
        # Verify JSON structure
        import json
        with open(report_path) as f:
            report_json = json.load(f)
        
        assert "pixel_masking_summary" in report_json
        assert report_json["pixel_masking_summary"]["files_with_pixel_masking"] == 1
        assert report_json["pixel_masking_summary"]["all_pixel_clean"] == True
        
        # Check file entry
        entry = report_json["file_entries"][0]
        assert "pixel_masking" in entry
        assert entry["pixel_masking"]["pixel_data_modified"] == True
        assert entry["pixel_masking"]["triggered_by_modality"] == "US"
        assert entry["compliance_status"]["metadata_clean"] == True
        assert entry["compliance_status"]["pixel_clean"] == True


class TestPixelMaskingEdgeCases:
    """Edge case tests for pixel masking."""
    
    def test_configurable_mask_fraction(self, sample_dicom_path, temp_output_dir):
        """
        Test that mask fraction is configurable.
        """
        # Test with 20% masking
        config = AnonymizationConfig(
            secret_salt=b"fraction_test_salt",
            enable_pixel_masking=True,
            pixel_mask_modalities={'US'},
            pixel_mask_top_fraction=0.20,  # 20%
        )
        anonymizer = DicomAnonymizer(config)
        
        output_path = temp_output_dir / "fraction_test.dcm"
        result = anonymizer.anonymize_file(sample_dicom_path, output_path)
        
        assert result.success
        assert result.pixel_mask_region is not None
        
        # Verify the mask region reflects 20%
        total_rows = result.pixel_mask_region["total_rows"]
        masked_rows = result.pixel_mask_region["top_rows_masked"]
        
        expected_masked = int(total_rows * 0.20)
        assert masked_rows == expected_masked, \
            f"Expected {expected_masked} rows masked, got {masked_rows}"
    
    def test_secondary_capture_masking(self, create_test_dicom, temp_output_dir):
        """
        Test that Secondary Capture (SC) modality triggers masking.
        """
        config = AnonymizationConfig(
            secret_salt=b"sc_test_salt",
            enable_pixel_masking=True,
            pixel_mask_modalities={'US', 'SC', 'OT'},
            pixel_mask_top_fraction=0.10,
        )
        anonymizer = DicomAnonymizer(config)
        
        # Create SC test file
        input_path = create_test_dicom()
        ds = pydicom.dcmread(str(input_path))
        ds.Modality = 'SC'
        ds.save_as(str(input_path))
        
        output_path = temp_output_dir / "sc_masked.dcm"
        result = anonymizer.anonymize_file(input_path, output_path)
        
        assert result.success
        assert result.pixel_data_modified
        assert result.pixel_mask_triggered_by == 'SC'


# ═══════════════════════════════════════════════════════════════════════════════
# RUN TESTS
# ═══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
