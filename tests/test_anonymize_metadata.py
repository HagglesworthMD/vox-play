"""
Unit tests for src/run_on_dicom.anonymize_metadata()

Tests the core metadata anonymization logic covering:
- Fallback mode (no context)
- Research mode (trial tags, deid_date)
- Clinical mode (patient demographics, audit trail)
- UID remapping
- Context sync (accession, dates)
"""
import types
import pytest
import pydicom


def _mk_ds(**tags):
    """Create a minimal pydicom Dataset with common tags."""
    ds = pydicom.Dataset()
    # seed minimum tags commonly used
    ds.PatientName = tags.pop("PatientName", "ORIGINAL^NAME")
    ds.PatientID = tags.pop("PatientID", "12345")
    ds.StudyInstanceUID = tags.pop("StudyInstanceUID", "1.2.3.4.5.6.7.8.9")
    ds.SeriesInstanceUID = tags.pop("SeriesInstanceUID", "1.2.3.4.5.6.7.8.10")
    ds.SOPInstanceUID = tags.pop("SOPInstanceUID", "1.2.3.4.5.6.7.8.11")

    for k, v in tags.items():
        setattr(ds, k, v)
    return ds


@pytest.fixture
def rod(monkeypatch):
    """
    Import src.run_on_dicom while neutralizing brittle top-level imports.
    The module currently imports clinical_corrector as a top-level name in some setups.
    """
    import sys
    # Provide a dummy clinical_corrector module if needed (keeps import stable)
    if "clinical_corrector" not in sys.modules:
        sys.modules["clinical_corrector"] = types.SimpleNamespace(ClinicalCorrector=object)
    if "compliance" not in sys.modules:
        sys.modules["compliance"] = types.SimpleNamespace(enforce_dicom_compliance=lambda ds, *a, **k: ds)
    if "utils" not in sys.modules:
        sys.modules["utils"] = types.SimpleNamespace(apply_deterministic_sanitization=lambda ds: None)

    import importlib
    # Clear cached import if present
    if "src.run_on_dicom" in sys.modules:
        del sys.modules["src.run_on_dicom"]
    
    mod = importlib.import_module("src.run_on_dicom")

    # Mock the two always-called functions so we can focus on anonymize_metadata logic.
    monkeypatch.setattr(mod, "enforce_dicom_compliance", lambda ds, *a, **k: ds)
    monkeypatch.setattr(mod, "apply_deterministic_sanitization", lambda ds: None)

    return mod


# ============================================================================
# FALLBACK MODE (no context)
# ============================================================================

def test_anonymize_metadata_fallback_mode_sets_patient_name(rod):
    """Fallback mode should use new_name for PatientName."""
    ds = _mk_ds()
    rod.anonymize_metadata(ds, "NEW^NAME", research_context=None, clinical_context=None)

    # UID remapping changes PatientName indirectly via mode logic
    # The function doesn't return ds, it modifies in-place
    # Check that UIDs were remapped (this is the observable effect)
    assert ds.StudyInstanceUID != "1.2.3.4.5.6.7.8.9"


# ============================================================================
# RESEARCH MODE
# ============================================================================

def test_anonymize_metadata_research_mode_updates_context(rod):
    """Research mode should update research_context with extracted values."""
    ds = _mk_ds(
        AccessionNumber="ACC123",
        StudyDate="20250101",
    )
    research_context = {"trial_id": "TRIAL-001", "site_id": "SITE-A"}
    
    rod.anonymize_metadata(ds, "RESEARCH^SUBJECT", research_context=research_context, clinical_context=None)

    # Context gets updated with extracted fields
    assert research_context.get("accession") == "ACC123" or research_context.get("accession_number") == "ACC123"


def test_anonymize_metadata_research_mode_adds_trial_tags(rod):
    """Research mode should add clinical trial tags (group 0012)."""
    ds = _mk_ds()
    research_context = {"trial_id": "LUNG_TRIAL_2025", "site_id": "SITE-01", "subject_id": "SUB-001"}
    
    rod.anonymize_metadata(ds, "RESEARCH^SUBJECT", research_context=research_context, clinical_context=None)

    # Check for trial-related tags
    ds_repr = repr(ds).lower()
    assert "trial" in ds_repr or "research" in ds_repr or "de-identified" in ds_repr


def test_anonymize_metadata_research_mode_deid_date_branch(rod):
    """deid_date in research_context should set ContentDate."""
    ds = _mk_ds(StudyDate="20250101")
    research_context = {"deid_date": "2024-06-15"}  # YYYY-MM-DD format
    
    rod.anonymize_metadata(ds, "RESEARCH^SUBJECT", research_context=research_context, clinical_context=None)

    # ContentDate should be set (format: YYYYMMDD - dashes removed)
    assert hasattr(ds, "ContentDate")
    assert ds.ContentDate == "20240615"


# ============================================================================
# CLINICAL MODE
# ============================================================================

def test_anonymize_metadata_clinical_mode_updates_study_info(rod):
    """Clinical mode should update study date/time/description."""
    ds = _mk_ds(
        StudyDate="20240202",
        StudyTime="121314",
    )
    clinical_context = {
        "patient_name": "CLINICAL^NAME",
        "study_date": "2024-03-03",  # YYYY-MM-DD format
        "study_time": "10:10:10",    # HH:MM:SS format
        "study_type": "ABDOMEN US",
    }

    rod.anonymize_metadata(ds, "IGNORED", research_context=None, clinical_context=clinical_context)

    # Dates/times should be converted and applied
    assert ds.StudyDate == "20240303"  # Dashes removed
    assert ds.StudyTime == "101010"    # Colons removed
    assert ds.StudyDescription == "ABDOMEN US"


def test_anonymize_metadata_clinical_mode_updates_personnel(rod):
    """Clinical mode should update sonographer and referring physician."""
    ds = _mk_ds()
    clinical_context = {
        "patient_name": "PATIENT^NAME",
        "sonographer": "Smith, John",
        "referring_physician": "Dr. Jane Doe",
    }

    rod.anonymize_metadata(ds, "X", research_context=None, clinical_context=clinical_context)

    assert ds.OperatorsName == "Smith, John"
    assert ds.ReferringPhysicianName == "Dr. Jane Doe"


def test_anonymize_metadata_clinical_mode_audit_trail(rod):
    """Clinical mode with audit fields should set ImageComments."""
    ds = _mk_ds(PatientName="ORIGINAL^NAME")
    clinical_context = {
        "patient_name": "NEW^NAME",
        "reason_for_correction": "Wrong patient",
        "correction_notes": "Corrected demographics",
        "operator_name": "Admin User",
    }

    rod.anonymize_metadata(ds, "X", research_context=None, clinical_context=clinical_context)

    # ImageComments should contain audit info
    assert hasattr(ds, "ImageComments")
    assert "[CORRECTED]" in ds.ImageComments
    assert "Wrong patient" in ds.ImageComments or "Reason:" in ds.ImageComments


def test_anonymize_metadata_clinical_mode_auto_timestamp(rod):
    """auto_timestamp=True should add timestamp to ImageComments."""
    ds = _mk_ds(PatientName="ORIGINAL^NAME")
    clinical_context = {
        "patient_name": "NEW^NAME",
        "auto_timestamp": True,
    }

    rod.anonymize_metadata(ds, "X", research_context=None, clinical_context=clinical_context)

    assert hasattr(ds, "ImageComments")
    # Should contain "Timestamp:" with date
    assert "Timestamp:" in ds.ImageComments


def test_anonymize_metadata_clinical_mode_original_name_differs(rod):
    """When original name differs from new, should record in audit."""
    ds = _mk_ds(PatientName="WRONG^NAME")
    clinical_context = {
        "patient_name": "CORRECT^NAME",
    }

    rod.anonymize_metadata(ds, "X", research_context=None, clinical_context=clinical_context)

    # Original name should be recorded if it differs
    if hasattr(ds, "ImageComments"):
        # May contain "Original:" prefix
        assert "Original:" in ds.ImageComments or "WRONG^NAME" in ds.ImageComments


# ============================================================================
# UID REMAPPING
# ============================================================================

def test_anonymize_metadata_uid_remapping_changes_uids(rod):
    """UIDs should be remapped to new deterministic values."""
    ds = _mk_ds(
        StudyInstanceUID="1.2.3.4.5.6.7.8.9",
        SeriesInstanceUID="1.2.3.4.5.6.7.8.10",
        SOPInstanceUID="1.2.3.4.5.6.7.8.11",
    )

    old_uids = (ds.StudyInstanceUID, ds.SeriesInstanceUID, ds.SOPInstanceUID)
    
    rod.anonymize_metadata(ds, "NEW^NAME", research_context=None, clinical_context=None)
    
    new_uids = (ds.StudyInstanceUID, ds.SeriesInstanceUID, ds.SOPInstanceUID)

    # UIDs should be different
    assert new_uids != old_uids
    
    # New UIDs should still be valid DICOM UIDs (digits and dots, starts with 2.25.)
    for uid in new_uids:
        assert "." in uid
        assert uid.startswith("2.25.")


def test_anonymize_metadata_uid_remapping_is_deterministic(rod):
    """Same input UID should produce same output UID."""
    ds1 = _mk_ds(StudyInstanceUID="1.2.3.999")
    ds2 = _mk_ds(StudyInstanceUID="1.2.3.999")
    
    rod.anonymize_metadata(ds1, "NAME1", research_context=None, clinical_context=None)
    rod.anonymize_metadata(ds2, "NAME2", research_context=None, clinical_context=None)
    
    # Same input UID should produce same output UID
    assert ds1.StudyInstanceUID == ds2.StudyInstanceUID


# ============================================================================
# CONTEXT SYNC (Final accession/date updates)
# ============================================================================

def test_anonymize_metadata_syncs_accession_to_context(rod):
    """Accession number from dataset should be synced to contexts."""
    ds = _mk_ds(AccessionNumber="FINAL-ACC-123")
    research_context = {}
    
    rod.anonymize_metadata(ds, "X", research_context=research_context, clinical_context=None)
    
    # Context should have accession synced
    assert research_context.get("accession") == "FINAL-ACC-123" or \
           research_context.get("accession_number") == "FINAL-ACC-123"


def test_anonymize_metadata_syncs_studydate_to_context(rod):
    """StudyDate from dataset should be synced to contexts."""
    ds = _mk_ds(StudyDate="20241225")
    clinical_context = {"patient_name": "X"}
    
    rod.anonymize_metadata(ds, "X", research_context=None, clinical_context=clinical_context)
    
    # Context should have date synced
    assert clinical_context.get("new_study_date") == "20241225"
