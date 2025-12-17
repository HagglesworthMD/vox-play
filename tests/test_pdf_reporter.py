"""
Unit tests for pdf_reporter.py

These tests verify that PDF reports generate successfully without errors
and produce valid output. We test:
- All 6 report types generate without raising
- Output is bytes with reasonable size
- Invalid report types raise ValueError
- Convenience function works

Note: We don't parse PDF content deeply - just verify generation succeeds.
"""
import pytest
import tempfile
import os

# Add src to path (matches pattern from other test files)
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from pdf_reporter import PDFReporter, create_report, FPDF_AVAILABLE


# Skip all tests if fpdf2 is not installed
pytestmark = pytest.mark.skipif(
    not FPDF_AVAILABLE,
    reason="fpdf2 not installed"
)


class TestPDFReporterInit:
    """Test PDFReporter initialization."""
    
    def test_init_succeeds(self):
        """PDFReporter should initialize without error when fpdf2 is available."""
        reporter = PDFReporter()
        assert reporter is not None


class TestInternalRepairReport:
    """Tests for INTERNAL_REPAIR report type."""
    
    def test_generates_without_error(self):
        """INTERNAL_REPAIR report should generate without raising."""
        reporter = PDFReporter()
        data = {
            'patient_name': 'DOE^JOHN',
            'accession': 'ACC123456',
            'study_date': '2024-01-15',
            'operator': 'TestOperator',
        }
        result = reporter.create_pdf('INTERNAL_REPAIR', data)
        assert isinstance(result, bytes)
    
    def test_output_has_reasonable_size(self):
        """INTERNAL_REPAIR report should produce output larger than 1KB."""
        reporter = PDFReporter()
        data = {'patient_name': 'TEST^PATIENT'}
        result = reporter.create_pdf('INTERNAL_REPAIR', data)
        assert len(result) > 1024  # At least 1KB
    
    def test_with_fixed_tags(self):
        """INTERNAL_REPAIR report should handle fixed_tags list."""
        reporter = PDFReporter()
        data = {
            'patient_name': 'DOE^JANE',
            'fixed_tags': [
                {'name': 'PatientName', 'original': 'DOE^JOHN', 'new': 'DOE^JANE', 'action': 'Modified'},
                {'name': 'PatientID', 'original': '12345', 'new': '54321', 'action': 'Modified'},
            ]
        }
        result = reporter.create_pdf('INTERNAL_REPAIR', data)
        assert len(result) > 1024
    
    def test_with_mask_applied(self):
        """INTERNAL_REPAIR report should handle mask_applied flag."""
        reporter = PDFReporter()
        data = {
            'patient_name': 'MASKED^PATIENT',
            'mask_applied': True,
            'mask_region': '(10, 10, 200, 50)',
            'frames_processed': 100,
        }
        result = reporter.create_pdf('INTERNAL_REPAIR', data)
        assert len(result) > 1024
    
    def test_with_audit_hashes(self):
        """INTERNAL_REPAIR report should include audit trail hashes."""
        reporter = PDFReporter()
        data = {
            'patient_name': 'AUDIT^TEST',
            'uuid': 'test-uuid-1234',
            'original_hash': 'a' * 64,
            'processed_hash': 'b' * 64,
        }
        result = reporter.create_pdf('INTERNAL_REPAIR', data)
        assert len(result) > 1024


class TestResearchReport:
    """Tests for RESEARCH (Safe Harbor) report type."""
    
    def test_generates_without_error(self):
        """RESEARCH report should generate without raising."""
        reporter = PDFReporter()
        data = {
            'subject_id': 'SUB-001',
            'trial_id': 'TRIAL-2024-001',
            'site_id': 'SITE-A',
            'time_point': 'Baseline',
        }
        result = reporter.create_pdf('RESEARCH', data)
        assert isinstance(result, bytes)
        assert len(result) > 1024
    
    def test_with_pixel_masked(self):
        """RESEARCH report should handle pixel_masked flag."""
        reporter = PDFReporter()
        data = {
            'subject_id': 'SUB-002',
            'pixel_masked': True,
            'uids_regenerated': True,
            'file_count': 50,
        }
        result = reporter.create_pdf('RESEARCH', data)
        assert len(result) > 1024
    
    def test_minimal_data(self):
        """RESEARCH report should work with empty data dict."""
        reporter = PDFReporter()
        result = reporter.create_pdf('RESEARCH', {})
        assert len(result) > 1024


class TestStrictReport:
    """Tests for STRICT (OAIC) report type."""
    
    def test_generates_without_error(self):
        """STRICT report should generate without raising."""
        reporter = PDFReporter()
        data = {
            'hashed_patient_id': 'abc123def456' * 5,
            'date_shift_days': '-45',
            'uids_regenerated': True,
        }
        result = reporter.create_pdf('STRICT', data)
        assert isinstance(result, bytes)
        assert len(result) > 1024
    
    def test_with_pixel_masked_false(self):
        """STRICT report should handle pixel_masked=False."""
        reporter = PDFReporter()
        data = {'pixel_masked': False}
        result = reporter.create_pdf('STRICT', data)
        assert len(result) > 1024


class TestFOILegalReport:
    """Tests for FOI_LEGAL report type."""
    
    def test_generates_without_error(self):
        """FOI_LEGAL report should generate without raising."""
        reporter = PDFReporter()
        data = {
            'case_reference': 'CROWN-2024-001',
            'requesting_party': 'Crown Solicitor Office',
            'patient_name': 'PLAINTIFF^NAME',
        }
        result = reporter.create_pdf('FOI_LEGAL', data)
        assert isinstance(result, bytes)
        assert len(result) > 1024
    
    def test_with_files_list(self):
        """FOI_LEGAL report should handle files list with hashes."""
        reporter = PDFReporter()
        data = {
            'case_reference': 'CASE-001',
            'files': [
                {'name': 'image1.dcm', 'original_hash': 'a' * 64, 'processed_hash': 'b' * 64},
                {'name': 'image2.dcm', 'original_hash': 'c' * 64, 'processed_hash': 'd' * 64},
            ]
        }
        result = reporter.create_pdf('FOI_LEGAL', data)
        assert len(result) > 1024
    
    def test_with_redactions(self):
        """FOI_LEGAL report should handle redaction log."""
        reporter = PDFReporter()
        data = {
            'case_reference': 'CASE-002',
            'redactions': [
                {'tag': 'OperatorsName', 'action': 'REDACTED'},
                {'tag': 'ReferringPhysicianName', 'action': 'REDACTED'},
            ]
        }
        result = reporter.create_pdf('FOI_LEGAL', data)
        assert len(result) > 1024


class TestFOIPatientReport:
    """Tests for FOI_PATIENT report type."""
    
    def test_generates_without_error(self):
        """FOI_PATIENT report should generate without raising."""
        reporter = PDFReporter()
        data = {
            'patient_name': 'RECIPIENT^NAME',
            'facility_name': 'Test Hospital',
            'study_date': '2024-01-15',
        }
        result = reporter.create_pdf('FOI_PATIENT', data)
        assert isinstance(result, bytes)
        assert len(result) > 1024
    
    def test_with_full_details(self):
        """FOI_PATIENT report should handle all optional fields."""
        reporter = PDFReporter()
        data = {
            'patient_name': 'PATIENT^FULL',
            'patient_address': '123 Test Street\nTest City, 5000',
            'facility_name': 'Adelaide Medical Centre',
            'facility_address': '50 Hospital Lane, Adelaide',
            'facility_phone': '(08) 1234 5678',
            'request_date': '2024-01-10',
            'reference_number': 'FOI-2024-0001',
            'study_date': '2024-01-05',
            'modality': 'US',
            'accession': 'ACC999',
            'file_count': 25,
            'signatory_name': 'Jane Smith',
            'signatory_title': 'Medical Records Manager',
        }
        result = reporter.create_pdf('FOI_PATIENT', data)
        assert len(result) > 1024


class TestNIfTIReport:
    """Tests for NIFTI report type."""
    
    def test_generates_without_error(self):
        """NIFTI report should generate without raising."""
        reporter = PDFReporter()
        data = {
            'conversion_mode': '3D',
            'input_count': 100,
            'output_count': 1,
            'retention': 100.0,
        }
        result = reporter.create_pdf('NIFTI', data)
        assert isinstance(result, bytes)
        assert len(result) > 1024
    
    def test_with_low_retention(self):
        """NIFTI report should handle low retention values."""
        reporter = PDFReporter()
        data = {
            'conversion_mode': '2D_FALLBACK',
            'input_count': 50,
            'output_count': 45,
            'retention': 85.5,
        }
        result = reporter.create_pdf('NIFTI', data)
        assert len(result) > 1024


class TestInvalidReportType:
    """Tests for invalid report type handling."""
    
    def test_raises_on_unknown_type(self):
        """create_pdf should raise ValueError for unknown report type."""
        reporter = PDFReporter()
        with pytest.raises(ValueError, match="Unknown report type"):
            reporter.create_pdf('INVALID_TYPE', {})
    
    def test_error_message_includes_valid_types(self):
        """Error message should list valid report types."""
        reporter = PDFReporter()
        try:
            reporter.create_pdf('BAD', {})
        except ValueError as e:
            assert 'INTERNAL_REPAIR' in str(e)
            assert 'RESEARCH' in str(e)


class TestConvenienceFunction:
    """Tests for the create_report convenience function."""
    
    def test_creates_report(self):
        """create_report should work like reporter.create_pdf."""
        result = create_report('INTERNAL_REPAIR', {'patient_name': 'TEST'})
        assert isinstance(result, bytes)
        assert len(result) > 1024
    
    def test_saves_to_file(self):
        """create_report should save to file when output_path provided."""
        with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as f:
            output_path = f.name
        
        try:
            result = create_report('RESEARCH', {'subject_id': 'TEST'}, output_path=output_path)
            
            # Check file was created
            assert os.path.exists(output_path)
            
            # Check file has content
            with open(output_path, 'rb') as f:
                file_content = f.read()
            assert len(file_content) > 1024
            assert file_content == result  # Same content
        finally:
            if os.path.exists(output_path):
                os.unlink(output_path)


class TestCaseInsensitivity:
    """Test that report type matching is case-insensitive."""
    
    def test_lowercase_type(self):
        """Report type should work with lowercase."""
        result = create_report('internal_repair', {'patient_name': 'TEST'})
        assert len(result) > 1024
    
    def test_mixed_case_type(self):
        """Report type should work with mixed case."""
        result = create_report('Research', {'subject_id': 'TEST'})
        assert len(result) > 1024
