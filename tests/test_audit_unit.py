"""
Unit tests for audit.py

Tests the audit receipt generation and utility functions:
- extract_sonographer_initials: Name parsing and initial extraction
- calculate_file_hash: SHA-256 file hashing
- generate_audit_receipt: Professional audit receipt generation

All functions are mostly pure/deterministic, so these tests should be fast and stable.
"""
import os
import sys
import hashlib
from pathlib import Path
import pytest

# Import from audit.py specifically (not the audit/ package)
# Python prefers packages over modules when both exist, so we use importlib
import importlib.util
_audit_path = os.path.join(os.path.dirname(__file__), '..', 'src', 'audit.py')
_spec = importlib.util.spec_from_file_location("audit_module", _audit_path)
_audit = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_audit)

extract_sonographer_initials = _audit.extract_sonographer_initials
calculate_file_hash = _audit.calculate_file_hash
generate_audit_receipt = _audit.generate_audit_receipt


class TestExtractSonographerInitials:
    """Tests for the extract_sonographer_initials function."""
    
    def test_dicom_name_format_lastname_firstname(self):
        """Should parse DICOM name format 'LastName^FirstName' -> 'S.J.'"""
        meta = {'OperatorsName': 'Smith^John'}
        result = extract_sonographer_initials(meta)
        assert result == "S.J."
    
    def test_dicom_name_format_with_middle(self):
        """Should parse DICOM name format with middle name."""
        meta = {'OperatorsName': 'Smith^John^Michael'}
        result = extract_sonographer_initials(meta)
        assert result == "S.J."
    
    def test_regular_name_format_first_last(self):
        """Should parse 'FirstName LastName' -> 'F.L.'"""
        meta = {'OperatorsName': 'John Smith'}
        result = extract_sonographer_initials(meta)
        assert result == "J.S."
    
    def test_comma_separated_format(self):
        """Should parse 'LastName, FirstName' -> 'S.J.'"""
        meta = {'OperatorsName': 'Smith, John'}
        result = extract_sonographer_initials(meta)
        assert result == "S.J."
    
    def test_single_name_only(self):
        """Should handle single name with no delimiter."""
        meta = {'OperatorsName': 'Smith'}
        result = extract_sonographer_initials(meta)
        assert result == "SM"
    
    def test_uses_operators_name_priority(self):
        """Should prefer OperatorsName over PerformingPhysicianName."""
        meta = {
            'OperatorsName': 'Smith^Jane',
            'PerformingPhysicianName': 'Jones^Tom',
        }
        result = extract_sonographer_initials(meta)
        assert result == "S.J."
    
    def test_falls_back_to_performing_physician(self):
        """Should use PerformingPhysicianName if OperatorsName missing."""
        meta = {'PerformingPhysicianName': 'Jones^Tom'}
        result = extract_sonographer_initials(meta)
        assert result == "J.T."
    
    def test_lowercase_key_variant(self):
        """Should handle lowercase key variants."""
        meta = {'operators_name': 'Brown^Alice'}
        result = extract_sonographer_initials(meta)
        assert result == "B.A."
    
    def test_empty_name_returns_na(self):
        """Should return 'N/A' for empty name."""
        meta = {'OperatorsName': ''}
        result = extract_sonographer_initials(meta)
        assert result == "N/A"
    
    def test_missing_key_returns_na(self):
        """Should return 'N/A' when no name keys present."""
        meta = {'SomeOtherField': 'value'}
        result = extract_sonographer_initials(meta)
        assert result == "N/A"
    
    def test_empty_dict_returns_na(self):
        """Should return 'N/A' for empty metadata dict."""
        result = extract_sonographer_initials({})
        assert result == "N/A"
    
    def test_none_value_returns_na(self):
        """Should return 'N/A' when name value is None."""
        meta = {'OperatorsName': None}
        result = extract_sonographer_initials(meta)
        assert result == "N/A"


class TestCalculateFileHash:
    """Tests for the calculate_file_hash function."""
    
    def test_returns_sha256_hex(self, tmp_path):
        """Should return SHA-256 hash as hex string."""
        test_file = tmp_path / "test.bin"
        content = b"Hello VoxelMask"
        test_file.write_bytes(content)
        
        result = calculate_file_hash(str(test_file))
        expected = hashlib.sha256(content).hexdigest()
        
        assert result == expected
    
    def test_deterministic_same_content(self, tmp_path):
        """Same content should always produce same hash."""
        content = b"Test content for hashing"
        
        file1 = tmp_path / "file1.bin"
        file2 = tmp_path / "file2.bin"
        file1.write_bytes(content)
        file2.write_bytes(content)
        
        hash1 = calculate_file_hash(str(file1))
        hash2 = calculate_file_hash(str(file2))
        
        assert hash1 == hash2
    
    def test_different_content_different_hash(self, tmp_path):
        """Different content should produce different hash."""
        file1 = tmp_path / "file1.bin"
        file2 = tmp_path / "file2.bin"
        file1.write_bytes(b"Content A")
        file2.write_bytes(b"Content B")
        
        hash1 = calculate_file_hash(str(file1))
        hash2 = calculate_file_hash(str(file2))
        
        assert hash1 != hash2
    
    def test_hash_length_is_64_chars(self, tmp_path):
        """SHA-256 hex digest should be 64 characters."""
        test_file = tmp_path / "test.bin"
        test_file.write_bytes(b"test")
        
        result = calculate_file_hash(str(test_file))
        assert len(result) == 64
    
    def test_missing_file_returns_error(self):
        """Should return 'HASH_ERROR' for missing file."""
        result = calculate_file_hash("/non/existent/file.bin")
        assert result == "HASH_ERROR"
    
    def test_empty_file(self, tmp_path):
        """Should hash empty file successfully."""
        test_file = tmp_path / "empty.bin"
        test_file.write_bytes(b"")
        
        result = calculate_file_hash(str(test_file))
        expected = hashlib.sha256(b"").hexdigest()
        
        assert result == expected


class TestGenerateAuditReceipt:
    """Tests for the generate_audit_receipt function."""
    
    @pytest.fixture
    def basic_original_meta(self):
        """Basic original metadata dict."""
        return {
            'patient_name': 'DOE^JOHN',
            'patient_id': '12345',
            'study_date': '20240115',
            'modality': 'US',
            'institution': 'Test Hospital',
            'OperatorsName': 'Smith^Jane',
        }
    
    @pytest.fixture
    def basic_new_meta(self):
        """Basic new metadata dict."""
        return {
            'patient_name': 'ANON^PATIENT',
            'patient_id': 'SUB001',
            'new_study_date': '20240115',
        }
    
    def test_returns_string(self, basic_original_meta, basic_new_meta):
        """generate_audit_receipt should return a string."""
        result = generate_audit_receipt(
            original_meta=basic_original_meta,
            new_meta=basic_new_meta,
            uuid_str="test-uuid-1234",
            operator_id="TEST_OP",
            mode="RESEARCH",
        )
        assert isinstance(result, str)
    
    def test_includes_uuid(self, basic_original_meta, basic_new_meta):
        """Receipt should include the provided UUID."""
        uuid_str = "unique-uuid-12345"
        result = generate_audit_receipt(
            original_meta=basic_original_meta,
            new_meta=basic_new_meta,
            uuid_str=uuid_str,
            operator_id="OP",
            mode="RESEARCH",
        )
        assert uuid_str in result
    
    def test_includes_operator_id(self, basic_original_meta, basic_new_meta):
        """Receipt should include the operator ID when profile allows staff visibility.
        
        Phase 12: Staff IDs are only shown for internal_repair profile.
        Other profiles (safe_harbor, research, FOI) redact staff identifiers.
        """
        result = generate_audit_receipt(
            original_meta=basic_original_meta,
            new_meta=basic_new_meta,
            uuid_str="uuid",
            operator_id="OPERATOR_JANE",
            mode="CLINICAL",
            compliance_profile="internal_repair",  # Only profile that shows staff IDs
        )
        assert "OPERATOR_JANE" in result
    
    def test_operator_id_redacted_for_research(self, basic_original_meta, basic_new_meta):
        """Receipt should REDACT operator ID for research/safe_harbor profiles.
        
        Phase 12: Staff identifiers are protected for all profiles except internal_repair.
        """
        result = generate_audit_receipt(
            original_meta=basic_original_meta,
            new_meta=basic_new_meta,
            uuid_str="uuid",
            operator_id="OPERATOR_JANE",
            mode="RESEARCH",
            compliance_profile="safe_harbor",
        )
        assert "OPERATOR_JANE" not in result
        assert "REDACTED" in result
    
    def test_includes_original_patient_info(self, basic_original_meta, basic_new_meta):
        """Receipt should include original patient information when profile allows PHI.
        
        Phase 12: Patient identifiers only shown for internal_repair and FOI profiles.
        """
        result = generate_audit_receipt(
            original_meta=basic_original_meta,
            new_meta=basic_new_meta,
            uuid_str="uuid",
            operator_id="OP",
            mode="CLINICAL",
            compliance_profile="internal_repair",
        )
        assert "DOE^JOHN" in result or "12345" in result
    
    def test_includes_new_patient_info(self, basic_original_meta, basic_new_meta):
        """Receipt should include new patient information when profile allows PHI.
        
        Phase 12: Patient identifiers only shown for internal_repair and FOI profiles.
        """
        result = generate_audit_receipt(
            original_meta=basic_original_meta,
            new_meta=basic_new_meta,
            uuid_str="uuid",
            operator_id="OP",
            mode="CLINICAL",
            compliance_profile="internal_repair",
        )
        assert "ANON^PATIENT" in result or "SUB001" in result
    
    def test_research_mode_includes_compliance(self, basic_original_meta, basic_new_meta):
        """Research mode should include compliance certification."""
        result = generate_audit_receipt(
            original_meta=basic_original_meta,
            new_meta=basic_new_meta,
            uuid_str="uuid",
            operator_id="OP",
            mode="RESEARCH",
            compliance_profile="safe_harbor",
        )
        assert "Safe Harbor" in result or "COMPLIANCE" in result
    
    def test_clinical_mode(self, basic_original_meta, basic_new_meta):
        """Clinical mode should work without errors."""
        result = generate_audit_receipt(
            original_meta=basic_original_meta,
            new_meta=basic_new_meta,
            uuid_str="uuid",
            operator_id="OP",
            mode="CLINICAL",
        )
        assert isinstance(result, str)
        assert len(result) > 0
    
    def test_foi_mode_includes_foi_section(self, basic_original_meta, basic_new_meta):
        """FOI mode should include FOI-specific sections."""
        result = generate_audit_receipt(
            original_meta=basic_original_meta,
            new_meta=basic_new_meta,
            uuid_str="uuid",
            operator_id="OP",
            mode="RESEARCH",
            is_foi_mode=True,
        )
        assert "FOI" in result
    
    def test_foi_mode_with_redactions(self, basic_original_meta, basic_new_meta):
        """FOI mode should include redaction list."""
        redactions = [
            {'tag': 'OperatorsName', 'action': 'REDACTED'},
            {'tag': 'ReferringPhysicianName', 'action': 'REDACTED'},
        ]
        result = generate_audit_receipt(
            original_meta=basic_original_meta,
            new_meta=basic_new_meta,
            uuid_str="uuid",
            operator_id="OP",
            mode="RESEARCH",
            is_foi_mode=True,
            foi_redactions=redactions,
        )
        assert "OperatorsName" in result
    
    def test_with_mask_applied(self, basic_original_meta, basic_new_meta):
        """Should indicate when pixel masking was applied."""
        result = generate_audit_receipt(
            original_meta=basic_original_meta,
            new_meta=basic_new_meta,
            uuid_str="uuid",
            operator_id="OP",
            mode="RESEARCH",
            mask_applied=True,
            pixel_action_reason="Burned-in PHI detected",
        )
        assert "APPLIED" in result
    
    def test_with_file_hashes(self, basic_original_meta, basic_new_meta):
        """Should include file hashes when provided."""
        result = generate_audit_receipt(
            original_meta=basic_original_meta,
            new_meta=basic_new_meta,
            uuid_str="uuid",
            operator_id="OP",
            mode="RESEARCH",
            original_file_hash="abc123" * 10,
            anonymized_file_hash="def456" * 10,
        )
        assert "abc123" in result or "Chain" in result
    
    def test_with_safety_notification(self, basic_original_meta, basic_new_meta):
        """Should include safety notification when provided."""
        notification = "CRITICAL: Manual review required"
        result = generate_audit_receipt(
            original_meta=basic_original_meta,
            new_meta=basic_new_meta,
            uuid_str="uuid",
            operator_id="OP",
            mode="RESEARCH",
            safety_notification=notification,
        )
        assert notification in result
    
    def test_internal_repair_profile(self, basic_original_meta, basic_new_meta):
        """Clinical correction profile should include specific sections."""
        result = generate_audit_receipt(
            original_meta=basic_original_meta,
            new_meta=basic_new_meta,
            uuid_str="uuid",
            operator_id="OP",
            mode="CLINICAL",
            compliance_profile="internal_repair",
        )
        assert "CLINICAL CORRECTION" in result or "PRESERVED" in result
    
    def test_empty_metas_does_not_crash(self):
        """Should handle empty metadata dicts without crashing."""
        result = generate_audit_receipt(
            original_meta={},
            new_meta={},
            uuid_str="test-uuid",
            operator_id="OP",
            mode="RESEARCH",
        )
        assert isinstance(result, str)
        assert "test-uuid" in result
    
    def test_includes_timestamp(self, basic_original_meta, basic_new_meta):
        """Receipt should include a timestamp."""
        result = generate_audit_receipt(
            original_meta=basic_original_meta,
            new_meta=basic_new_meta,
            uuid_str="uuid",
            operator_id="OP",
            mode="RESEARCH",
        )
        # Should have date-like content (year)
        assert "202" in result or "Timestamp" in result.lower()


class TestModuleImports:
    """Tests for module-level checks."""
    
    def test_audit_module_imports(self):
        """audit.py module should import successfully."""
        # We already loaded it via importlib above as _audit
        assert _audit is not None
    
    def test_functions_are_callable(self):
        """All public functions should be callable."""
        assert callable(extract_sonographer_initials)
        assert callable(calculate_file_hash)
        assert callable(generate_audit_receipt)

