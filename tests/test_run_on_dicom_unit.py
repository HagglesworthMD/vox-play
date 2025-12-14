"""
Unit tests for run_on_dicom.py core functions.

These tests exercise the pure in-memory functions (like process_dataset)
without requiring real DICOM files or pixel data.
"""
import pytest
import pydicom
from pydicom.dataset import Dataset, FileMetaDataset
from pydicom.uid import ExplicitVRLittleEndian

# Add src to path (matches pattern from other test files)
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from run_on_dicom import process_dataset, anonymize_metadata


def make_minimal_ds():
    """Create a minimal DICOM dataset for testing (no pixel data)."""
    ds = Dataset()
    ds.PatientName = "DOE^JOHN"
    ds.PatientID = "12345"
    ds.StudyDate = "20240101"
    ds.StudyTime = "120000"
    ds.StudyInstanceUID = "1.2.3.4.5.6.7.8.9"
    ds.SeriesInstanceUID = "1.2.3.4.5.6.7.8.9.1"
    ds.SOPInstanceUID = "1.2.3.4.5.6.7.8.9.2"
    ds.Modality = "US"
    
    # Minimal file meta so pydicom is happy
    ds.file_meta = FileMetaDataset()
    ds.file_meta.TransferSyntaxUID = ExplicitVRLittleEndian
    ds.file_meta.MediaStorageSOPInstanceUID = ds.SOPInstanceUID
    ds.file_meta.MediaStorageSOPClassUID = "1.2.840.10008.5.1.4.1.1.6.1"  # US Image Storage
    
    return ds


class TestProcessDataset:
    """Tests for the process_dataset pure function."""
    
    def test_returns_dataset(self):
        """process_dataset should return a Dataset object."""
        ds = make_minimal_ds()
        result = process_dataset(
            ds,
            old_name_text="DOE^JOHN",
            new_name_text="ANON^PATIENT",
        )
        assert isinstance(result, Dataset)
    
    def test_modifies_in_place(self):
        """process_dataset should modify the dataset in-place and return same object."""
        ds = make_minimal_ds()
        result = process_dataset(
            ds,
            old_name_text="DOE^JOHN",
            new_name_text="ANON^PATIENT",
        )
        assert result is ds  # Same object reference
    
    def test_handles_no_pixel_data(self):
        """process_dataset should handle datasets without PixelData gracefully."""
        ds = make_minimal_ds()
        # Explicitly ensure no PixelData
        assert not hasattr(ds, 'PixelData')
        
        # Should not raise
        result = process_dataset(
            ds,
            old_name_text="DOE^JOHN",
            new_name_text="ANON^PATIENT",
        )
        assert result is not None
    
    def test_with_research_context(self):
        """process_dataset should accept research_context dict."""
        ds = make_minimal_ds()
        research_context = {
            'trial_id': 'TEST_TRIAL_001',
            'site_id': 'SITE_A',
            'subject_id': 'SUB_001',
            'time_point': 'Baseline',
        }
        
        result = process_dataset(
            ds,
            old_name_text="DOE^JOHN",
            new_name_text="RESEARCH_SUBJECT",
            research_context=research_context,
        )
        assert result is not None
    
    def test_with_clinical_context(self):
        """process_dataset should accept clinical_context dict."""
        ds = make_minimal_ds()
        clinical_context = {
            'patient_name': 'SMITH^JANE',
            'patient_sex': 'F',
            'patient_dob': '1990-05-15',
            'accession_number': 'ACC123',
            'study_date': '2024-01-15',
            'study_time': '10:30:00',
            'reason_for_correction': 'Name misspelled',
            'operator_name': 'Tech1',
        }
        
        result = process_dataset(
            ds,
            old_name_text="DOE^JOHN",
            new_name_text="SMITH^JANE",
            clinical_context=clinical_context,
        )
        assert result is not None


class TestAnonymizeMetadata:
    """Tests for the anonymize_metadata function."""
    
    def test_basic_call_does_not_raise(self):
        """anonymize_metadata should not raise with basic inputs."""
        ds = make_minimal_ds()
        # Should not raise
        anonymize_metadata(ds, "NEW_NAME", None, None)
    
    def test_with_research_context(self):
        """anonymize_metadata should handle research context."""
        ds = make_minimal_ds()
        research_context = {
            'trial_id': 'TRIAL_001',
            'subject_id': 'SUB_001',
        }
        # Should not raise
        anonymize_metadata(ds, "SUB_001", research_context, None)
    
    def test_with_clinical_context(self):
        """anonymize_metadata should handle clinical context."""
        ds = make_minimal_ds()
        clinical_context = {
            'patient_name': 'CORRECTED^NAME',
            'reason_for_correction': 'Typo fix',
        }
        # Should not raise
        anonymize_metadata(ds, "CORRECTED^NAME", None, clinical_context)
