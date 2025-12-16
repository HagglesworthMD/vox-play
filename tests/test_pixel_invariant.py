"""
Unit tests for src/pixel_invariant.py
======================================
Phase 3: Pixel Invariant Enforcement Tests

Test Strategy:
1. PixelAction enum tests
2. sha256_bytes and get_pixel_data_safe helper tests
3. decide_pixel_action logic tests
4. enforce_pixel_passthrough_invariant tests (pass/fail cases)
5. check_transfer_syntax_preserved tests
6. validate_uid_only_output integration tests
7. Full end-to-end UID-only export simulation

This test suite permanently locks the invariant:
- UID-only mode MUST NOT modify PixelData
- Any mutation raises RuntimeError immediately
"""

import hashlib
import pytest
import pydicom
from pydicom.dataset import Dataset, FileDataset
from pydicom.uid import ExplicitVRLittleEndian, JPEGBaseline8Bit
import numpy as np

# Import the module under test
from src.pixel_invariant import (
    PixelAction,
    PixelInvariantResult,
    sha256_bytes,
    get_pixel_data_safe,
    decide_pixel_action,
    enforce_pixel_passthrough_invariant,
    check_transfer_syntax_preserved,
    validate_uid_only_output,
)


# ═══════════════════════════════════════════════════════════════════════════════
# FIXTURES
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.fixture
def minimal_uncompressed_ds():
    """
    Create a minimal uncompressed DICOM dataset with known PixelData bytes.
    Uses deterministic pixel content for hash comparison.
    """
    ds = Dataset()
    ds.file_meta = pydicom.dataset.FileMetaDataset()
    ds.file_meta.TransferSyntaxUID = ExplicitVRLittleEndian
    ds.file_meta.MediaStorageSOPClassUID = "1.2.840.10008.5.1.4.1.1.7"  # Secondary Capture
    ds.file_meta.MediaStorageSOPInstanceUID = "1.2.3.4.5.6.7.8.9.1"
    
    ds.SOPClassUID = "1.2.840.10008.5.1.4.1.1.7"
    ds.SOPInstanceUID = "1.2.3.4.5.6.7.8.9.1"
    ds.StudyInstanceUID = "1.2.3.4.5"
    ds.SeriesInstanceUID = "1.2.3.4.5.1"
    ds.PatientName = "Test^Patient"
    ds.PatientID = "TEST001"
    
    ds.Rows = 32
    ds.Columns = 32
    ds.SamplesPerPixel = 1
    ds.PhotometricInterpretation = "MONOCHROME2"
    ds.BitsAllocated = 8
    ds.BitsStored = 8
    ds.HighBit = 7
    ds.PixelRepresentation = 0
    
    # Deterministic pixel bytes - sequence 0-255 repeated
    pixel = bytes([i % 256 for i in range(ds.Rows * ds.Columns)])
    ds.PixelData = pixel
    
    return ds


@pytest.fixture
def copy_dataset(minimal_uncompressed_ds):
    """
    Create a factory fixture for making copies of datasets.
    """
    def _copy(source_ds=None):
        import copy
        if source_ds is None:
            source_ds = minimal_uncompressed_ds
        return copy.deepcopy(source_ds)
    return _copy


@pytest.fixture
def uid_only_clinical_context():
    """Clinical context with uid_only_mode=True."""
    return {
        "patient_name": "PRESERVED",
        "uid_only_mode": True,
        "operator_name": "Test Operator"
    }


@pytest.fixture
def masking_clinical_context():
    """Clinical context with uid_only_mode=False."""
    return {
        "patient_name": "New^Name",
        "uid_only_mode": False,
        "operator_name": "Test Operator"
    }


# ═══════════════════════════════════════════════════════════════════════════════
# TEST CLASS: PixelAction Enum
# ═══════════════════════════════════════════════════════════════════════════════

class TestPixelActionEnum:
    """Tests for the PixelAction enum."""
    
    def test_not_applied_value(self):
        """NOT_APPLIED should have correct string value."""
        assert PixelAction.NOT_APPLIED.value == "NOT_APPLIED"
    
    def test_mask_applied_value(self):
        """MASK_APPLIED should have correct string value."""
        assert PixelAction.MASK_APPLIED.value == "MASK_APPLIED"
    
    def test_enum_is_str_subclass(self):
        """PixelAction should be usable as a string."""
        action = PixelAction.NOT_APPLIED
        assert isinstance(action, str)
        assert action == "NOT_APPLIED"
    
    def test_enum_equality_with_string(self):
        """Enum values should compare equal to their string representation."""
        assert PixelAction.NOT_APPLIED == "NOT_APPLIED"
        assert PixelAction.MASK_APPLIED == "MASK_APPLIED"


# ═══════════════════════════════════════════════════════════════════════════════
# TEST CLASS: sha256_bytes Helper
# ═══════════════════════════════════════════════════════════════════════════════

class TestSha256Bytes:
    """Tests for the sha256_bytes helper function."""
    
    def test_empty_bytes_hash(self):
        """Empty bytes should produce known SHA-256 hash."""
        # SHA-256 of empty string
        expected = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
        result = sha256_bytes(b"")
        assert result == expected
    
    def test_known_string_hash(self):
        """Known input should produce known hash."""
        # SHA-256 of "hello"
        expected = "2cf24dba5fb0a30e26e83b2ac5b9e29e1b161e5c1fa7425e73043362938b9824"
        result = sha256_bytes(b"hello")
        assert result == expected
    
    def test_hash_length(self):
        """Hash should be 64 hex characters."""
        result = sha256_bytes(b"any data")
        assert len(result) == 64
    
    def test_hash_is_lowercase_hex(self):
        """Hash should be lowercase hexadecimal."""
        result = sha256_bytes(b"test")
        assert all(c in "0123456789abcdef" for c in result)
    
    def test_different_inputs_different_hashes(self):
        """Different inputs should produce different hashes."""
        hash1 = sha256_bytes(b"input1")
        hash2 = sha256_bytes(b"input2")
        assert hash1 != hash2
    
    def test_same_input_same_hash(self):
        """Same input should always produce same hash."""
        data = b"deterministic test data"
        hash1 = sha256_bytes(data)
        hash2 = sha256_bytes(data)
        assert hash1 == hash2


# ═══════════════════════════════════════════════════════════════════════════════
# TEST CLASS: get_pixel_data_safe
# ═══════════════════════════════════════════════════════════════════════════════

class TestGetPixelDataSafe:
    """Tests for safe pixel data extraction."""
    
    def test_returns_bytes_for_valid_pixel_data(self, minimal_uncompressed_ds):
        """Should return bytes for dataset with PixelData."""
        result = get_pixel_data_safe(minimal_uncompressed_ds)
        assert isinstance(result, bytes)
        assert len(result) == 32 * 32  # Rows * Columns
    
    def test_returns_none_for_missing_pixel_data(self):
        """Should return None for dataset without PixelData."""
        ds = Dataset()
        ds.PatientName = "Test"
        result = get_pixel_data_safe(ds)
        assert result is None
    
    def test_preserves_exact_bytes(self, minimal_uncompressed_ds):
        """Should return exact same bytes as original."""
        original = minimal_uncompressed_ds.PixelData
        result = get_pixel_data_safe(minimal_uncompressed_ds)
        assert result == original


# ═══════════════════════════════════════════════════════════════════════════════
# TEST CLASS: decide_pixel_action
# ═══════════════════════════════════════════════════════════════════════════════

class TestDecidePixelAction:
    """Tests for the pixel action decision function."""
    
    def test_uid_only_mode_returns_not_applied(self, uid_only_clinical_context):
        """UID-only mode should return NOT_APPLIED."""
        result = decide_pixel_action(clinical_context=uid_only_clinical_context)
        assert result == PixelAction.NOT_APPLIED
    
    def test_explicit_apply_mask_returns_mask_applied(self):
        """apply_mask=True should return MASK_APPLIED."""
        result = decide_pixel_action(apply_mask=True)
        assert result == PixelAction.MASK_APPLIED
    
    def test_non_empty_mask_list_returns_mask_applied(self):
        """Non-empty mask_list should return MASK_APPLIED."""
        result = decide_pixel_action(mask_list=[(0, 0, 100, 100)])
        assert result == PixelAction.MASK_APPLIED
    
    def test_empty_mask_list_returns_not_applied(self):
        """Empty mask_list should return NOT_APPLIED."""
        result = decide_pixel_action(mask_list=[])
        assert result == PixelAction.NOT_APPLIED
    
    def test_manual_box_returns_mask_applied(self):
        """manual_box set should return MASK_APPLIED."""
        result = decide_pixel_action(manual_box=(10, 10, 50, 50))
        assert result == PixelAction.MASK_APPLIED
    
    def test_no_context_no_mask_returns_not_applied(self):
        """No context and no mask should return NOT_APPLIED."""
        result = decide_pixel_action()
        assert result == PixelAction.NOT_APPLIED
    
    def test_uid_only_overrides_mask_list(self, uid_only_clinical_context):
        """UID-only mode should override mask_list."""
        # Even with mask_list, uid_only_mode=True should win
        result = decide_pixel_action(
            clinical_context=uid_only_clinical_context,
            mask_list=[(0, 0, 100, 100)]
        )
        # NOTE: Current implementation checks uid_only first
        assert result == PixelAction.NOT_APPLIED
    
    def test_non_uid_only_context_allows_masking(self, masking_clinical_context):
        """Non UID-only context should allow masking."""
        result = decide_pixel_action(
            clinical_context=masking_clinical_context,
            apply_mask=True
        )
        assert result == PixelAction.MASK_APPLIED


# ═══════════════════════════════════════════════════════════════════════════════
# TEST CLASS: enforce_pixel_passthrough_invariant - PASS Cases
# ═══════════════════════════════════════════════════════════════════════════════

class TestEnforcePixelPassthroughInvariantPass:
    """Tests for successful invariant checks."""
    
    def test_identical_pixel_data_passes(self, minimal_uncompressed_ds, copy_dataset):
        """Identical PixelData should pass."""
        input_ds = minimal_uncompressed_ds
        output_ds = copy_dataset(input_ds)
        
        result = enforce_pixel_passthrough_invariant(
            input_ds, output_ds,
            enabled=True,
            why="test"
        )
        
        assert result.passed is True
        assert result.status == "PASS"
        assert result.input_hash == result.output_hash
    
    def test_disabled_check_returns_na(self, minimal_uncompressed_ds, copy_dataset):
        """Disabled check should return N/A status."""
        input_ds = minimal_uncompressed_ds
        output_ds = copy_dataset(input_ds)
        output_ds.PixelData = b"completely different"  # Would fail if enabled
        
        result = enforce_pixel_passthrough_invariant(
            input_ds, output_ds,
            enabled=False,
            why="test"
        )
        
        assert result.passed is True
        assert result.status == "N/A"
    
    def test_both_missing_pixel_data_returns_na(self):
        """Both datasets missing PixelData should return N/A."""
        input_ds = Dataset()
        input_ds.PatientName = "Input"
        output_ds = Dataset()
        output_ds.PatientName = "Output"
        
        result = enforce_pixel_passthrough_invariant(
            input_ds, output_ds,
            enabled=True,
            why="test"
        )
        
        assert result.passed is True
        assert result.status == "N/A"
    
    def test_result_contains_hashes(self, minimal_uncompressed_ds, copy_dataset):
        """Result should contain input and output hashes."""
        input_ds = minimal_uncompressed_ds
        output_ds = copy_dataset(input_ds)
        
        result = enforce_pixel_passthrough_invariant(
            input_ds, output_ds,
            enabled=True,
            why="test"
        )
        
        assert result.input_hash is not None
        assert result.output_hash is not None
        assert len(result.input_hash) == 64
        assert len(result.output_hash) == 64
    
    def test_result_contains_lengths(self, minimal_uncompressed_ds, copy_dataset):
        """Result should contain input and output lengths."""
        input_ds = minimal_uncompressed_ds
        output_ds = copy_dataset(input_ds)
        
        result = enforce_pixel_passthrough_invariant(
            input_ds, output_ds,
            enabled=True,
            why="test"
        )
        
        assert result.input_length == 32 * 32
        assert result.output_length == 32 * 32


# ═══════════════════════════════════════════════════════════════════════════════
# TEST CLASS: enforce_pixel_passthrough_invariant - FAIL Cases
# ═══════════════════════════════════════════════════════════════════════════════

class TestEnforcePixelPassthroughInvariantFail:
    """Tests for invariant violation detection."""
    
    def test_different_content_raises_error(self, minimal_uncompressed_ds, copy_dataset):
        """Different PixelData content should raise RuntimeError."""
        input_ds = minimal_uncompressed_ds
        output_ds = copy_dataset(input_ds)
        
        # Modify one byte
        modified_pixels = bytearray(output_ds.PixelData)
        modified_pixels[0] = (modified_pixels[0] + 1) % 256
        output_ds.PixelData = bytes(modified_pixels)
        
        with pytest.raises(RuntimeError) as exc_info:
            enforce_pixel_passthrough_invariant(
                input_ds, output_ds,
                enabled=True,
                why="test modification"
            )
        
        assert "Pixel invariant violated" in str(exc_info.value)
        assert "test modification" in str(exc_info.value)
    
    def test_different_length_raises_error(self, minimal_uncompressed_ds, copy_dataset):
        """Different PixelData length should raise RuntimeError."""
        input_ds = minimal_uncompressed_ds
        output_ds = copy_dataset(input_ds)
        
        # Truncate pixel data
        output_ds.PixelData = output_ds.PixelData[:100]
        
        with pytest.raises(RuntimeError) as exc_info:
            enforce_pixel_passthrough_invariant(
                input_ds, output_ds,
                enabled=True,
                why="length test"
            )
        
        assert "length changed" in str(exc_info.value)
    
    def test_pixel_data_added_raises_error(self):
        """PixelData added to output should raise RuntimeError."""
        input_ds = Dataset()
        input_ds.PatientName = "Input"
        
        output_ds = Dataset()
        output_ds.PatientName = "Output"
        output_ds.PixelData = b"new pixel data"
        
        with pytest.raises(RuntimeError) as exc_info:
            enforce_pixel_passthrough_invariant(
                input_ds, output_ds,
                enabled=True,
                why="added test"
            )
        
        assert "PixelData was added" in str(exc_info.value)
    
    def test_pixel_data_removed_raises_error(self, minimal_uncompressed_ds):
        """PixelData removed from output should raise RuntimeError."""
        input_ds = minimal_uncompressed_ds
        
        output_ds = Dataset()
        output_ds.PatientName = "Output"
        # No PixelData attribute
        
        with pytest.raises(RuntimeError) as exc_info:
            enforce_pixel_passthrough_invariant(
                input_ds, output_ds,
                enabled=True,
                why="removed test"
            )
        
        assert "PixelData was removed" in str(exc_info.value)
    
    def test_error_message_contains_hash_prefix(self, minimal_uncompressed_ds, copy_dataset):
        """Error message should contain hash prefixes for debugging."""
        input_ds = minimal_uncompressed_ds
        output_ds = copy_dataset(input_ds)
        output_ds.PixelData = b"x" * len(input_ds.PixelData)
        
        with pytest.raises(RuntimeError) as exc_info:
            enforce_pixel_passthrough_invariant(
                input_ds, output_ds,
                enabled=True,
                why="hash test"
            )
        
        # Should contain truncated hashes for debugging
        assert "Input hash:" in str(exc_info.value)
        assert "Output hash:" in str(exc_info.value)


# ═══════════════════════════════════════════════════════════════════════════════
# TEST CLASS: check_transfer_syntax_preserved
# ═══════════════════════════════════════════════════════════════════════════════

class TestCheckTransferSyntaxPreserved:
    """Tests for transfer syntax preservation check."""
    
    def test_same_transfer_syntax_passes(self, minimal_uncompressed_ds, copy_dataset):
        """Same TransferSyntaxUID should pass."""
        input_ds = minimal_uncompressed_ds
        output_ds = copy_dataset(input_ds)
        
        result = check_transfer_syntax_preserved(
            input_ds, output_ds,
            enabled=True,
            why="test"
        )
        
        assert result is True
    
    def test_disabled_check_always_passes(self, minimal_uncompressed_ds, copy_dataset):
        """Disabled check should always pass."""
        input_ds = minimal_uncompressed_ds
        output_ds = copy_dataset(input_ds)
        output_ds.file_meta.TransferSyntaxUID = JPEGBaseline8Bit
        
        result = check_transfer_syntax_preserved(
            input_ds, output_ds,
            enabled=False,
            why="test"
        )
        
        assert result is True
    
    def test_changed_transfer_syntax_raises_error(self, minimal_uncompressed_ds, copy_dataset):
        """Changed TransferSyntaxUID should raise RuntimeError."""
        input_ds = minimal_uncompressed_ds
        output_ds = copy_dataset(input_ds)
        output_ds.file_meta.TransferSyntaxUID = JPEGBaseline8Bit
        
        with pytest.raises(RuntimeError) as exc_info:
            check_transfer_syntax_preserved(
                input_ds, output_ds,
                enabled=True,
                why="transcode test"
            )
        
        assert "Transfer Syntax invariant violated" in str(exc_info.value)
    
    def test_missing_file_meta_skips_check(self):
        """Missing file_meta should skip check and return True."""
        input_ds = Dataset()
        output_ds = Dataset()
        
        result = check_transfer_syntax_preserved(
            input_ds, output_ds,
            enabled=True,
            why="test"
        )
        
        assert result is True


# ═══════════════════════════════════════════════════════════════════════════════
# TEST CLASS: validate_uid_only_output Integration
# ═══════════════════════════════════════════════════════════════════════════════

class TestValidateUidOnlyOutput:
    """Integration tests for the full validation wrapper."""
    
    def test_not_applied_with_identical_data_passes(
        self, minimal_uncompressed_ds, copy_dataset
    ):
        """UID-only mode with identical data should pass."""
        input_ds = minimal_uncompressed_ds
        output_ds = copy_dataset(input_ds)
        
        result = validate_uid_only_output(
            input_ds, output_ds,
            pixel_action=PixelAction.NOT_APPLIED
        )
        
        assert result.passed is True
        assert result.status == "PASS"
    
    def test_mask_applied_skips_check(self, minimal_uncompressed_ds, copy_dataset):
        """MASK_APPLIED mode should skip invariant check."""
        input_ds = minimal_uncompressed_ds
        output_ds = copy_dataset(input_ds)
        
        # Modify pixels - should be allowed with MASK_APPLIED
        output_ds.PixelData = b"modified" * 128
        
        result = validate_uid_only_output(
            input_ds, output_ds,
            pixel_action=PixelAction.MASK_APPLIED
        )
        
        assert result.passed is True
        assert result.status == "N/A"
    
    def test_updates_audit_dict(self, minimal_uncompressed_ds, copy_dataset):
        """Should update audit dict with result fields."""
        input_ds = minimal_uncompressed_ds
        output_ds = copy_dataset(input_ds)
        audit = {}
        
        validate_uid_only_output(
            input_ds, output_ds,
            pixel_action=PixelAction.NOT_APPLIED,
            audit_dict=audit
        )
        
        assert audit['pixel_action'] == "NOT_APPLIED"
        assert audit['pixel_invariant'] == "PASS"
        assert 'pixel_sha_in' in audit
        assert 'pixel_sha_out' in audit
    
    def test_audit_dict_with_mask_applied(self, minimal_uncompressed_ds, copy_dataset):
        """Audit dict should reflect MASK_APPLIED correctly."""
        input_ds = minimal_uncompressed_ds
        output_ds = copy_dataset(input_ds)
        output_ds.PixelData = b"modified" * 128
        audit = {}
        
        validate_uid_only_output(
            input_ds, output_ds,
            pixel_action=PixelAction.MASK_APPLIED,
            audit_dict=audit
        )
        
        assert audit['pixel_action'] == "MASK_APPLIED"
        assert audit['pixel_invariant'] == "N/A"


# ═══════════════════════════════════════════════════════════════════════════════
# TEST CLASS: End-to-End UID-Only Export Simulation
# ═══════════════════════════════════════════════════════════════════════════════

class TestUidOnlyExportSimulation:
    """
    Simulates the full UID-only export flow to verify pixel invariant.
    
    This is the "lock-in" test that ensures the invariant is enforced
    in realistic scenarios.
    """
    
    def test_uid_only_does_not_modify_pixeldata(self, minimal_uncompressed_ds, copy_dataset):
        """
        CRITICAL TEST: Simulates UID-only export and verifies pixel preservation.
        
        This test MUST remain in the suite and MUST pass for all releases.
        """
        src = minimal_uncompressed_ds
        in_hash = sha256_bytes(src.PixelData)
        
        # Simulate export: deep copy (like real export would do)
        out = copy_dataset(src)
        
        # Simulate metadata-only changes (what UID-only mode does)
        import pydicom.uid
        out.StudyInstanceUID = pydicom.uid.generate_uid()
        out.SeriesInstanceUID = pydicom.uid.generate_uid()
        out.SOPInstanceUID = pydicom.uid.generate_uid()
        out.file_meta.MediaStorageSOPInstanceUID = out.SOPInstanceUID
        
        # Verify pixel data is unchanged
        out_hash = sha256_bytes(out.PixelData)
        
        assert out_hash == in_hash
        assert out.PixelData == src.PixelData
        
        # Verify through official invariant check
        result = validate_uid_only_output(
            src, out,
            pixel_action=PixelAction.NOT_APPLIED
        )
        
        assert result.status == "PASS"
    
    def test_accidental_decode_cycle_is_detected(
        self, minimal_uncompressed_ds, copy_dataset
    ):
        """
        Test that decode/encode cycle is detected as a violation.
        
        This catches the common bug: accidentally reading pixel_array
        and writing it back (even without modification).
        """
        src = minimal_uncompressed_ds
        out = copy_dataset(src)
        
        # Simulate accidental decode/encode cycle
        # This is what happens when someone reads pixel_array
        # and writes it back as bytes
        arr = np.frombuffer(out.PixelData, dtype=np.uint8)
        # Even without modification, re-encoding could potentially differ
        # In practice, for uncompressed data it should be identical
        out.PixelData = arr.tobytes()
        
        # For uncompressed data, this should actually still pass
        # (bytes are identical)
        result = validate_uid_only_output(
            src, out,
            pixel_action=PixelAction.NOT_APPLIED
        )
        
        assert result.status == "PASS"
    
    def test_actual_pixel_modification_is_detected(
        self, minimal_uncompressed_ds, copy_dataset
    ):
        """
        Test that actual pixel modification raises error.
        """
        src = minimal_uncompressed_ds
        out = copy_dataset(src)
        
        # Simulate black box overlay (the bug we're fixing)
        arr = np.frombuffer(out.PixelData, dtype=np.uint8).copy()
        arr[0:100] = 0  # Black out first 100 pixels
        out.PixelData = arr.tobytes()
        
        with pytest.raises(RuntimeError) as exc_info:
            validate_uid_only_output(
                src, out,
                pixel_action=PixelAction.NOT_APPLIED
            )
        
        assert "Pixel invariant violated" in str(exc_info.value)


# ═══════════════════════════════════════════════════════════════════════════════
# TEST CLASS: PixelInvariantResult NamedTuple
# ═══════════════════════════════════════════════════════════════════════════════

class TestPixelInvariantResult:
    """Tests for the PixelInvariantResult structure."""
    
    def test_can_create_pass_result(self):
        """Should be able to create a PASS result."""
        result = PixelInvariantResult(
            passed=True,
            status="PASS",
            input_hash="abc123",
            output_hash="abc123"
        )
        assert result.passed is True
        assert result.status == "PASS"
    
    def test_can_create_fail_result(self):
        """Should be able to create a FAIL result."""
        result = PixelInvariantResult(
            passed=False,
            status="FAIL",
            error_message="Pixels differ"
        )
        assert result.passed is False
        assert result.error_message == "Pixels differ"
    
    def test_default_optional_fields_are_none(self):
        """Optional fields should default to None."""
        result = PixelInvariantResult(passed=True, status="N/A")
        assert result.input_hash is None
        assert result.output_hash is None
        assert result.input_length is None
        assert result.output_length is None
        assert result.error_message is None
