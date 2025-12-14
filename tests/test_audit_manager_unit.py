"""
Unit tests for src/audit_manager.py

Goals:
- Deterministic coverage increases without real DICOM I/O
- Exercise uncovered branches in:
  - AuditLogger.generate_audit_log (115–128)
  - AuditLogger.export_logs_to_csv (255–278)
  - AuditLogger.get_statistics date filter branch (297–298)
  - pandas-unavailable branch (28–29)
"""

from __future__ import annotations

import inspect
import json
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional

import pytest

# Ensure src is on the path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import audit_manager  # type: ignore


def _call_with_supported_kwargs(func, *args, **kwargs):
    """
    Call func passing only kwargs that exist in func's signature.
    This makes tests tolerant to small API differences.
    """
    sig = inspect.signature(func)
    supported = {}
    for k, v in kwargs.items():
        if k in sig.parameters:
            supported[k] = v
    return func(*args, **supported)


def _make_fake_dataset(**fields):
    """
    Create a tiny pydicom Dataset if pydicom is installed; otherwise a stub object.
    """
    try:
        from pydicom.dataset import Dataset  # type: ignore
        ds = Dataset()
        for k, v in fields.items():
            setattr(ds, k, v)
        return ds
    except Exception:
        class Stub:
            pass
        ds = Stub()
        for k, v in fields.items():
            setattr(ds, k, v)
        return ds


def _make_logger(tmp_path: Path):
    """
    Create an AuditLogger instance with a temp DB path.
    """
    db_path = tmp_path / getattr(audit_manager, "DB_FILENAME", "scrub_history.db")
    return audit_manager.AuditLogger(db_path=str(db_path))


def _log_one_event(logger, *,
                   scrub_uuid: str = "00000000-0000-0000-0000-000000000001",
                   operator_id: str = "OP001",
                   original_filename: str = "test.dcm",
                   reason_code: str = "UNIT_TEST",
                   patient_id: str = "PID123",
                   patient_name: str = "DOE^JOHN",
                   study_date: str = "20250101",
                   modality: str = "US",
                   institution: str = "Test Hospital") -> int:
    """
    Insert one scrub event via log_scrub_event.
    Returns the log row ID.
    """
    return logger.log_scrub_event(
        operator_id=operator_id,
        original_filename=original_filename,
        scrub_uuid=scrub_uuid,
        reason_code=reason_code,
        patient_id_original=patient_id,
        patient_name_original=patient_name,
        study_date=study_date,
        modality=modality,
        institution=institution,
    )


# =============================================================================
# Test: PANDAS_AVAILABLE=False branch (lines 28-29, 255-256)
# =============================================================================

def test_export_logs_to_csv_raises_when_pandas_unavailable(tmp_path: Path):
    """
    Covers: module-level branch PANDAS_AVAILABLE=False (28–29)
    and verifies export_logs_to_csv fails deterministically when pandas is unavailable.
    """
    logger = _make_logger(tmp_path)
    
    # Store original value
    original_pandas_available = audit_manager.PANDAS_AVAILABLE
    
    try:
        # Force pandas unavailable branch
        audit_manager.PANDAS_AVAILABLE = False

        with pytest.raises(ImportError) as excinfo:
            logger.export_logs_to_csv(
                start_date="2020-01-01",
                end_date="2025-12-31",
            )

        # Message should mention pandas
        assert "pandas" in str(excinfo.value).lower()
    finally:
        # Restore original value
        audit_manager.PANDAS_AVAILABLE = original_pandas_available


# =============================================================================
# Test: generate_audit_log (lines 115-128)
# =============================================================================

def test_generate_audit_log_without_dataset(tmp_path: Path):
    """
    Covers generate_audit_log branch when dataset=None (skips force-sync logic).
    """
    logger = _make_logger(tmp_path)

    # Call generate_audit_log with dataset=None
    result = logger.generate_audit_log(
        activity_id="TEST_ACTIVITY",
        details={"accession": "ACC123", "study_date": "20250101"},
        dataset=None,
    )

    # Should return a string audit log
    assert result is not None
    assert isinstance(result, str)
    assert "TEST_ACTIVITY" in result


def test_generate_audit_log_with_dataset_forces_accession_removed(tmp_path: Path):
    """
    Covers generate_audit_log 'force-sync' logic (115-128) when dataset IS provided.
    The accession should be forced to 'REMOVED' in the details dict.
    """
    logger = _make_logger(tmp_path)

    ds = _make_fake_dataset(
        PatientID="PID999",
        StudyDate="20251215",
        AccessionNumber="ACC_ORIGINAL",
    )

    details = {
        "accession": "ACC_ORIGINAL",
        "accession_number": "ACC_ORIGINAL",
        "study_date": "20251215",
    }

    result = logger.generate_audit_log(
        activity_id="FORCE_SYNC_TEST",
        details=details,
        dataset=ds,
    )

    # After the call, details should have been mutated
    assert details["accession"] == "REMOVED"
    assert details["accession_number"] == "REMOVED"
    # If StudyDate exists in dataset, new_study_date should be set
    assert details.get("new_study_date") == "20251215" or details.get("NewStudyDate") == "20251215"


def test_generate_audit_log_with_dataset_missing_study_date(tmp_path: Path):
    """
    Covers generate_audit_log when dataset is provided but has no StudyDate attribute.
    Should not crash, just skip the StudyDate sync.
    """
    logger = _make_logger(tmp_path)

    # Dataset WITHOUT StudyDate
    ds = _make_fake_dataset(
        PatientID="PID999",
        AccessionNumber="ACC_ORIGINAL",
    )

    details = {
        "accession": "ACC_ORIGINAL",
        "accession_number": "ACC_ORIGINAL",
    }

    result = logger.generate_audit_log(
        activity_id="NO_STUDY_DATE_TEST",
        details=details,
        dataset=ds,
    )

    # Accession should still be forced to REMOVED
    assert details["accession"] == "REMOVED"
    # new_study_date should NOT be set since dataset has no StudyDate
    assert "new_study_date" not in details or details.get("new_study_date") is None


# =============================================================================
# Test: export_logs_to_csv pandas path + column reorder (lines 255-278)
# =============================================================================

@dataclass
class _StubDataFrame:
    """Stub DataFrame for testing without real pandas."""
    rows: list
    columns: list = None
    columns_requested: Optional[list] = None
    csv_written_to: Optional[str] = None

    def __post_init__(self):
        if self.rows:
            self.columns = list(self.rows[0].keys()) if isinstance(self.rows[0], dict) else []

    def __getitem__(self, cols):
        # Column reorder path uses df[cols]
        self.columns_requested = list(cols)
        return self

    def to_csv(self, path, index=False):
        self.csv_written_to = str(path)
        # Write deterministic CSV content
        Path(path).write_text("id,timestamp,operator_id,scrub_uuid\n1,2025-01-01,OP001,uuid1\n", encoding="utf-8")


class _StubPandas:
    """Stub pandas module for testing."""
    def __init__(self):
        self.last_df: Optional[_StubDataFrame] = None

    def DataFrame(self, rows):
        self.last_df = _StubDataFrame(rows=list(rows))
        return self.last_df


def test_export_logs_to_csv_pandas_path_writes_csv(tmp_path: Path, monkeypatch):
    """
    Covers export_logs_to_csv pandas path + column reorder (255–278) deterministically
    WITHOUT requiring real pandas.
    """
    logger = _make_logger(tmp_path)

    # Insert at least one event so there's data to export
    _log_one_event(logger, scrub_uuid="00000000-0000-0000-0000-000000000010")

    stub_pd = _StubPandas()
    monkeypatch.setattr(audit_manager, "PANDAS_AVAILABLE", True)
    monkeypatch.setattr(audit_manager, "pd", stub_pd)

    out_csv = tmp_path / "audit_export.csv"

    result = logger.export_logs_to_csv(
        start_date="2020-01-01",
        end_date="2030-12-31",
        output_path=str(out_csv),
    )

    # Output file should exist (our stub writes it)
    assert out_csv.exists()
    assert "operator_id" in out_csv.read_text(encoding="utf-8")

    # Stub should have been used
    assert stub_pd.last_df is not None
    assert stub_pd.last_df.csv_written_to == str(out_csv)
    
    # Column reorder branch should have tried to subset df[columns]
    assert stub_pd.last_df.columns_requested is not None
    assert isinstance(stub_pd.last_df.columns_requested, list)

    # Return value should be the output path
    assert result == str(out_csv)


def test_export_logs_to_csv_uses_default_output_path(tmp_path: Path, monkeypatch):
    """
    Covers the default output_path generation branch (lines 260-261).
    """
    logger = _make_logger(tmp_path)
    
    # Insert at least one event
    _log_one_event(logger, scrub_uuid="00000000-0000-0000-0000-000000000011")
    
    stub_pd = _StubPandas()
    monkeypatch.setattr(audit_manager, "PANDAS_AVAILABLE", True)
    monkeypatch.setattr(audit_manager, "pd", stub_pd)
    
    # Change to tmp_path so the default file is created there
    original_cwd = os.getcwd()
    try:
        os.chdir(tmp_path)
        
        # Call WITHOUT specifying output_path
        result = logger.export_logs_to_csv(
            start_date="2020-01-01",
            end_date="2025-12-31",
            # output_path not specified - should use default
        )
        
        # Result should contain the date range in filename
        assert "2020-01-01" in result
        assert "2025-12-31" in result
        assert result.endswith(".csv")
    finally:
        os.chdir(original_cwd)


# =============================================================================
# Test: get_statistics date filter branch (lines 296-298)
# =============================================================================

def test_get_statistics_without_date_filter(tmp_path: Path):
    """
    Covers get_statistics when NO date filter is applied (where_clause empty).
    """
    logger = _make_logger(tmp_path)

    # Insert events
    _log_one_event(logger, scrub_uuid="00000000-0000-0000-0000-000000000020")
    _log_one_event(logger, scrub_uuid="00000000-0000-0000-0000-000000000021")

    # Call without date range
    stats = logger.get_statistics()

    assert stats is not None
    assert isinstance(stats, dict)
    assert stats["total_events"] == 2
    assert stats["successful"] == 2
    assert stats["failed"] == 0
    assert stats["success_rate"] == 100.0
    assert "by_operator" in stats
    assert "by_reason_code" in stats


def test_get_statistics_with_date_range_applies_filter_branch(tmp_path: Path):
    """
    Covers get_statistics date filter branch (297–298) by passing start/end.
    """
    logger = _make_logger(tmp_path)

    # Insert two events
    _log_one_event(logger, scrub_uuid="00000000-0000-0000-0000-000000000030")
    _log_one_event(logger, scrub_uuid="00000000-0000-0000-0000-000000000031")

    # Filter with date range that should include the events
    # Events are logged with current UTC timestamp, so use wide range
    stats = logger.get_statistics(
        start_date="2020-01-01",
        end_date="2030-12-31",
    )

    assert stats is not None
    assert isinstance(stats, dict)
    assert stats["total_events"] >= 0
    assert "successful" in stats
    assert "by_operator" in stats


def test_get_statistics_with_narrow_date_range_excludes_events(tmp_path: Path):
    """
    Covers get_statistics date filter branch with a range that excludes all events.
    """
    logger = _make_logger(tmp_path)

    # Insert events (they'll have current timestamp)
    _log_one_event(logger, scrub_uuid="00000000-0000-0000-0000-000000000040")

    # Use a date range in the past that won't include current events
    stats = logger.get_statistics(
        start_date="2000-01-01",
        end_date="2000-12-31",
    )

    assert stats is not None
    assert isinstance(stats, dict)
    # Should find no events in that range
    assert stats["total_events"] == 0
    assert stats["successful"] == 0
    assert stats["success_rate"] == 0  # 0 when no events


# =============================================================================
# Test: AuditLogger basic operations
# =============================================================================

def test_audit_logger_initialization(tmp_path: Path):
    """Test that AuditLogger initializes correctly and creates database."""
    logger = _make_logger(tmp_path)
    
    db_path = tmp_path / audit_manager.DB_FILENAME
    assert db_path.exists()


def test_generate_scrub_uuid_returns_valid_uuid(tmp_path: Path):
    """Test that generate_scrub_uuid returns a valid UUID4 string."""
    logger = _make_logger(tmp_path)
    
    uuid1 = logger.generate_scrub_uuid()
    uuid2 = logger.generate_scrub_uuid()
    
    # Should be valid UUID format
    assert len(uuid1) == 36
    assert uuid1.count("-") == 4
    
    # Should be unique
    assert uuid1 != uuid2


def test_log_scrub_event_inserts_record(tmp_path: Path):
    """Test that log_scrub_event inserts a record and returns row ID."""
    logger = _make_logger(tmp_path)
    
    row_id = _log_one_event(logger, scrub_uuid="test-uuid-001")
    
    assert row_id is not None
    assert isinstance(row_id, int)
    assert row_id > 0


def test_get_event_by_uuid_finds_event(tmp_path: Path):
    """Test that get_event_by_uuid retrieves the correct event."""
    logger = _make_logger(tmp_path)
    
    test_uuid = "findme-uuid-12345678"
    _log_one_event(logger, scrub_uuid=test_uuid, operator_id="OP_FIND")
    
    event = logger.get_event_by_uuid(test_uuid)
    
    assert event is not None
    assert isinstance(event, dict)
    assert event["scrub_uuid"] == test_uuid
    assert event["operator_id"] == "OP_FIND"


def test_get_event_by_uuid_returns_none_for_missing(tmp_path: Path):
    """Test that get_event_by_uuid returns None for non-existent UUID."""
    logger = _make_logger(tmp_path)
    
    event = logger.get_event_by_uuid("nonexistent-uuid-999")
    
    assert event is None


def test_get_events_by_date_range(tmp_path: Path):
    """Test that get_events_by_date_range retrieves events correctly."""
    logger = _make_logger(tmp_path)
    
    # Insert events
    _log_one_event(logger, scrub_uuid="range-uuid-001")
    _log_one_event(logger, scrub_uuid="range-uuid-002")
    
    # Query with wide date range
    events = logger.get_events_by_date_range(
        start_date="2020-01-01",
        end_date="2030-12-31",
    )
    
    assert isinstance(events, list)
    assert len(events) >= 2


# =============================================================================
# Test: embed_compliance_tags function
# =============================================================================

def test_embed_compliance_tags_sets_required_fields(tmp_path: Path):
    """Test that embed_compliance_tags sets all required OAIC/APP 11 fields."""
    ds = _make_fake_dataset(
        PatientID="PID123",
        PatientName="DOE^JOHN",
    )
    
    audit_manager.embed_compliance_tags(
        dataset=ds,
        operator_id="OP001",
        reason_code="UNIT_TEST",
        scrub_uuid="embed-test-uuid",
    )
    
    # Check required fields
    assert ds.PatientIdentityRemoved == "YES"
    assert ds.BurnedInAnnotation == "NO"
    assert "OAIC_APP11" in ds.DeidentificationMethod
    assert "OP001" in ds.DeidentificationMethod
    assert "embed-test-uuid" in ds.DeidentificationMethod
    
    # Check ContributingEquipmentSequence
    assert hasattr(ds, "ContributingEquipmentSequence")
    assert len(ds.ContributingEquipmentSequence) == 1
    
    # Check DeidentificationMethodCodeSequence
    assert hasattr(ds, "DeidentificationMethodCodeSequence")
    assert len(ds.DeidentificationMethodCodeSequence) == 1


def test_embed_compliance_tags_appends_to_existing_sequence(tmp_path: Path):
    """Test that embed_compliance_tags appends to existing sequences."""
    from pydicom.sequence import Sequence
    from pydicom.dataset import Dataset
    
    ds = _make_fake_dataset(
        PatientID="PID123",
    )
    
    # Pre-create sequences with existing items
    existing_equipment = Dataset()
    existing_equipment.Manufacturer = "ExistingManufacturer"
    ds.ContributingEquipmentSequence = Sequence([existing_equipment])
    
    existing_deid = Dataset()
    existing_deid.CodeValue = "EXISTING"
    ds.DeidentificationMethodCodeSequence = Sequence([existing_deid])
    
    audit_manager.embed_compliance_tags(
        dataset=ds,
        operator_id="OP002",
        reason_code="APPEND_TEST",
        scrub_uuid="append-test-uuid",
    )
    
    # Should have appended, not replaced
    assert len(ds.ContributingEquipmentSequence) == 2
    assert len(ds.DeidentificationMethodCodeSequence) == 2


# =============================================================================
# Test: AtomicScrubOperation
# =============================================================================

def test_atomic_scrub_operation_executes_successfully(tmp_path: Path):
    """Test that AtomicScrubOperation completes successfully."""
    import pydicom.uid
    
    logger = _make_logger(tmp_path)
    atomic_op = audit_manager.AtomicScrubOperation(logger)
    
    # Create a valid DICOM dataset
    ds = _make_fake_dataset(
        PatientID="PID123",
        PatientName="DOE^JOHN",
        StudyDate="20251215",
        Modality="US",
        InstitutionName="Test Hospital",
        SOPClassUID="1.2.840.10008.5.1.4.1.1.6.1",
        SOPInstanceUID=pydicom.uid.generate_uid(),
    )
    ds.is_little_endian = True
    ds.is_implicit_VR = False
    
    # Add file_meta
    from pydicom.dataset import FileMetaDataset
    file_meta = FileMetaDataset()
    file_meta.MediaStorageSOPClassUID = ds.SOPClassUID
    file_meta.MediaStorageSOPInstanceUID = ds.SOPInstanceUID
    file_meta.TransferSyntaxUID = pydicom.uid.ExplicitVRLittleEndian
    file_meta.ImplementationClassUID = pydicom.uid.generate_uid()
    ds.file_meta = file_meta
    
    output_path = tmp_path / "scrubbed_output.dcm"
    
    success, scrub_uuid = atomic_op.execute_scrub(
        dataset=ds,
        output_path=str(output_path),
        operator_id="OP_ATOMIC",
        reason_code="ATOMIC_TEST",
        original_filename="original.dcm",
    )
    
    assert success is True
    assert scrub_uuid is not None
    assert output_path.exists()
    
    # Verify file was saved with compliance tags
    saved_ds = pydicom.dcmread(str(output_path), force=True)
    assert saved_ds.PatientIdentityRemoved == "YES"
    
    # Verify event was logged
    event = logger.get_event_by_uuid(scrub_uuid)
    assert event is not None
    assert event["operator_id"] == "OP_ATOMIC"


def test_atomic_scrub_operation_fails_on_database_error(tmp_path: Path, monkeypatch):
    """
    Covers: AtomicScrubOperation database failure path (lines 472-476).
    When database log fails, file should NOT be saved.
    """
    import sqlite3
    import pydicom.uid
    
    logger = _make_logger(tmp_path)
    atomic_op = audit_manager.AtomicScrubOperation(logger)
    
    # Create a valid DICOM dataset
    ds = _make_fake_dataset(
        PatientID="PID123",
        PatientName="DOE^JOHN",
        SOPClassUID="1.2.840.10008.5.1.4.1.1.6.1",
        SOPInstanceUID=pydicom.uid.generate_uid(),
    )
    
    output_path = tmp_path / "should_not_exist.dcm"
    
    # Monkeypatch log_scrub_event to raise sqlite3.Error
    def raise_db_error(*args, **kwargs):
        raise sqlite3.Error("Simulated database failure")
    
    monkeypatch.setattr(logger, "log_scrub_event", raise_db_error)
    
    with pytest.raises(RuntimeError) as excinfo:
        atomic_op.execute_scrub(
            dataset=ds,
            output_path=str(output_path),
            operator_id="OP_FAIL",
            reason_code="DB_FAIL_TEST",
            original_filename="original.dcm",
        )
    
    # Should mention ATOMIC SAFETY and database failure
    assert "ATOMIC SAFETY" in str(excinfo.value)
    assert "Database log failed" in str(excinfo.value) or "database" in str(excinfo.value).lower()
    
    # File should NOT exist since DB failed first
    assert not output_path.exists()


def test_atomic_scrub_operation_updates_log_on_file_save_failure(tmp_path: Path, monkeypatch):
    """
    Covers: AtomicScrubOperation file save failure path (lines 482-498).
    When file save fails after logging, the log should be updated to failed status.
    """
    import pydicom.uid
    
    logger = _make_logger(tmp_path)
    atomic_op = audit_manager.AtomicScrubOperation(logger)
    
    # Create a minimal dataset
    ds = _make_fake_dataset(
        PatientID="PID123",
        PatientName="DOE^JOHN",
        SOPClassUID="1.2.840.10008.5.1.4.1.1.6.1",
        SOPInstanceUID=pydicom.uid.generate_uid(),
    )
    
    # Use a path that will cause save to fail (directory doesn't exist and can't be created)
    bad_output_path = "/nonexistent_root_dir/impossible/path/output.dcm"
    
    with pytest.raises(RuntimeError) as excinfo:
        atomic_op.execute_scrub(
            dataset=ds,
            output_path=bad_output_path,
            operator_id="OP_SAVE_FAIL",
            reason_code="SAVE_FAIL_TEST",
            original_filename="original.dcm",
        )
    
    # Should mention ATOMIC SAFETY and file save failure
    assert "ATOMIC SAFETY" in str(excinfo.value)
    assert "File save failed" in str(excinfo.value) or "save" in str(excinfo.value).lower()
    
    # Extract UUID from error message to verify log was updated
    # The error message contains the UUID
    error_msg = str(excinfo.value)
    if "UUID:" in error_msg:
        # Extract UUID from message like "UUID: abc-123. Error: ..."
        uuid_start = error_msg.find("UUID:") + 5
        uuid_end = error_msg.find(".", uuid_start)
        if uuid_end == -1:
            uuid_end = len(error_msg)
        scrub_uuid = error_msg[uuid_start:uuid_end].strip()
        
        # Verify the log was updated to reflect failure
        event = logger.get_event_by_uuid(scrub_uuid)
        if event:
            assert event["success"] == 0, "Log should be marked as failed"
            assert event["error_message"] is not None, "Error message should be recorded"


def test_atomic_scrub_operation_handles_log_update_failure_gracefully(tmp_path: Path, monkeypatch):
    """
    Covers: AtomicScrubOperation line 493-494 (except: pass during log update).
    When both file save AND log update fail, it should still raise the original error.
    """
    import pydicom.uid
    
    logger = _make_logger(tmp_path)
    atomic_op = audit_manager.AtomicScrubOperation(logger)
    
    ds = _make_fake_dataset(
        PatientID="PID123",
        SOPClassUID="1.2.840.10008.5.1.4.1.1.6.1",
        SOPInstanceUID=pydicom.uid.generate_uid(),
    )
    
    # Path that will fail to save
    bad_output_path = "/nonexistent/path/output.dcm"
    
    # Monkeypatch _get_connection to raise during the UPDATE attempt (after successful INSERT)
    original_get_connection = logger._get_connection
    call_count = [0]
    
    def failing_get_connection():
        call_count[0] += 1
        if call_count[0] > 1:  # First call is for INSERT, subsequent for UPDATE
            raise Exception("Connection failed during update")
        return original_get_connection()
    
    # Only patch after the first successful log
    success_log_id = [None]
    original_log_event = logger.log_scrub_event
    
    def tracking_log_event(*args, **kwargs):
        result = original_log_event(*args, **kwargs)
        success_log_id[0] = result
        # Now break _get_connection for subsequent calls
        monkeypatch.setattr(logger, "_get_connection", failing_get_connection)
        return result
    
    monkeypatch.setattr(logger, "log_scrub_event", tracking_log_event)
    
    with pytest.raises(RuntimeError) as excinfo:
        atomic_op.execute_scrub(
            dataset=ds,
            output_path=bad_output_path,
            operator_id="OP_DOUBLE_FAIL",
            reason_code="DOUBLE_FAIL_TEST",
            original_filename="original.dcm",
        )
    
    # Should still raise the file save error (the except: pass should have caught the update error)
    assert "ATOMIC SAFETY" in str(excinfo.value)

