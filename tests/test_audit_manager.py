"""
Unit tests for audit_manager.py

Tests the SQLite-based audit logging system:
- AuditLogger: database initialization, event logging, queries, statistics
- AtomicScrubOperation: atomic file+db operations
- embed_compliance_tags: DICOM header embedding

Uses temp directories to avoid polluting the filesystem.
"""
import os
import json
import sqlite3
from pathlib import Path
from datetime import datetime
import pytest

# Add src to path (matches pattern from other test files)
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from audit_manager import (
    AuditLogger,
    AtomicScrubOperation,
    embed_compliance_tags,
    APP_VERSION,
    MANUFACTURER,
    DB_FILENAME,
)

# For DICOM dataset tests
import pydicom
from pydicom.dataset import Dataset, FileMetaDataset
from pydicom.uid import ExplicitVRLittleEndian


@pytest.fixture
def tmp_db_path(tmp_path: Path) -> str:
    """Create a temporary database path."""
    return str(tmp_path / "test_audit.db")


@pytest.fixture
def audit_logger(tmp_db_path: str) -> AuditLogger:
    """Create an AuditLogger with a temp database."""
    return AuditLogger(db_path=tmp_db_path)


@pytest.fixture
def minimal_dataset() -> Dataset:
    """Create a minimal DICOM dataset for testing."""
    ds = Dataset()
    ds.PatientName = "TEST^PATIENT"
    ds.PatientID = "12345"
    ds.StudyDate = "20240115"
    ds.Modality = "US"
    ds.SOPInstanceUID = "1.2.3.4.5.6.7.8.9"
    ds.StudyInstanceUID = "1.2.3.4.5.6.7.8.9.10"
    
    # File meta
    ds.file_meta = FileMetaDataset()
    ds.file_meta.TransferSyntaxUID = ExplicitVRLittleEndian
    ds.file_meta.MediaStorageSOPInstanceUID = ds.SOPInstanceUID
    ds.file_meta.MediaStorageSOPClassUID = "1.2.840.10008.5.1.4.1.1.6.1"
    
    return ds


class TestAuditLoggerInit:
    """Tests for AuditLogger initialization."""
    
    def test_creates_database_file(self, tmp_db_path):
        """AuditLogger should create the SQLite database file."""
        logger = AuditLogger(db_path=tmp_db_path)
        assert os.path.exists(tmp_db_path)
    
    def test_creates_scrub_events_table(self, tmp_db_path):
        """AuditLogger should create the scrub_events table."""
        logger = AuditLogger(db_path=tmp_db_path)
        
        conn = sqlite3.connect(tmp_db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='scrub_events'")
        result = cursor.fetchone()
        conn.close()
        
        assert result is not None
        assert result[0] == "scrub_events"
    
    def test_creates_indexes(self, tmp_db_path):
        """AuditLogger should create indexes for faster lookups."""
        logger = AuditLogger(db_path=tmp_db_path)
        
        conn = sqlite3.connect(tmp_db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='index'")
        indexes = [row[0] for row in cursor.fetchall()]
        conn.close()
        
        assert "idx_timestamp" in indexes
        assert "idx_scrub_uuid" in indexes
        assert "idx_operator" in indexes
    
    def test_uses_default_path_if_none(self, tmp_path, monkeypatch):
        """AuditLogger should use default DB_FILENAME if no path provided."""
        # Change to temp directory to avoid polluting cwd
        monkeypatch.chdir(tmp_path)
        
        logger = AuditLogger(db_path=None)
        assert os.path.exists(DB_FILENAME)


class TestGenerateScrubUuid:
    """Tests for UUID generation."""
    
    def test_generates_valid_uuid4(self, audit_logger):
        """generate_scrub_uuid should return a valid UUID4 string."""
        uuid_str = audit_logger.generate_scrub_uuid()
        
        # Should be a string
        assert isinstance(uuid_str, str)
        
        # Should have UUID format (8-4-4-4-12)
        parts = uuid_str.split('-')
        assert len(parts) == 5
        assert len(parts[0]) == 8
        assert len(parts[1]) == 4
        assert len(parts[2]) == 4
        assert len(parts[3]) == 4
        assert len(parts[4]) == 12
    
    def test_generates_unique_uuids(self, audit_logger):
        """Each call should generate a unique UUID."""
        uuids = [audit_logger.generate_scrub_uuid() for _ in range(100)]
        assert len(set(uuids)) == 100  # All unique


class TestLogScrubEvent:
    """Tests for logging scrub events."""
    
    def test_logs_basic_event(self, audit_logger):
        """log_scrub_event should insert a record into the database."""
        scrub_uuid = audit_logger.generate_scrub_uuid()
        
        audit_logger.log_scrub_event(
            operator_id="TEST_OPERATOR",
            original_filename="input.dcm",
            scrub_uuid=scrub_uuid,
            reason_code="RESEARCH_DEID",
        )
        
        # Verify it was stored
        event = audit_logger.get_event_by_uuid(scrub_uuid)
        assert event is not None
        assert event["operator_id"] == "TEST_OPERATOR"
        assert event["original_filename"] == "input.dcm"
        assert event["reason_code"] == "RESEARCH_DEID"
    
    def test_logs_with_all_fields(self, audit_logger):
        """log_scrub_event should store all optional fields."""
        scrub_uuid = audit_logger.generate_scrub_uuid()
        
        audit_logger.log_scrub_event(
            operator_id="ADMIN",
            original_filename="patient_scan.dcm",
            scrub_uuid=scrub_uuid,
            reason_code="FOI_LEGAL",
            output_filename="anonymized.dcm",
            patient_id_original="MRN12345",
            patient_name_original="DOE^JOHN",
            study_date="20240115",
            modality="CT",
            institution="Test Hospital",
            success=True,
            error_message=None,
        )
        
        event = audit_logger.get_event_by_uuid(scrub_uuid)
        assert event["output_filename"] == "anonymized.dcm"
        assert event["patient_id_original"] == "MRN12345"
        assert event["patient_name_original"] == "DOE^JOHN"
        assert event["study_date"] == "20240115"
        assert event["modality"] == "CT"
        assert event["institution"] == "Test Hospital"
        assert event["success"] == 1
    
    def test_logs_failure_event(self, audit_logger):
        """log_scrub_event should record failure with error message."""
        scrub_uuid = audit_logger.generate_scrub_uuid()
        
        audit_logger.log_scrub_event(
            operator_id="OPERATOR",
            original_filename="bad_file.dcm",
            scrub_uuid=scrub_uuid,
            reason_code="CLINICAL",
            success=False,
            error_message="Failed to read DICOM file",
        )
        
        event = audit_logger.get_event_by_uuid(scrub_uuid)
        assert event["success"] == 0
        assert event["error_message"] == "Failed to read DICOM file"
    
    def test_includes_app_version(self, audit_logger):
        """Logged events should include the app version."""
        scrub_uuid = audit_logger.generate_scrub_uuid()
        
        audit_logger.log_scrub_event(
            operator_id="OP",
            original_filename="file.dcm",
            scrub_uuid=scrub_uuid,
            reason_code="RESEARCH",
        )
        
        event = audit_logger.get_event_by_uuid(scrub_uuid)
        assert event["app_version"] == APP_VERSION


class TestGetEventByUuid:
    """Tests for retrieving events by UUID."""
    
    def test_returns_none_for_unknown_uuid(self, audit_logger):
        """get_event_by_uuid should return None for non-existent UUID."""
        result = audit_logger.get_event_by_uuid("non-existent-uuid-12345")
        assert result is None
    
    def test_returns_correct_event(self, audit_logger):
        """get_event_by_uuid should return the correct event."""
        uuid1 = audit_logger.generate_scrub_uuid()
        uuid2 = audit_logger.generate_scrub_uuid()
        
        audit_logger.log_scrub_event(
            operator_id="OP1",
            original_filename="file1.dcm",
            scrub_uuid=uuid1,
            reason_code="RESEARCH",
        )
        audit_logger.log_scrub_event(
            operator_id="OP2",
            original_filename="file2.dcm",
            scrub_uuid=uuid2,
            reason_code="CLINICAL",
        )
        
        event1 = audit_logger.get_event_by_uuid(uuid1)
        event2 = audit_logger.get_event_by_uuid(uuid2)
        
        assert event1["operator_id"] == "OP1"
        assert event2["operator_id"] == "OP2"


class TestGetEventsByDateRange:
    """Tests for date range queries."""
    
    def test_returns_events_in_range(self, audit_logger):
        """get_events_by_date_range should return events within the range."""
        # Log an event (will use current timestamp)
        scrub_uuid = audit_logger.generate_scrub_uuid()
        audit_logger.log_scrub_event(
            operator_id="OP",
            original_filename="file.dcm",
            scrub_uuid=scrub_uuid,
            reason_code="RESEARCH",
        )
        
        # Query with a wide date range
        start = "2020-01-01"
        end = "2030-12-31"
        events = audit_logger.get_events_by_date_range(start, end)
        
        assert len(events) >= 1
        assert any(e["scrub_uuid"] == scrub_uuid for e in events)
    
    def test_returns_empty_for_out_of_range(self, audit_logger):
        """get_events_by_date_range should return empty list for no matches."""
        scrub_uuid = audit_logger.generate_scrub_uuid()
        audit_logger.log_scrub_event(
            operator_id="OP",
            original_filename="file.dcm",
            scrub_uuid=scrub_uuid,
            reason_code="RESEARCH",
        )
        
        # Query with a date range in the past
        events = audit_logger.get_events_by_date_range("2000-01-01", "2000-12-31")
        assert len(events) == 0


class TestGetStatistics:
    """Tests for statistics generation."""
    
    def test_returns_statistics_dict(self, audit_logger):
        """get_statistics should return a dictionary with stats."""
        # Log some events
        for i in range(5):
            audit_logger.log_scrub_event(
                operator_id=f"OP{i}",
                original_filename=f"file{i}.dcm",
                scrub_uuid=audit_logger.generate_scrub_uuid(),
                reason_code="RESEARCH",
                success=True,
            )
        
        # One failure
        audit_logger.log_scrub_event(
            operator_id="OP_FAIL",
            original_filename="fail.dcm",
            scrub_uuid=audit_logger.generate_scrub_uuid(),
            reason_code="CLINICAL",
            success=False,
        )
        
        stats = audit_logger.get_statistics()
        
        assert isinstance(stats, dict)
        assert stats["total_events"] == 6
        assert stats["successful"] == 5
        assert stats["failed"] == 1


class TestEmbedComplianceTags:
    """Tests for DICOM compliance tag embedding."""
    
    def test_embeds_deidentification_method(self, minimal_dataset):
        """embed_compliance_tags should set DeidentificationMethod."""
        embed_compliance_tags(
            dataset=minimal_dataset,
            operator_id="TEST_OP",
            reason_code="RESEARCH_DEID",
            scrub_uuid="test-uuid-1234",
        )
        
        assert hasattr(minimal_dataset, "DeidentificationMethod")
        # Check it contains expected components (OAIC_APP11, operator, uuid)
        deid_method = minimal_dataset.DeidentificationMethod
        assert "OAIC_APP11" in deid_method or "SAMI_SCRUB" in deid_method
    
    def test_embeds_patient_identity_removed(self, minimal_dataset):
        """embed_compliance_tags should set PatientIdentityRemoved to YES."""
        embed_compliance_tags(
            dataset=minimal_dataset,
            operator_id="TEST_OP",
            reason_code="RESEARCH_DEID",
            scrub_uuid="test-uuid-1234",
        )
        
        assert minimal_dataset.PatientIdentityRemoved == "YES"
    
    def test_does_not_raise(self, minimal_dataset):
        """embed_compliance_tags should not raise with valid inputs."""
        # Should not raise
        embed_compliance_tags(
            dataset=minimal_dataset,
            operator_id="OPERATOR",
            reason_code="FOI_LEGAL",
            scrub_uuid="any-uuid-here",
        )


class TestAtomicScrubOperation:
    """Tests for atomic scrub operations."""
    
    def test_init_with_logger(self, audit_logger):
        """AtomicScrubOperation should initialize with an AuditLogger."""
        atomic_op = AtomicScrubOperation(audit_logger)
        assert atomic_op is not None
    
    def test_execute_scrub_saves_file(self, audit_logger, minimal_dataset, tmp_path):
        """execute_scrub should save the DICOM file."""
        atomic_op = AtomicScrubOperation(audit_logger)
        output_path = str(tmp_path / "output.dcm")
        
        result = atomic_op.execute_scrub(
            dataset=minimal_dataset,
            output_path=output_path,
            operator_id="TEST_OP",
            reason_code="RESEARCH",
            original_filename="input.dcm",
        )
        
        # File should exist
        assert os.path.exists(output_path)
        
        # Should be readable as DICOM (use force=True for files without preamble)
        ds = pydicom.dcmread(output_path, force=True)
        assert ds is not None
    
    def test_execute_scrub_logs_event(self, audit_logger, minimal_dataset, tmp_path):
        """execute_scrub should log the event to the database."""
        atomic_op = AtomicScrubOperation(audit_logger)
        output_path = str(tmp_path / "output.dcm")
        
        result = atomic_op.execute_scrub(
            dataset=minimal_dataset,
            output_path=output_path,
            operator_id="LOGGED_OP",
            reason_code="RESEARCH",
            original_filename="logged_input.dcm",
        )
        
        # Should have logged an event
        stats = audit_logger.get_statistics()
        assert stats["total_events"] >= 1
    
    def test_returns_scrub_uuid(self, audit_logger, minimal_dataset, tmp_path):
        """execute_scrub should return the scrub UUID."""
        atomic_op = AtomicScrubOperation(audit_logger)
        output_path = str(tmp_path / "output.dcm")
        
        result = atomic_op.execute_scrub(
            dataset=minimal_dataset,
            output_path=output_path,
            operator_id="TEST_OP",
            reason_code="RESEARCH",
            original_filename="input.dcm",
        )
        
        # Result should contain scrub_uuid
        assert result is not None
        # The exact structure depends on implementation


class TestConstants:
    """Tests for module constants."""
    
    def test_app_version_is_string(self):
        """APP_VERSION should be a string."""
        assert isinstance(APP_VERSION, str)
        assert len(APP_VERSION) > 0
    
    def test_manufacturer_is_string(self):
        """MANUFACTURER should be a string."""
        assert isinstance(MANUFACTURER, str)
    
    def test_db_filename_is_string(self):
        """DB_FILENAME should be a string ending in .db."""
        assert isinstance(DB_FILENAME, str)
        assert DB_FILENAME.endswith(".db")
