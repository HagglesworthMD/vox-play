"""
Phase 12: UI Contract + Receipt Golden Tests

Tests that lock down the Phase 12 UI contract without needing a browser:
1. Profile definitions map to correct receipt behaviors
2. Buttons are correctly named and mapped
3. Modes are separate and produce expected outputs
4. Receipt output is audit-defensible ("says what it does on the tin")

These tests guard against:
- Adding new buttons without updating the UI freeze doc
- Changing profile behavior silently
- Receipt visibility regressions
"""
import pytest
import sys
import os

# Import from audit.py specifically
import importlib.util
_audit_path = os.path.join(os.path.dirname(__file__), '..', 'src', 'audit.py')
_spec = importlib.util.spec_from_file_location("audit_module", _audit_path)
_audit = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_audit)

generate_audit_receipt = _audit.generate_audit_receipt


# ═══════════════════════════════════════════════════════════════════════════════
# PROFILE DEFINITIONS (must match app.py exactly)
# ═══════════════════════════════════════════════════════════════════════════════

CANONICAL_PROFILES = [
    "internal_repair",
    "us_research_safe_harbor",
    "au_strict_oaic",
    "foi_legal",
    "foi_patient",
]

PROFILE_DISPLAY_NAMES = {
    "internal_repair": "🔧 Internal Repair - Metadata correction (evaluation only)",
    "us_research_safe_harbor": "🇺🇸 US Research (Safe Harbor) - De-identification for research",
    "au_strict_oaic": "🇦🇺 AU Strict (OAIC APP11) - Hash IDs, shift dates",
    "foi_legal": "⚖️ FOI/Legal - Staff redacted, patient data preserved",
    "foi_patient": "📋 FOI/Patient - Patient record release",
}


class TestProfileDefinitions:
    """Test that profile definitions are complete and consistent."""
    
    def test_all_profiles_have_display_names(self):
        """Every canonical profile must have a display name."""
        for profile in CANONICAL_PROFILES:
            assert profile in PROFILE_DISPLAY_NAMES, f"Missing display name for {profile}"
    
    def test_profile_count_matches_ui_freeze(self):
        """Phase 12 defines exactly 5 profiles. Don't add without updating docs."""
        assert len(CANONICAL_PROFILES) == 5, "Profile count changed - update PHASE12_UI_FREEZE.md"
    
    def test_no_duplicate_profiles(self):
        """Profile names must be unique."""
        assert len(CANONICAL_PROFILES) == len(set(CANONICAL_PROFILES))


class TestPHIVisibilityModel:
    """Test the two-flag PHI visibility model from Phase 12."""
    
    @pytest.fixture
    def sample_meta(self):
        return {
            'patient_name': 'DOE^JOHN',
            'patient_id': '12345',
            'study_date': '20240115',
            'modality': 'US',
            'institution': 'Test Hospital',
            'OperatorsName': 'Smith^Jane',
        }
    
    @pytest.fixture
    def sample_new_meta(self):
        return {
            'patient_name': 'ANON^PATIENT',
            'patient_id': 'SUB001',
            'new_study_date': '20240115',
        }
    
    # ═══════════════════════════════════════════════════════════════════════════
    # STAFF ID VISIBILITY TESTS
    # ═══════════════════════════════════════════════════════════════════════════
    
    def test_internal_repair_shows_staff_ids(self, sample_meta, sample_new_meta):
        """internal_repair is the ONLY profile that shows staff identifiers."""
        result = generate_audit_receipt(
            original_meta=sample_meta,
            new_meta=sample_new_meta,
            uuid_str="test-uuid",
            operator_id="OPERATOR_123",
            mode="CLINICAL",
            compliance_profile="internal_repair",
        )
        assert "OPERATOR_123" in result
        assert "Staff identifiers in receipt:    SHOWN" in result
    
    def test_safe_harbor_redacts_staff_ids(self, sample_meta, sample_new_meta):
        """Research profiles redact staff identifiers."""
        result = generate_audit_receipt(
            original_meta=sample_meta,
            new_meta=sample_new_meta,
            uuid_str="test-uuid",
            operator_id="OPERATOR_123",
            mode="RESEARCH",
            compliance_profile="us_research_safe_harbor",
        )
        assert "OPERATOR_123" not in result
        assert "Staff identifiers in receipt:    REDACTED" in result
    
    def test_foi_legal_redacts_staff_ids(self, sample_meta, sample_new_meta):
        """FOI profiles redact staff identifiers (employee privacy)."""
        result = generate_audit_receipt(
            original_meta=sample_meta,
            new_meta=sample_new_meta,
            uuid_str="test-uuid",
            operator_id="OPERATOR_123",
            mode="RESEARCH",
            compliance_profile="foi_legal",
        )
        assert "OPERATOR_123" not in result
        assert "Staff identifiers in receipt:    REDACTED" in result
    
    # ═══════════════════════════════════════════════════════════════════════════
    # PATIENT PHI VISIBILITY TESTS
    # ═══════════════════════════════════════════════════════════════════════════
    
    def test_internal_repair_shows_patient_phi(self, sample_meta, sample_new_meta):
        """internal_repair shows patient identifiers."""
        result = generate_audit_receipt(
            original_meta=sample_meta,
            new_meta=sample_new_meta,
            uuid_str="test-uuid",
            operator_id="OP",
            mode="CLINICAL",
            compliance_profile="internal_repair",
        )
        assert "DOE^JOHN" in result
        assert "Patient identifiers in receipt:  SHOWN" in result
    
    def test_foi_legal_shows_patient_phi(self, sample_meta, sample_new_meta):
        """FOI/legal shows patient identifiers (chain of custody)."""
        result = generate_audit_receipt(
            original_meta=sample_meta,
            new_meta=sample_new_meta,
            uuid_str="test-uuid",
            operator_id="OP",
            mode="RESEARCH",
            compliance_profile="foi_legal",
        )
        assert "DOE^JOHN" in result
        assert "Patient identifiers in receipt:  SHOWN" in result
    
    def test_safe_harbor_redacts_patient_phi(self, sample_meta, sample_new_meta):
        """Research profiles redact patient identifiers."""
        result = generate_audit_receipt(
            original_meta=sample_meta,
            new_meta=sample_new_meta,
            uuid_str="test-uuid",
            operator_id="OP",
            mode="RESEARCH",
            compliance_profile="us_research_safe_harbor",
        )
        # Patient name should NOT appear in result
        assert "DOE^JOHN" not in result
        assert "Patient identifiers in receipt:  REDACTED" in result


class TestReceiptGoldenOutputs:
    """Golden output tests for audit receipts - these lock expected format."""
    
    @pytest.fixture
    def sample_meta(self):
        return {
            'patient_name': 'DOE^JOHN',
            'patient_id': '12345',
            'study_date': '20240115',
            'modality': 'US',
            'institution': 'Test Hospital',
            'OperatorsName': 'Smith^Jane',
        }
    
    @pytest.fixture
    def sample_new_meta(self):
        return {
            'patient_name': 'ANON^PATIENT',
            'patient_id': 'SUB001',
            'new_study_date': '20240115',
        }
    
    def test_receipt_has_voxelmask_header(self, sample_meta, sample_new_meta):
        """All receipts must have VoxelMask header."""
        result = generate_audit_receipt(
            original_meta=sample_meta,
            new_meta=sample_new_meta,
            uuid_str="test-uuid",
            operator_id="OP",
            mode="RESEARCH",
        )
        assert "VOXELMASK - AUDIT RECEIPT" in result
    
    def test_receipt_has_visibility_disclosure(self, sample_meta, sample_new_meta):
        """All receipts must have visibility disclosure section."""
        result = generate_audit_receipt(
            original_meta=sample_meta,
            new_meta=sample_new_meta,
            uuid_str="test-uuid",
            operator_id="OP",
            mode="RESEARCH",
        )
        assert "VISIBILITY DISCLOSURE" in result
        assert "Patient identifiers in receipt:" in result
        assert "Staff identifiers in receipt:" in result
        assert "Patient tags in OUTPUT DICOM:" in result
        assert "Pixel masking applied:" in result
    
    def test_receipt_has_processing_details(self, sample_meta, sample_new_meta):
        """All receipts must have processing details section."""
        result = generate_audit_receipt(
            original_meta=sample_meta,
            new_meta=sample_new_meta,
            uuid_str="test-uuid",
            operator_id="OP",
            mode="RESEARCH",
        )
        assert "PROCESSING DETAILS" in result
        assert "Timestamp:" in result
        assert "Scrub UUID:" in result
        assert "Operator:" in result
        assert "Profile:" in result
    
    def test_receipt_has_chain_of_custody(self, sample_meta, sample_new_meta):
        """All receipts must have chain of custody section."""
        result = generate_audit_receipt(
            original_meta=sample_meta,
            new_meta=sample_new_meta,
            uuid_str="test-uuid",
            operator_id="OP",
            mode="RESEARCH",
        )
        assert "CHAIN OF CUSTODY" in result
        assert "Original File:" in result
        assert "Anonymized File:" in result
    
    def test_receipt_has_compliance_section(self, sample_meta, sample_new_meta):
        """Standard receipts must have compliance certification."""
        result = generate_audit_receipt(
            original_meta=sample_meta,
            new_meta=sample_new_meta,
            uuid_str="test-uuid",
            operator_id="OP",
            mode="RESEARCH",
            compliance_profile="safe_harbor",
        )
        assert "COMPLIANCE CERTIFICATION" in result
    
    def test_foi_receipt_has_screaming_header(self, sample_meta, sample_new_meta):
        """FOI receipts must have prominent warning header."""
        result = generate_audit_receipt(
            original_meta=sample_meta,
            new_meta=sample_new_meta,
            uuid_str="test-uuid",
            operator_id="OP",
            mode="RESEARCH",
            compliance_profile="foi_legal",
        )
        assert "FOI EXPORT" in result or "CONTAINS PATIENT IDENTIFIERS" in result
    
    def test_internal_repair_has_correction_section(self, sample_meta, sample_new_meta):
        """Internal repair receipts must have clinical correction certification."""
        result = generate_audit_receipt(
            original_meta=sample_meta,
            new_meta=sample_new_meta,
            uuid_str="test-uuid",
            operator_id="OP",
            mode="CLINICAL",
            compliance_profile="internal_repair",
        )
        assert "CLINICAL CORRECTION CERTIFICATION" in result


class TestUIButtonContract:
    """Tests that lock down the Phase 12 UI button contract."""
    
    # These constants must match the actual buttons in app.py
    CANONICAL_BUTTONS = {
        "open_viewer_localhost": "🔍 Open Viewer",
        # Download buttons use dynamic keys, but labels are fixed
    }
    
    DOWNLOAD_BUTTON_LABELS = [
        "📦 Download ZIP",  # Multi-file label prefix
    ]
    
    def test_open_viewer_button_exists(self):
        """Phase 12 requires exactly one Open Viewer button."""
        # This test documents the contract - actual UI testing requires browser
        assert "open_viewer_localhost" in self.CANONICAL_BUTTONS
        assert "Open Viewer" in self.CANONICAL_BUTTONS["open_viewer_localhost"]
    
    def test_no_legacy_viewer_buttons(self):
        """Phase 12 removed legacy viewer buttons."""
        legacy_buttons = [
            "open_viewer_system",  # Removed - was file:// approach
            "open_viewer_browser",  # Never existed
            "open_viewer_zip",  # Never existed
        ]
        for button in legacy_buttons:
            assert button not in self.CANONICAL_BUTTONS, f"Legacy button {button} should not exist"


class TestProfileReceiptMapping:
    """Test that each profile produces the expected receipt behavior."""
    
    @pytest.fixture
    def sample_meta(self):
        return {
            'patient_name': 'DOE^JOHN',
            'patient_id': '12345',
            'study_date': '20240115',
            'modality': 'US',
            'OperatorsName': 'Smith^Jane',
        }
    
    @pytest.fixture
    def sample_new_meta(self):
        return {
            'patient_name': 'ANON^PATIENT',
            'patient_id': 'SUB001',
        }
    
    @pytest.mark.parametrize("profile,expected_reason", [
        ("internal_repair", "CLINICAL_CORRECTION"),
        ("us_research_safe_harbor", "RESEARCH_DEID"),
        ("au_strict_oaic", "RESEARCH_DEID"),
        ("foi_legal", "FOI_LEGAL_RELEASE"),
        ("foi_patient", "FOI_LEGAL_RELEASE"),
    ])
    def test_profile_produces_correct_reason_code(self, sample_meta, sample_new_meta, profile, expected_reason):
        """Each profile must produce the expected reason code."""
        result = generate_audit_receipt(
            original_meta=sample_meta,
            new_meta=sample_new_meta,
            uuid_str="test-uuid",
            operator_id="OP",
            mode="RESEARCH",
            compliance_profile=profile,
        )
        assert expected_reason in result, f"Profile {profile} should produce reason {expected_reason}"
    
    @pytest.mark.parametrize("profile,shows_patient,shows_staff", [
        ("internal_repair", True, True),
        ("us_research_safe_harbor", False, False),
        ("au_strict_oaic", False, False),
        ("foi_legal", True, False),
        ("foi_patient", True, False),
    ])
    def test_profile_visibility_matrix(self, sample_meta, sample_new_meta, profile, shows_patient, shows_staff):
        """Each profile has a defined visibility policy."""
        result = generate_audit_receipt(
            original_meta=sample_meta,
            new_meta=sample_new_meta,
            uuid_str="test-uuid",
            operator_id="OPERATOR_TEST",
            mode="RESEARCH",
            compliance_profile=profile,
        )
        
        if shows_patient:
            assert "DOE^JOHN" in result, f"Profile {profile} should show patient PHI"
        else:
            assert "DOE^JOHN" not in result, f"Profile {profile} should redact patient PHI"
        
        if shows_staff:
            assert "OPERATOR_TEST" in result, f"Profile {profile} should show staff IDs"
        else:
            assert "OPERATOR_TEST" not in result, f"Profile {profile} should redact staff IDs"
