"""
Unit tests for compliance_engine.py - High-ROI Coverage

Targets all missing line ranges to boost coverage from ~58% to ~85%+.
Uses minimal pydicom datasets and deterministic mocking.

Test Categories:
A) _shift_date() branch matrix
B) _hash_patient_id() branch matrix
C) _fix_corrupted_headers() branch matrix
D) _apply_us_kill_switch() branch matrix
E) _regenerate_uids() branch matrix
F) _apply_internal_repair() branch matrix
G) _apply_us_research_safe_harbor() branch matrix
H) _apply_au_strict_oaic() branch matrix
I) process_dataset() branch matrix
J) apply_compliance() wrapper
"""
import os
import sys
from unittest.mock import patch, MagicMock

import pytest
import pydicom
from pydicom.dataset import Dataset, FileDataset, FileMetaDataset
from pydicom.uid import ExplicitVRLittleEndian, ImplicitVRLittleEndian

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from compliance_engine import (
    UIDManager,
    DicomComplianceManager,
    apply_compliance,
)


# ============================================================================
# FIXTURES
# ============================================================================

@pytest.fixture
def ds_base():
    """
    Create a minimal pydicom Dataset for testing.
    Includes common PHI fields and UIDs.
    """
    ds = Dataset()
    
    # Patient identifiers
    ds.PatientID = "P123"
    ds.PatientName = "DOE^JANE"
    ds.PatientBirthDate = "19801231"
    
    # Study/Series info
    ds.StudyDate = "20240115"
    ds.SeriesDate = "20240116"
    ds.Modality = "CT"
    
    # UIDs
    ds.StudyInstanceUID = "1.2.840.10008.1.1.1"
    ds.SeriesInstanceUID = "1.2.840.10008.1.1.2"
    ds.SOPInstanceUID = "1.2.840.10008.1.1.3"
    ds.SOPClassUID = pydicom.uid.CTImageStorage
    
    # File meta (incomplete - to test header fixing)
    ds.file_meta = FileMetaDataset()
    # Intentionally missing TransferSyntaxUID, MediaStorageSOPClassUID, etc.
    
    return ds


@pytest.fixture
def ds_with_complete_file_meta(ds_base):
    """Dataset with complete file_meta for UID tests."""
    ds = ds_base
    ds.file_meta.TransferSyntaxUID = ExplicitVRLittleEndian
    ds.file_meta.MediaStorageSOPClassUID = ds.SOPClassUID
    ds.file_meta.MediaStorageSOPInstanceUID = ds.SOPInstanceUID
    return ds


@pytest.fixture
def uid_sequence():
    """Generator for deterministic UID values."""
    counter = [0]
    def _generate():
        counter[0] += 1
        return f"1.2.3.{counter[0]}"
    return _generate


@pytest.fixture
def manager():
    """Fresh DicomComplianceManager instance."""
    return DicomComplianceManager()


# ============================================================================
# A) _shift_date() BRANCH MATRIX
# ============================================================================

class TestShiftDate:
    """Tests for _shift_date() method."""
    
    def test_shift_date_empty_or_short_returns_original(self, manager):
        """Empty or short date strings should be returned unchanged."""
        # Covers line 167
        assert manager._shift_date("", -30) == ""
        assert manager._shift_date("2024", -30) == "2024"
        assert manager._shift_date("202401", -30) == "202401"
    
    def test_shift_date_invalid_format_returns_original(self, manager):
        """Invalid date format should be returned unchanged."""
        # Covers lines 174-175
        assert manager._shift_date("20241340", -30) == "20241340"  # Invalid month
        assert manager._shift_date("notadate", -30) == "notadate"
        assert manager._shift_date("2024-01-15", -30) == "2024-01-15"  # Wrong format
    
    def test_shift_date_valid_shifts_by_days(self, manager):
        """Valid date should be shifted by specified days."""
        # 20240115 - 20 days = 20231226
        result = manager._shift_date("20240115", -20)
        assert result == "20231226"
        
        # Shift forward
        result = manager._shift_date("20240115", 10)
        assert result == "20240125"


# ============================================================================
# B) _hash_patient_id() BRANCH MATRIX
# ============================================================================

class TestHashPatientId:
    """Tests for _hash_patient_id() method."""
    
    def test_hash_patient_id_prefix_and_length(self, manager):
        """Hash should have ANON_ prefix and 12 hex uppercase chars."""
        # Covers lines 187-188
        result = manager._hash_patient_id("P123")
        
        assert result.startswith("ANON_")
        suffix = result[5:]  # Remove "ANON_"
        assert len(suffix) == 12
        assert suffix.isupper()
        assert all(c in "0123456789ABCDEF" for c in suffix)
    
    def test_hash_patient_id_is_deterministic(self, manager):
        """Same PatientID should always produce same hash."""
        result1 = manager._hash_patient_id("P123")
        result2 = manager._hash_patient_id("P123")
        assert result1 == result2
        
        # Different ID produces different hash
        result3 = manager._hash_patient_id("P456")
        assert result3 != result1


# ============================================================================
# C) _fix_corrupted_headers() BRANCH MATRIX
# ============================================================================

class TestFixCorruptedHeaders:
    """Tests for _fix_corrupted_headers() method."""
    
    def test_fix_headers_creates_file_meta_and_sets_transfer_syntax(self, manager):
        """Should create file_meta and set TransferSyntaxUID if missing."""
        # Covers lines 202, 205-206
        ds = Dataset()
        ds.SOPClassUID = pydicom.uid.CTImageStorage
        ds.SOPInstanceUID = "1.2.3.4"
        # No file_meta at all
        
        result = manager._fix_corrupted_headers(ds)
        
        assert hasattr(result, 'file_meta')
        assert result.file_meta.TransferSyntaxUID == ImplicitVRLittleEndian
        log = "\n".join(manager.get_processing_log())
        assert "Fixed: Missing TransferSyntaxUID" in log
    
    def test_fix_headers_sets_media_storage_sop_class_uid(self, manager):
        """Should set MediaStorageSOPClassUID from SOPClassUID."""
        # Covers lines 205-206, 210-212
        ds = Dataset()
        ds.SOPClassUID = pydicom.uid.CTImageStorage
        ds.SOPInstanceUID = "1.2.3.4"
        ds.file_meta = FileMetaDataset()
        ds.file_meta.TransferSyntaxUID = ExplicitVRLittleEndian
        # Missing MediaStorageSOPClassUID
        
        result = manager._fix_corrupted_headers(ds)
        
        assert result.file_meta.MediaStorageSOPClassUID == pydicom.uid.CTImageStorage
        log = "\n".join(manager.get_processing_log())
        assert "MediaStorageSOPClassUID" in log
    
    def test_fix_headers_sets_media_storage_sop_instance_uid(self, manager):
        """Should set MediaStorageSOPInstanceUID from SOPInstanceUID."""
        # Covers lines 216-218
        ds = Dataset()
        ds.SOPClassUID = pydicom.uid.CTImageStorage
        ds.SOPInstanceUID = "1.2.3.4.5"
        ds.file_meta = FileMetaDataset()
        ds.file_meta.TransferSyntaxUID = ExplicitVRLittleEndian
        ds.file_meta.MediaStorageSOPClassUID = pydicom.uid.CTImageStorage
        # Missing MediaStorageSOPInstanceUID
        
        result = manager._fix_corrupted_headers(ds)
        
        assert result.file_meta.MediaStorageSOPInstanceUID == "1.2.3.4.5"
        log = "\n".join(manager.get_processing_log())
        assert "MediaStorageSOPInstanceUID" in log


# ============================================================================
# D) _apply_us_kill_switch() BRANCH MATRIX
# ============================================================================

class TestApplyUsKillSwitch:
    """Tests for _apply_us_kill_switch() method."""
    
    def test_us_kill_switch_sets_burnedinannotation_for_us(self, manager):
        """Should set BurnedInAnnotation=NO for US modality."""
        # Covers lines 235-236
        ds = Dataset()
        ds.Modality = "US"
        
        result = manager._apply_us_kill_switch(ds)
        
        assert result.BurnedInAnnotation == "NO"
        log = "\n".join(manager.get_processing_log())
        assert "US Kill-Switch" in log
    
    def test_us_kill_switch_noop_for_non_us(self, manager):
        """Should NOT set BurnedInAnnotation for non-US modality."""
        ds = Dataset()
        ds.Modality = "CT"
        
        result = manager._apply_us_kill_switch(ds)
        
        assert not hasattr(result, 'BurnedInAnnotation')


# ============================================================================
# E) _regenerate_uids() BRANCH MATRIX
# ============================================================================

class TestRegenerateUids:
    """Tests for _regenerate_uids() method."""
    
    def test_regenerate_uids_initializes_uid_manager(self, manager, ds_with_complete_file_meta):
        """Should initialize UID manager seeded by PatientID."""
        # Covers line 250-252
        ds = ds_with_complete_file_meta
        assert manager._uid_manager is None
        
        manager._regenerate_uids(ds)
        
        assert manager._uid_manager is not None
    
    def test_regenerate_uids_updates_study_and_series_uids(self, manager, ds_with_complete_file_meta):
        """Should regenerate Study and Series UIDs."""
        ds = ds_with_complete_file_meta
        old_study = ds.StudyInstanceUID
        old_series = ds.SeriesInstanceUID
        
        manager._regenerate_uids(ds)
        
        assert ds.StudyInstanceUID != old_study
        assert ds.SeriesInstanceUID != old_series
        log = "\n".join(manager.get_processing_log())
        assert "StudyInstanceUID regenerated" in log
        assert "SeriesInstanceUID regenerated" in log
    
    def test_regenerate_uids_updates_sop_and_file_meta(self, manager, ds_with_complete_file_meta):
        """Should update SOPInstanceUID and sync to file_meta."""
        ds = ds_with_complete_file_meta
        old_sop = ds.SOPInstanceUID
        
        manager._regenerate_uids(ds)
        
        assert ds.SOPInstanceUID != old_sop
        assert ds.file_meta.MediaStorageSOPInstanceUID == ds.SOPInstanceUID
        log = "\n".join(manager.get_processing_log())
        assert "SOPInstanceUID regenerated" in log
    
    def test_regenerate_uids_skips_missing_uid_fields(self, manager):
        """Should not crash when UID fields are missing."""
        ds = Dataset()
        ds.PatientID = "P123"
        # No UIDs present
        
        # Should not raise
        manager._regenerate_uids(ds)


# ============================================================================
# F) _apply_internal_repair() BRANCH MATRIX
# ============================================================================

class TestApplyInternalRepair:
    """Tests for _apply_internal_repair() method."""
    
    def test_internal_repair_fixes_headers_and_applies_kill_switch(self, manager, ds_base):
        """Should fix headers and apply US kill switch."""
        # Covers lines 286-294
        ds = ds_base
        ds.Modality = "US"
        
        result = manager._apply_internal_repair(ds)
        
        # Headers fixed
        assert hasattr(result, 'file_meta')
        assert hasattr(result.file_meta, 'TransferSyntaxUID')
        
        # US kill switch applied
        assert result.BurnedInAnnotation == "NO"
        
        # Log recorded
        log = "\n".join(manager.get_processing_log())
        assert "Profile: Internal Repair" in log


# ============================================================================
# G) _apply_us_research_safe_harbor() BRANCH MATRIX
# ============================================================================

class TestApplyUsResearchSafeHarbor:
    """Tests for _apply_us_research_safe_harbor() method."""
    
    def test_us_research_sets_deid_tags(self, manager, ds_base):
        """Should set PatientIdentityRemoved and DeidentificationMethod."""
        result = manager._apply_us_research_safe_harbor(ds_base)
        
        assert result.PatientIdentityRemoved == "YES"
        assert "HIPAA_SAFE_HARBOR" in result.DeidentificationMethod
        assert "DATE_SHIFT" in result.DeidentificationMethod
        assert "UID_REGEN" in result.DeidentificationMethod
        assert hasattr(result, 'DeidentificationMethodCodeSequence')
    
    def test_us_research_shifts_date_fields(self, manager, ds_base):
        """Should shift date fields by calculated offset."""
        ds = ds_base
        original_study_date = ds.StudyDate
        
        result = manager._apply_us_research_safe_harbor(ds)
        
        # Date should be shifted (not same as original)
        assert result.StudyDate != original_study_date
        log = "\n".join(manager.get_processing_log())
        assert "Shifted: StudyDate" in log
    
    def test_us_research_birthdate_keeps_year_only(self, manager, ds_base):
        """Should keep only year of PatientBirthDate."""
        # Covers lines 364-369
        ds = ds_base
        ds.PatientBirthDate = "19801231"
        
        result = manager._apply_us_research_safe_harbor(ds)
        
        assert result.PatientBirthDate == "19800101"
        log = "\n".join(manager.get_processing_log())
        assert "Modified: PatientBirthDate" in log
    
    def test_us_research_deletes_patient_name(self, manager, ds_base):
        """Should delete PatientName (HIPAA identifier)."""
        ds = ds_base
        assert hasattr(ds, 'PatientName')
        
        result = manager._apply_us_research_safe_harbor(ds)
        
        assert not hasattr(result, 'PatientName')


# ============================================================================
# H) _apply_au_strict_oaic() BRANCH MATRIX
# ============================================================================

class TestApplyAuStrictOaic:
    """Tests for _apply_au_strict_oaic() method."""
    
    def test_au_strict_hashes_patient_id(self, manager, ds_base):
        """Should hash PatientID and log it."""
        # Covers lines 420-422
        ds = ds_base
        original_id = ds.PatientID
        
        result = manager._apply_au_strict_oaic(ds)
        
        assert result.PatientID != original_id
        assert result.PatientID.startswith("ANON_")
        log = "\n".join(manager.get_processing_log())
        assert "Hashed: PatientID" in log
    
    def test_au_strict_sets_deid_tags(self, manager, ds_base):
        """Should set compliance tags including OAIC_APP11."""
        result = manager._apply_au_strict_oaic(ds_base)
        
        assert result.PatientIdentityRemoved == "YES"
        assert "OAIC_APP11" in result.DeidentificationMethod
        assert hasattr(result, 'DeidentificationMethodCodeSequence')
    
    def test_au_strict_shifts_dates(self, manager, ds_base):
        """Should shift date fields."""
        ds = ds_base
        original_study_date = ds.StudyDate
        
        result = manager._apply_au_strict_oaic(ds)
        
        assert result.StudyDate != original_study_date
        log = "\n".join(manager.get_processing_log())
        assert "Shifted: StudyDate" in log
    
    def test_au_strict_birthdate_keeps_year_only(self, manager, ds_base):
        """Should keep only year of PatientBirthDate."""
        ds = ds_base
        ds.PatientBirthDate = "19801231"
        
        result = manager._apply_au_strict_oaic(ds)
        
        assert result.PatientBirthDate == "19800101"
    
    def test_au_strict_deletes_patient_name(self, manager, ds_base):
        """Should delete PatientName."""
        ds = ds_base
        assert hasattr(ds, 'PatientName')
        
        result = manager._apply_au_strict_oaic(ds)
        
        assert not hasattr(result, 'PatientName')


# ============================================================================
# I) process_dataset() BRANCH MATRIX
# ============================================================================

class TestProcessDataset:
    """Tests for process_dataset() method."""
    
    def test_process_dataset_unknown_profile_falls_back(self, manager, ds_base):
        """Unknown profile should fall back to internal_repair."""
        # Covers line 494
        result_ds, info = manager.process_dataset(ds_base, "weird_unknown_profile")
        
        log = "\n".join(info['log'])
        assert "Unknown profile" in log
        assert "internal_repair" in log.lower()
    
    def test_process_dataset_fix_uids_calls_regenerate(self, manager, ds_with_complete_file_meta):
        """fix_uids=True should call _regenerate_uids."""
        # Covers lines 497-501
        ds = ds_with_complete_file_meta
        old_study = ds.StudyInstanceUID
        
        result_ds, info = manager.process_dataset(
            ds, 
            DicomComplianceManager.PROFILE_INTERNAL_REPAIR,
            fix_uids=True
        )
        
        assert result_ds.StudyInstanceUID != old_study
        assert info['fix_uids'] is True
    
    def test_process_dataset_returns_processing_info(self, manager, ds_base):
        """Should return complete processing_info dict."""
        # Covers line 505
        result_ds, info = manager.process_dataset(
            ds_base,
            DicomComplianceManager.PROFILE_US_RESEARCH
        )
        
        assert 'profile' in info
        assert 'fix_uids' in info
        assert 'date_shift_days' in info
        assert 'uid_mapping' in info
        assert 'log' in info
        
        # US Research creates uid_manager
        assert info['uid_mapping'] is not None
    
    def test_process_dataset_internal_repair_no_uid_mapping(self, manager, ds_base):
        """Internal repair without fix_uids should have None uid_mapping."""
        result_ds, info = manager.process_dataset(
            ds_base,
            DicomComplianceManager.PROFILE_INTERNAL_REPAIR,
            fix_uids=False
        )
        
        assert info['uid_mapping'] is None


# ============================================================================
# J) apply_compliance() WRAPPER
# ============================================================================

class TestApplyCompliance:
    """Tests for apply_compliance() convenience function."""
    
    def test_apply_compliance_returns_tuple(self, ds_base):
        """Should return (dataset, info) tuple."""
        # Covers lines 538-539
        result = apply_compliance(ds_base, 'internal_repair')
        
        assert isinstance(result, tuple)
        assert len(result) == 2
        
        result_ds, info = result
        assert isinstance(result_ds, Dataset)
        assert isinstance(info, dict)
    
    def test_apply_compliance_delegates_to_manager(self, ds_base):
        """Should use DicomComplianceManager internally."""
        result_ds, info = apply_compliance(
            ds_base,
            profile='us_research_safe_harbor',
            fix_uids=False
        )
        
        assert info['profile'] == 'us_research_safe_harbor'
        assert result_ds.PatientIdentityRemoved == "YES"


# ============================================================================
# UIDMANAGER TESTS
# ============================================================================

class TestUIDManager:
    """Tests for UIDManager class."""
    
    def test_uid_manager_initialization(self):
        """Should initialize with empty mappings."""
        mgr = UIDManager(seed="P123")
        
        assert mgr._study_uid_map == {}
        assert mgr._series_uid_map == {}
        assert mgr._instance_uid_map == {}
        assert mgr._seed == "P123"
    
    def test_get_new_study_uid_consistent_mapping(self):
        """Same input UID should return same output UID."""
        mgr = UIDManager()
        
        uid1 = mgr.get_new_study_uid("1.2.3.4")
        uid2 = mgr.get_new_study_uid("1.2.3.4")
        uid3 = mgr.get_new_study_uid("1.2.3.5")
        
        assert uid1 == uid2  # Same input = same output
        assert uid1 != uid3  # Different input = different output
        assert uid1 != "1.2.3.4"  # Output differs from input
    
    def test_get_new_series_uid_consistent_mapping(self):
        """Same input UID should return same output UID."""
        mgr = UIDManager()
        
        uid1 = mgr.get_new_series_uid("1.2.3.4")
        uid2 = mgr.get_new_series_uid("1.2.3.4")
        
        assert uid1 == uid2
    
    def test_get_new_instance_uid_consistent_mapping(self):
        """Same input UID should return same output UID."""
        mgr = UIDManager()
        
        uid1 = mgr.get_new_instance_uid("1.2.3.4")
        uid2 = mgr.get_new_instance_uid("1.2.3.4")
        
        assert uid1 == uid2
    
    def test_get_mapping_summary(self):
        """Should return correct counts."""
        mgr = UIDManager()
        
        mgr.get_new_study_uid("1.1")
        mgr.get_new_study_uid("1.2")
        mgr.get_new_series_uid("2.1")
        mgr.get_new_instance_uid("3.1")
        mgr.get_new_instance_uid("3.2")
        mgr.get_new_instance_uid("3.3")
        
        summary = mgr.get_mapping_summary()
        
        assert summary['studies_remapped'] == 2
        assert summary['series_remapped'] == 1
        assert summary['instances_remapped'] == 3
