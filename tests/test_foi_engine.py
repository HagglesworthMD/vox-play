"""
Unit tests for foi_engine.py

Tests FOI (Freedom of Information) processing functionality:
- FOIEngine: Staff redaction, UID preservation, patient data preservation
- Scanned document detection and exclusion
- FOIBatchProcessor: Multi-file processing
- Convenience functions: process_foi_request, exclude_scanned_documents
"""
import os
import sys
from pathlib import Path
import pytest

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

import pydicom
from pydicom.dataset import Dataset, FileMetaDataset
from pydicom.uid import ExplicitVRLittleEndian
from pydicom.sequence import Sequence

from foi_engine import (
    FOIEngine,
    FOIProcessingResult,
    FOIBatchProcessor,
    process_foi_request,
    exclude_scanned_documents,
)


@pytest.fixture
def minimal_dataset():
    """Create a minimal DICOM dataset for FOI testing."""
    ds = Dataset()
    ds.PatientName = "DOE^JOHN"
    ds.PatientID = "MRN123456"
    ds.StudyDate = "20240115"
    ds.StudyTime = "143000"
    ds.Modality = "US"
    ds.AccessionNumber = "ACC2024001"
    ds.SOPInstanceUID = "1.2.3.4.5.6.7.8.9"
    ds.StudyInstanceUID = "1.2.3.4.5.6.7.8.9.10"
    ds.SeriesInstanceUID = "1.2.3.4.5.6.7.8.9.11"
    
    # Add staff names for redaction testing
    ds.OperatorsName = "TECH^JANE"
    ds.PerformingPhysicianName = "DOCTOR^BOB"
    ds.ReferringPhysicianName = "GP^REFERRING"
    
    # File meta
    ds.file_meta = FileMetaDataset()
    ds.file_meta.TransferSyntaxUID = ExplicitVRLittleEndian
    ds.file_meta.MediaStorageSOPInstanceUID = ds.SOPInstanceUID
    ds.file_meta.MediaStorageSOPClassUID = "1.2.840.10008.5.1.4.1.1.6.1"
    
    return ds


@pytest.fixture
def dataset_with_pixel_data(minimal_dataset):
    """Dataset with pixel data for hash testing."""
    minimal_dataset.PixelData = b'\x00\x01\x02\x03' * 100
    return minimal_dataset


class TestFOIProcessingResult:
    """Tests for FOIProcessingResult dataclass."""
    
    def test_default_values(self):
        """Should have correct default values."""
        result = FOIProcessingResult()
        assert result.success is False
        assert result.mode == "unknown"
        assert result.files_processed == 0
        assert result.redactions == []
        assert result.error is None
    
    def test_mutable_defaults_are_independent(self):
        """Each instance should have independent mutable defaults."""
        r1 = FOIProcessingResult()
        r2 = FOIProcessingResult()
        r1.redactions.append({'tag': 'test'})
        assert len(r2.redactions) == 0


class TestFOIEngineInit:
    """Tests for FOIEngine initialization."""
    
    def test_default_init(self):
        """Default init should not redact referring physician."""
        engine = FOIEngine()
        assert engine.redact_referring is False
    
    def test_init_with_redact_referring(self):
        """Should respect redact_referring_physician flag."""
        engine = FOIEngine(redact_referring_physician=True)
        assert engine.redact_referring is True


class TestProcessDatasetLegalMode:
    """Tests for process_dataset in legal mode."""
    
    def test_preserves_patient_name(self, minimal_dataset):
        """Legal mode should preserve patient name."""
        engine = FOIEngine()
        ds, result = engine.process_dataset(minimal_dataset, mode="legal")
        
        assert ds.PatientName == "DOE^JOHN"
        assert result.patient_name == "DOE^JOHN"
    
    def test_preserves_patient_id(self, minimal_dataset):
        """Legal mode should preserve patient ID."""
        engine = FOIEngine()
        ds, result = engine.process_dataset(minimal_dataset, mode="legal")
        
        assert ds.PatientID == "MRN123456"
    
    def test_preserves_accession_number(self, minimal_dataset):
        """Legal mode should preserve accession number."""
        engine = FOIEngine()
        ds, result = engine.process_dataset(minimal_dataset, mode="legal")
        
        assert ds.AccessionNumber == "ACC2024001"
        assert result.accession == "ACC2024001"
    
    def test_extracts_study_date(self, minimal_dataset):
        """Should format study date as YYYY-MM-DD."""
        engine = FOIEngine()
        ds, result = engine.process_dataset(minimal_dataset, mode="legal")
        
        assert result.study_date == "2024-01-15"
    
    def test_extracts_study_date_fallback(self, minimal_dataset):
        """Should handle non-standard study date format."""
        minimal_dataset.StudyDate = "January 15, 2024"  # Non-standard
        engine = FOIEngine()
        ds, result = engine.process_dataset(minimal_dataset, mode="legal")
        
        # Should use raw value as fallback
        assert "January" in result.study_date or result.study_date == "2024-01-15"
    
    def test_redacts_operators_name(self, minimal_dataset):
        """Should redact operators name."""
        engine = FOIEngine()
        ds, result = engine.process_dataset(minimal_dataset, mode="legal")
        
        assert ds.OperatorsName == "REDACTED"
        assert any('Operator' in r.get('tag', '') for r in result.redactions)
    
    def test_redacts_performing_physician(self, minimal_dataset):
        """Should redact performing physician name."""
        engine = FOIEngine()
        ds, result = engine.process_dataset(minimal_dataset, mode="legal")
        
        assert ds.PerformingPhysicianName == "REDACTED"
    
    def test_preserves_referring_physician_by_default(self, minimal_dataset):
        """Should NOT redact referring physician by default."""
        engine = FOIEngine(redact_referring_physician=False)
        ds, result = engine.process_dataset(minimal_dataset, mode="legal")
        
        # Should NOT be redacted
        assert ds.ReferringPhysicianName == "GP^REFERRING"
    
    def test_redacts_referring_physician_when_enabled(self, minimal_dataset):
        """Should redact referring physician when flag is True."""
        engine = FOIEngine(redact_referring_physician=True)
        ds, result = engine.process_dataset(minimal_dataset, mode="legal")
        
        assert ds.ReferringPhysicianName == "REDACTED"
    
    def test_success_flag_is_true(self, minimal_dataset):
        """Successful processing should set success=True."""
        engine = FOIEngine()
        ds, result = engine.process_dataset(minimal_dataset, mode="legal")
        
        assert result.success is True
        assert result.files_processed == 1
    
    def test_mode_is_set(self, minimal_dataset):
        """Result should include the processing mode."""
        engine = FOIEngine()
        ds, result = engine.process_dataset(minimal_dataset, mode="legal")
        
        assert result.mode == "legal"


class TestProcessDatasetPatientMode:
    """Tests for process_dataset in patient mode."""
    
    def test_patient_mode_works(self, minimal_dataset):
        """Patient mode should process successfully."""
        engine = FOIEngine()
        ds, result = engine.process_dataset(minimal_dataset, mode="patient")
        
        assert result.success is True
        assert result.mode == "patient"
    
    def test_patient_mode_redacts_staff(self, minimal_dataset):
        """Patient mode should also redact staff names."""
        engine = FOIEngine()
        ds, result = engine.process_dataset(minimal_dataset, mode="patient")
        
        assert ds.OperatorsName == "REDACTED"


class TestProcessDatasetPixelHashing:
    """Tests for pixel data hash calculation."""
    
    def test_calculates_hash_with_pixel_data(self, dataset_with_pixel_data):
        """Should calculate SHA-256 hash of pixel data."""
        engine = FOIEngine()
        ds, result = engine.process_dataset(dataset_with_pixel_data)
        
        assert len(result.hashes) == 1
        assert result.hashes[0]['original'] is not None
        assert len(result.hashes[0]['original']) == 64  # SHA-256 hex
    
    def test_hash_unchanged_flag(self, dataset_with_pixel_data):
        """Hash unchanged flag should be True when pixel data not modified."""
        engine = FOIEngine()
        ds, result = engine.process_dataset(dataset_with_pixel_data)
        
        assert result.hashes[0]['unchanged'] is True
    
    def test_no_pixel_data_hash(self, minimal_dataset):
        """Should handle datasets without pixel data."""
        engine = FOIEngine()
        ds, result = engine.process_dataset(minimal_dataset)
        
        assert len(result.hashes) == 1
        assert result.hashes[0]['original'] == "NO_PIXEL_DATA"
        assert result.hashes[0]['processed'] == "NO_PIXEL_DATA"


class TestScannedDocumentExclusion:
    """Tests for scanned document detection and exclusion."""
    
    def test_excludes_sc_modality(self, minimal_dataset):
        """Should exclude Secondary Capture (SC) modality."""
        minimal_dataset.Modality = "SC"
        engine = FOIEngine()
        ds, result = engine.process_dataset(minimal_dataset, exclude_scanned=True)
        
        assert result.success is False
        assert "SC" in result.error
    
    def test_excludes_ot_modality(self, minimal_dataset):
        """Should exclude Other (OT) modality."""
        minimal_dataset.Modality = "OT"
        engine = FOIEngine()
        ds, result = engine.process_dataset(minimal_dataset, exclude_scanned=True)
        
        assert result.success is False
        assert "OT" in result.error
    
    def test_allows_us_modality(self, minimal_dataset):
        """Should allow Ultrasound (US) modality."""
        minimal_dataset.Modality = "US"
        engine = FOIEngine()
        ds, result = engine.process_dataset(minimal_dataset, exclude_scanned=True)
        
        assert result.success is True
    
    def test_allows_ct_modality(self, minimal_dataset):
        """Should allow CT modality."""
        minimal_dataset.Modality = "CT"
        engine = FOIEngine()
        ds, result = engine.process_dataset(minimal_dataset, exclude_scanned=True)
        
        assert result.success is True
    
    def test_no_exclusion_when_flag_false(self, minimal_dataset):
        """Should not exclude even SC when exclude_scanned=False."""
        minimal_dataset.Modality = "SC"
        engine = FOIEngine()
        ds, result = engine.process_dataset(minimal_dataset, exclude_scanned=False)
        
        assert result.success is True


class TestIsScannedDocument:
    """Tests for is_scanned_document detection."""
    
    def test_detects_sc_modality(self, minimal_dataset):
        """Should detect SC as scanned document."""
        minimal_dataset.Modality = "SC"
        engine = FOIEngine()
        is_scanned, reason = engine.is_scanned_document(minimal_dataset)
        
        assert is_scanned is True
        assert "Secondary Capture" in reason
    
    def test_detects_ot_modality(self, minimal_dataset):
        """Should detect OT as scanned document."""
        minimal_dataset.Modality = "OT"
        engine = FOIEngine()
        is_scanned, reason = engine.is_scanned_document(minimal_dataset)
        
        assert is_scanned is True
        assert "Other" in reason
    
    def test_detects_structured_report(self, minimal_dataset):
        """Should detect SR (Structured Report) SOP class."""
        minimal_dataset.Modality = "SR"
        minimal_dataset.SOPClassUID = "1.2.840.10008.5.1.4.1.1.88.11"  # Basic Text SR
        engine = FOIEngine()
        is_scanned, reason = engine.is_scanned_document(minimal_dataset)
        
        assert is_scanned is True
        assert "Structured Report" in reason
    
    def test_detects_worksheet_by_image_type(self, minimal_dataset):
        """Should detect derived secondary worksheets."""
        minimal_dataset.ImageType = ['DERIVED', 'SECONDARY']
        minimal_dataset.SeriesDescription = "Patient Worksheet Summary"
        engine = FOIEngine()
        is_scanned, reason = engine.is_scanned_document(minimal_dataset)
        
        assert is_scanned is True
        assert "Worksheet" in reason
    
    def test_normal_us_not_detected(self, minimal_dataset):
        """Normal US should not be detected as scanned."""
        minimal_dataset.Modality = "US"
        engine = FOIEngine()
        is_scanned, reason = engine.is_scanned_document(minimal_dataset)
        
        assert is_scanned is False
        assert reason == ""


class TestRemovePrivateTags:
    """Tests for private tag removal."""
    
    def test_removes_private_tags(self, minimal_dataset):
        """Should remove private (vendor-specific) tags."""
        # Add a private tag (odd group number)
        minimal_dataset.add_new(0x00091001, 'LO', 'Private Data')
        
        engine = FOIEngine()
        ds, result = engine.process_dataset(minimal_dataset)
        
        # Verify private tag is removed
        assert (0x0009, 0x1001) not in ds
    
    def test_reports_private_tag_removal(self, minimal_dataset):
        """Should report private tag removal in redactions."""
        minimal_dataset.add_new(0x00091001, 'LO', 'Private1')
        minimal_dataset.add_new(0x00091002, 'LO', 'Private2')
        
        engine = FOIEngine()
        ds, result = engine.process_dataset(minimal_dataset)
        
        private_redaction = [r for r in result.redactions if 'Private' in r.get('tag', '')]
        assert len(private_redaction) >= 1


class TestConvenienceFunctions:
    """Tests for module-level convenience functions."""
    
    def test_process_foi_request_legal(self, minimal_dataset):
        """process_foi_request should work in legal mode."""
        ds, result = process_foi_request(minimal_dataset, mode="legal")
        
        assert result.success is True
        assert result.mode == "legal"
    
    def test_process_foi_request_patient(self, minimal_dataset):
        """process_foi_request should work in patient mode."""
        ds, result = process_foi_request(minimal_dataset, mode="patient")
        
        assert result.success is True
        assert result.mode == "patient"
    
    def test_process_foi_request_redact_referring(self, minimal_dataset):
        """process_foi_request should respect redact_referring flag."""
        ds, result = process_foi_request(
            minimal_dataset, 
            mode="legal", 
            redact_referring=True
        )
        
        assert ds.ReferringPhysicianName == "REDACTED"
    
    def test_exclude_scanned_documents_function(self, minimal_dataset):
        """exclude_scanned_documents convenience function should work."""
        minimal_dataset.Modality = "US"
        assert exclude_scanned_documents(minimal_dataset) is False
        
        minimal_dataset.Modality = "SC"
        assert exclude_scanned_documents(minimal_dataset) is True


class TestFOIBatchProcessor:
    """Tests for FOIBatchProcessor."""
    
    def test_init(self):
        """Should initialize with parameters."""
        processor = FOIBatchProcessor(
            mode="patient",
            exclude_scanned=True,
            redact_referring=True
        )
        assert processor.mode == "patient"
        assert processor.exclude_scanned is True
    
    def test_process_files_single(self, minimal_dataset, tmp_path):
        """Should process a single file."""
        # Save input file
        input_dir = tmp_path / "input"
        input_dir.mkdir()
        input_path = input_dir / "test.dcm"
        minimal_dataset.save_as(str(input_path))
        
        # Process
        output_dir = str(tmp_path / "output")
        processor = FOIBatchProcessor(mode="legal")
        result = processor.process_files([str(input_path)], output_dir)
        
        assert result.files_processed == 1
        assert os.path.exists(os.path.join(output_dir, "test.dcm"))
    
    def test_process_files_multiple(self, minimal_dataset, tmp_path):
        """Should process multiple files."""
        input_dir = tmp_path / "input"
        input_dir.mkdir()
        
        # Create multiple input files
        paths = []
        for i in range(3):
            path = input_dir / f"test{i}.dcm"
            minimal_dataset.SOPInstanceUID = f"1.2.3.4.5.{i}"
            minimal_dataset.save_as(str(path))
            paths.append(str(path))
        
        output_dir = str(tmp_path / "output")
        processor = FOIBatchProcessor()
        result = processor.process_files(paths, output_dir)
        
        assert result.files_processed == 3
    
    def test_process_files_with_exclusion(self, minimal_dataset, tmp_path):
        """Should exclude scanned documents when configured."""
        input_dir = tmp_path / "input"
        input_dir.mkdir()
        
        # Normal US file
        us_path = input_dir / "us.dcm"
        minimal_dataset.Modality = "US"
        minimal_dataset.save_as(str(us_path))
        
        # SC file (should be excluded)
        sc_path = input_dir / "sc.dcm"
        minimal_dataset.Modality = "SC"
        minimal_dataset.SOPInstanceUID = "1.2.3.99"
        minimal_dataset.save_as(str(sc_path))
        
        output_dir = str(tmp_path / "output")
        processor = FOIBatchProcessor(exclude_scanned=True)
        result = processor.process_files([str(us_path), str(sc_path)], output_dir)
        
        assert result.files_processed == 1  # Only US processed
        assert len(result.excluded_files) == 1
    
    def test_handles_invalid_file(self, tmp_path):
        """Should handle errors gracefully."""
        output_dir = str(tmp_path / "output")
        processor = FOIBatchProcessor()
        
        result = processor.process_files(
            ["/nonexistent/file.dcm"],
            output_dir
        )
        
        assert len(result.warnings) >= 1
