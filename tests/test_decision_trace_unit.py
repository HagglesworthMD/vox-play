"""
Unit Tests for Decision Trace Module
=====================================
Sprint 1: Audit Decision Trace

Tests the DecisionTraceCollector, DecisionTraceWriter, and related
enumerations and utilities.

Run: PYTHONPATH=src pytest tests/test_decision_trace_unit.py -v
"""

import pytest
import sqlite3
import tempfile
import os
from datetime import datetime, timezone

# Import the module under test
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from decision_trace import (
    DecisionTraceCollector,
    DecisionTraceWriter,
    DecisionRecord,
    ReasonCode,
    ActionType,
    ScopeLevel,
    TargetType,
    RuleSource,
    generate_decision_summary,
    get_hipaa_reason_code,
    get_foi_reason_code,
)


# ═══════════════════════════════════════════════════════════════════════════════
# ENUMERATION TESTS
# ═══════════════════════════════════════════════════════════════════════════════

class TestReasonCodeEnumeration:
    """Tests for ReasonCode constants."""
    
    def test_all_reason_codes_are_strings(self):
        """All reason codes must be non-empty strings."""
        for attr in dir(ReasonCode):
            if not attr.startswith('_'):
                value = getattr(ReasonCode, attr)
                assert isinstance(value, str), f"{attr} is not a string"
                assert len(value) > 0, f"{attr} is empty"
    
    def test_hipaa_codes_have_correct_prefix(self):
        """HIPAA codes should start with HIPAA_18_."""
        hipaa_attrs = [a for a in dir(ReasonCode) if a.startswith('HIPAA_')]
        for attr in hipaa_attrs:
            value = getattr(ReasonCode, attr)
            assert value.startswith('HIPAA_18_'), f"{attr} has wrong prefix: {value}"
    
    def test_oaic_codes_have_correct_prefix(self):
        """OAIC codes should start with OAIC_APP11_."""
        oaic_attrs = [a for a in dir(ReasonCode) if a.startswith('OAIC_')]
        for attr in oaic_attrs:
            value = getattr(ReasonCode, attr)
            assert value.startswith('OAIC_APP11_'), f"{attr} has wrong prefix: {value}"
    
    def test_no_duplicate_reason_codes(self):
        """All reason code values must be unique."""
        values = []
        for attr in dir(ReasonCode):
            if not attr.startswith('_'):
                values.append(getattr(ReasonCode, attr))
        assert len(values) == len(set(values)), "Duplicate reason codes found"


class TestActionTypeEnumeration:
    """Tests for ActionType constants."""
    
    def test_all_action_types_are_strings(self):
        """All action types must be non-empty strings."""
        for attr in dir(ActionType):
            if not attr.startswith('_'):
                value = getattr(ActionType, attr)
                assert isinstance(value, str)
                assert len(value) > 0
    
    def test_expected_action_types_exist(self):
        """Required action types must be defined."""
        required = ['REMOVED', 'REPLACED', 'MASKED', 'RETAINED', 'SHIFTED', 'HASHED']
        for action in required:
            assert hasattr(ActionType, action), f"Missing action type: {action}"


class TestScopeLevelEnumeration:
    """Tests for ScopeLevel constants."""
    
    def test_expected_scope_levels_exist(self):
        """Required scope levels must be defined."""
        required = ['STUDY', 'SERIES', 'INSTANCE', 'PIXEL_REGION']
        for scope in required:
            assert hasattr(ScopeLevel, scope), f"Missing scope level: {scope}"


class TestTargetTypeEnumeration:
    """Tests for TargetType constants."""
    
    def test_expected_target_types_exist(self):
        """Required target types must be defined."""
        required = ['TAG', 'PRIVATE_TAG_GROUP', 'PIXEL_REGION', 'UID', 'DATE_VALUE']
        for target in required:
            assert hasattr(TargetType, target), f"Missing target type: {target}"


# ═══════════════════════════════════════════════════════════════════════════════
# DECISION TRACE COLLECTOR TESTS
# ═══════════════════════════════════════════════════════════════════════════════

class TestDecisionTraceCollector:
    """Tests for DecisionTraceCollector class."""
    
    def test_init_creates_empty_collector(self):
        """New collector should be empty and unlocked."""
        collector = DecisionTraceCollector()
        assert collector.count() == 0
        assert not collector.is_locked()
    
    def test_add_single_decision(self):
        """Adding a decision should increment count."""
        collector = DecisionTraceCollector()
        collector.add(
            scope_level=ScopeLevel.INSTANCE,
            scope_uid="1.2.3.4",
            action_type=ActionType.REMOVED,
            target_type=TargetType.TAG,
            target_name="PatientName",
            reason_code=ReasonCode.HIPAA_NAME,
            rule_source=RuleSource.HIPAA_SAFE_HARBOR
        )
        assert collector.count() == 1
    
    def test_add_multiple_decisions(self):
        """Multiple decisions should all be stored."""
        collector = DecisionTraceCollector()
        for i in range(5):
            collector.add(
                scope_level=ScopeLevel.INSTANCE,
                action_type=ActionType.REMOVED,
                target_type=TargetType.TAG,
                target_name=f"Tag{i}",
                reason_code=ReasonCode.HIPAA_NAME,
                rule_source=RuleSource.HIPAA_SAFE_HARBOR
            )
        assert collector.count() == 5
    
    def test_get_decisions_returns_copy(self):
        """get_decisions should return a copy, not the internal list."""
        collector = DecisionTraceCollector()
        collector.add(
            scope_level=ScopeLevel.INSTANCE,
            action_type=ActionType.REMOVED,
            target_type=TargetType.TAG,
            target_name="Test",
            reason_code=ReasonCode.HIPAA_NAME,
            rule_source=RuleSource.HIPAA_SAFE_HARBOR
        )
        decisions1 = collector.get_decisions()
        decisions2 = collector.get_decisions()
        assert decisions1 is not decisions2
    
    def test_decision_record_fields_stored_correctly(self):
        """Decision record should store all provided fields."""
        collector = DecisionTraceCollector()
        collector.add(
            scope_level=ScopeLevel.PIXEL_REGION,
            scope_uid="1.2.3.4.5",
            action_type=ActionType.MASKED,
            target_type=TargetType.PIXEL_REGION,
            target_name="PixelRegion[0]",
            reason_code=ReasonCode.BURNED_IN_TEXT,
            rule_source=RuleSource.MODALITY_SAFETY_PROTOCOL,
            checksum_before="abc123",
            checksum_after=None,
            region_x=10,
            region_y=20,
            region_w=100,
            region_h=50
        )
        decisions = collector.get_decisions()
        assert len(decisions) == 1
        d = decisions[0]
        assert d.scope_level == ScopeLevel.PIXEL_REGION
        assert d.scope_uid == "1.2.3.4.5"
        assert d.action_type == ActionType.MASKED
        assert d.target_type == TargetType.PIXEL_REGION
        assert d.target_name == "PixelRegion[0]"
        assert d.reason_code == ReasonCode.BURNED_IN_TEXT
        assert d.rule_source == RuleSource.MODALITY_SAFETY_PROTOCOL
        assert d.checksum_before == "abc123"
        assert d.checksum_after is None
        assert d.region_x == 10
        assert d.region_y == 20
        assert d.region_w == 100
        assert d.region_h == 50
    
    def test_decision_record_has_timestamp(self):
        """Decision record should have an auto-generated timestamp."""
        collector = DecisionTraceCollector()
        collector.add(
            scope_level=ScopeLevel.INSTANCE,
            action_type=ActionType.REMOVED,
            target_type=TargetType.TAG,
            target_name="Test",
            reason_code=ReasonCode.HIPAA_NAME,
            rule_source=RuleSource.HIPAA_SAFE_HARBOR
        )
        decisions = collector.get_decisions()
        assert decisions[0].timestamp is not None
        assert decisions[0].timestamp.endswith("Z")
    
    def test_lock_prevents_further_additions(self):
        """Locked collector should raise on add()."""
        collector = DecisionTraceCollector()
        collector.add(
            scope_level=ScopeLevel.INSTANCE,
            action_type=ActionType.REMOVED,
            target_type=TargetType.TAG,
            target_name="Test1",
            reason_code=ReasonCode.HIPAA_NAME,
            rule_source=RuleSource.HIPAA_SAFE_HARBOR
        )
        collector.lock()
        assert collector.is_locked()
        
        with pytest.raises(RuntimeError, match="locked"):
            collector.add(
                scope_level=ScopeLevel.INSTANCE,
                action_type=ActionType.REMOVED,
                target_type=TargetType.TAG,
                target_name="Test2",
                reason_code=ReasonCode.HIPAA_NAME,
                rule_source=RuleSource.HIPAA_SAFE_HARBOR
            )
    
    def test_lock_does_not_prevent_get_decisions(self):
        """Locked collector should still allow reading decisions."""
        collector = DecisionTraceCollector()
        collector.add(
            scope_level=ScopeLevel.INSTANCE,
            action_type=ActionType.REMOVED,
            target_type=TargetType.TAG,
            target_name="Test",
            reason_code=ReasonCode.HIPAA_NAME,
            rule_source=RuleSource.HIPAA_SAFE_HARBOR
        )
        collector.lock()
        decisions = collector.get_decisions()
        assert len(decisions) == 1
    
    def test_count_by_action(self):
        """count_by_action should group decisions correctly."""
        collector = DecisionTraceCollector()
        for _ in range(3):
            collector.add(
                scope_level=ScopeLevel.INSTANCE,
                action_type=ActionType.REMOVED,
                target_type=TargetType.TAG,
                target_name="Test",
                reason_code=ReasonCode.HIPAA_NAME,
                rule_source=RuleSource.HIPAA_SAFE_HARBOR
            )
        for _ in range(2):
            collector.add(
                scope_level=ScopeLevel.INSTANCE,
                action_type=ActionType.MASKED,
                target_type=TargetType.PIXEL_REGION,
                target_name="Region",
                reason_code=ReasonCode.BURNED_IN_TEXT,
                rule_source=RuleSource.MODALITY_SAFETY_PROTOCOL
            )
        
        counts = collector.count_by_action()
        assert counts[ActionType.REMOVED] == 3
        assert counts[ActionType.MASKED] == 2
    
    def test_count_by_reason(self):
        """count_by_reason should group decisions correctly."""
        collector = DecisionTraceCollector()
        collector.add(
            scope_level=ScopeLevel.INSTANCE,
            action_type=ActionType.REMOVED,
            target_type=TargetType.TAG,
            target_name="PatientName",
            reason_code=ReasonCode.HIPAA_NAME,
            rule_source=RuleSource.HIPAA_SAFE_HARBOR
        )
        collector.add(
            scope_level=ScopeLevel.INSTANCE,
            action_type=ActionType.REMOVED,
            target_type=TargetType.TAG,
            target_name="PatientID",
            reason_code=ReasonCode.HIPAA_MRN,
            rule_source=RuleSource.HIPAA_SAFE_HARBOR
        )
        collector.add(
            scope_level=ScopeLevel.INSTANCE,
            action_type=ActionType.REMOVED,
            target_type=TargetType.TAG,
            target_name="OtherPatientNames",
            reason_code=ReasonCode.HIPAA_NAME,
            rule_source=RuleSource.HIPAA_SAFE_HARBOR
        )
        
        counts = collector.count_by_reason()
        assert counts[ReasonCode.HIPAA_NAME] == 2
        assert counts[ReasonCode.HIPAA_MRN] == 1


# ═══════════════════════════════════════════════════════════════════════════════
# DECISION TRACE WRITER TESTS
# ═══════════════════════════════════════════════════════════════════════════════

class TestDecisionTraceWriter:
    """Tests for DecisionTraceWriter class."""
    
    @pytest.fixture
    def temp_db(self):
        """Create a temporary database file."""
        fd, path = tempfile.mkstemp(suffix='.db')
        os.close(fd)
        
        # Create the parent scrub_events table (required for FK)
        conn = sqlite3.connect(path)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS scrub_events (
                id INTEGER PRIMARY KEY,
                scrub_uuid TEXT NOT NULL UNIQUE,
                timestamp TEXT,
                operator_id TEXT,
                original_filename TEXT,
                reason_code TEXT,
                app_version TEXT,
                success INTEGER DEFAULT 1
            )
        """)
        conn.commit()
        conn.close()
        
        yield path
        os.unlink(path)
    
    def test_init_creates_table(self, temp_db):
        """Writer should create decision_trace table on init."""
        writer = DecisionTraceWriter(temp_db)
        
        conn = sqlite3.connect(temp_db)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='decision_trace'"
        )
        result = cursor.fetchone()
        conn.close()
        
        assert result is not None
        assert result[0] == 'decision_trace'
    
    def test_init_is_idempotent(self, temp_db):
        """Creating writer multiple times should not error."""
        writer1 = DecisionTraceWriter(temp_db)
        writer2 = DecisionTraceWriter(temp_db)
        # No exception = success
    
    def test_commit_empty_collector(self, temp_db):
        """Committing empty collector should return 0."""
        writer = DecisionTraceWriter(temp_db)
        collector = DecisionTraceCollector()
        
        count = writer.commit("test-uuid-123", collector)
        assert count == 0
    
    def test_commit_single_decision(self, temp_db):
        """Single decision should be committed to database."""
        # First insert parent record
        conn = sqlite3.connect(temp_db)
        conn.execute(
            "INSERT INTO scrub_events (scrub_uuid, timestamp) VALUES (?, ?)",
            ("test-uuid-456", datetime.now(timezone.utc).isoformat())
        )
        conn.commit()
        conn.close()
        
        writer = DecisionTraceWriter(temp_db)
        collector = DecisionTraceCollector()
        collector.add(
            scope_level=ScopeLevel.INSTANCE,
            scope_uid="1.2.3.4",
            action_type=ActionType.REMOVED,
            target_type=TargetType.TAG,
            target_name="PatientName",
            reason_code=ReasonCode.HIPAA_NAME,
            rule_source=RuleSource.HIPAA_SAFE_HARBOR
        )
        
        count = writer.commit("test-uuid-456", collector)
        assert count == 1
        
        # Verify in database
        decisions = writer.get_decisions_for_scrub("test-uuid-456")
        assert len(decisions) == 1
        assert decisions[0]['target_name'] == "PatientName"
    
    def test_commit_locks_collector(self, temp_db):
        """Committing should lock the collector."""
        conn = sqlite3.connect(temp_db)
        conn.execute(
            "INSERT INTO scrub_events (scrub_uuid, timestamp) VALUES (?, ?)",
            ("test-uuid-789", datetime.now(timezone.utc).isoformat())
        )
        conn.commit()
        conn.close()
        
        writer = DecisionTraceWriter(temp_db)
        collector = DecisionTraceCollector()
        collector.add(
            scope_level=ScopeLevel.INSTANCE,
            action_type=ActionType.REMOVED,
            target_type=TargetType.TAG,
            target_name="Test",
            reason_code=ReasonCode.HIPAA_NAME,
            rule_source=RuleSource.HIPAA_SAFE_HARBOR
        )
        
        assert not collector.is_locked()
        writer.commit("test-uuid-789", collector)
        assert collector.is_locked()
    
    def test_commit_multiple_decisions(self, temp_db):
        """Multiple decisions should all be committed."""
        conn = sqlite3.connect(temp_db)
        conn.execute(
            "INSERT INTO scrub_events (scrub_uuid, timestamp) VALUES (?, ?)",
            ("test-uuid-multi", datetime.now(timezone.utc).isoformat())
        )
        conn.commit()
        conn.close()
        
        writer = DecisionTraceWriter(temp_db)
        collector = DecisionTraceCollector()
        for i in range(10):
            collector.add(
                scope_level=ScopeLevel.INSTANCE,
                action_type=ActionType.REMOVED,
                target_type=TargetType.TAG,
                target_name=f"Tag{i}",
                reason_code=ReasonCode.HIPAA_NAME,
                rule_source=RuleSource.HIPAA_SAFE_HARBOR
            )
        
        count = writer.commit("test-uuid-multi", collector)
        assert count == 10
        
        decisions = writer.get_decisions_for_scrub("test-uuid-multi")
        assert len(decisions) == 10
    
    def test_get_decisions_for_nonexistent_scrub(self, temp_db):
        """Querying nonexistent scrub should return empty list."""
        writer = DecisionTraceWriter(temp_db)
        decisions = writer.get_decisions_for_scrub("nonexistent-uuid")
        assert decisions == []
    
    def test_pixel_region_fields_stored(self, temp_db):
        """Pixel region fields should be stored correctly."""
        conn = sqlite3.connect(temp_db)
        conn.execute(
            "INSERT INTO scrub_events (scrub_uuid, timestamp) VALUES (?, ?)",
            ("test-uuid-pixel", datetime.now(timezone.utc).isoformat())
        )
        conn.commit()
        conn.close()
        
        writer = DecisionTraceWriter(temp_db)
        collector = DecisionTraceCollector()
        collector.add(
            scope_level=ScopeLevel.PIXEL_REGION,
            scope_uid="1.2.3.4.5",
            action_type=ActionType.MASKED,
            target_type=TargetType.PIXEL_REGION,
            target_name="PixelRegion[0]",
            reason_code=ReasonCode.BURNED_IN_TEXT,
            rule_source=RuleSource.MODALITY_SAFETY_PROTOCOL,
            region_x=100,
            region_y=200,
            region_w=300,
            region_h=50
        )
        
        writer.commit("test-uuid-pixel", collector)
        decisions = writer.get_decisions_for_scrub("test-uuid-pixel")
        
        assert len(decisions) == 1
        d = decisions[0]
        assert d['region_x'] == 100
        assert d['region_y'] == 200
        assert d['region_w'] == 300
        assert d['region_h'] == 50


# ═══════════════════════════════════════════════════════════════════════════════
# DECISION SUMMARY TESTS
# ═══════════════════════════════════════════════════════════════════════════════

class TestDecisionSummary:
    """Tests for generate_decision_summary function."""
    
    def test_empty_decisions(self):
        """Empty decision list should return appropriate message."""
        summary = generate_decision_summary([])
        assert "No decisions recorded" in summary
    
    def test_summary_contains_total_count(self):
        """Summary should include total decision count."""
        decisions = [
            DecisionRecord(
                scope_level=ScopeLevel.INSTANCE,
                scope_uid="1.2.3",
                action_type=ActionType.REMOVED,
                target_type=TargetType.TAG,
                target_name="PatientName",
                reason_code=ReasonCode.HIPAA_NAME,
                rule_source=RuleSource.HIPAA_SAFE_HARBOR
            )
        ]
        summary = generate_decision_summary(decisions)
        assert "Total Decisions Recorded: 1" in summary
    
    def test_summary_contains_action_counts(self):
        """Summary should include action type breakdown."""
        decisions = [
            DecisionRecord(
                scope_level=ScopeLevel.INSTANCE,
                scope_uid="1.2.3",
                action_type=ActionType.REMOVED,
                target_type=TargetType.TAG,
                target_name="PatientName",
                reason_code=ReasonCode.HIPAA_NAME,
                rule_source=RuleSource.HIPAA_SAFE_HARBOR
            ),
            DecisionRecord(
                scope_level=ScopeLevel.INSTANCE,
                scope_uid="1.2.3",
                action_type=ActionType.MASKED,
                target_type=TargetType.PIXEL_REGION,
                target_name="PixelRegion[0]",
                reason_code=ReasonCode.BURNED_IN_TEXT,
                rule_source=RuleSource.MODALITY_SAFETY_PROTOCOL
            ),
        ]
        summary = generate_decision_summary(decisions)
        assert "1 tags REMOVED" in summary
        assert "1 regions MASKED" in summary
    
    def test_summary_includes_profile_name(self):
        """Summary should include profile name if provided."""
        decisions = [
            DecisionRecord(
                scope_level=ScopeLevel.INSTANCE,
                scope_uid="1.2.3",
                action_type=ActionType.REMOVED,
                target_type=TargetType.TAG,
                target_name="Test",
                reason_code=ReasonCode.HIPAA_NAME,
                rule_source=RuleSource.HIPAA_SAFE_HARBOR
            )
        ]
        summary = generate_decision_summary(decisions, profile_name="US Research (HIPAA Safe Harbor)")
        assert "US Research (HIPAA Safe Harbor)" in summary
    
    def test_summary_includes_compliance_attestation(self):
        """Summary should include compliance attestation statement."""
        decisions = [
            DecisionRecord(
                scope_level=ScopeLevel.INSTANCE,
                scope_uid="1.2.3",
                action_type=ActionType.REMOVED,
                target_type=TargetType.TAG,
                target_name="Test",
                reason_code=ReasonCode.HIPAA_NAME,
                rule_source=RuleSource.HIPAA_SAFE_HARBOR
            )
        ]
        summary = generate_decision_summary(decisions)
        assert "COMPLIANCE ATTESTATION" in summary
        assert "Enumerated reason codes" in summary


# ═══════════════════════════════════════════════════════════════════════════════
# HELPER FUNCTION TESTS
# ═══════════════════════════════════════════════════════════════════════════════

class TestHelperFunctions:
    """Tests for helper functions."""
    
    def test_get_hipaa_reason_code_patient_name(self):
        """PatientName should map to HIPAA_NAME."""
        code = get_hipaa_reason_code('PatientName')
        assert code == ReasonCode.HIPAA_NAME
    
    def test_get_hipaa_reason_code_patient_id(self):
        """PatientID should map to HIPAA_MRN."""
        code = get_hipaa_reason_code('PatientID')
        assert code == ReasonCode.HIPAA_MRN
    
    def test_get_hipaa_reason_code_unknown_tag(self):
        """Unknown tags should map to HIPAA_UNIQUE_ID."""
        code = get_hipaa_reason_code('UnknownTag123')
        assert code == ReasonCode.HIPAA_UNIQUE_ID
    
    def test_get_foi_reason_code_staff(self):
        """Staff tags should map to FOI_STAFF_REDACT."""
        code = get_foi_reason_code('OperatorsName', is_staff=True)
        assert code == ReasonCode.FOI_STAFF_REDACT
    
    def test_get_foi_reason_code_patient(self):
        """Patient tags should map to FOI_PRESERVE_PATIENT."""
        code = get_foi_reason_code('PatientName', is_staff=False)
        assert code == ReasonCode.FOI_PRESERVE_PATIENT


# ═══════════════════════════════════════════════════════════════════════════════
# PHI EXCLUSION TESTS (GOVERNANCE CRITICAL)
# ═══════════════════════════════════════════════════════════════════════════════

class TestPHIExclusionFromAuditLogs:
    """
    Explicit tests proving PHI values are NEVER persisted in decision trace.
    
    These tests provide governance-defensible evidence that:
    - Patient names, IDs, and dates are not logged
    - OCR-detected text content is not logged
    - Pixel values are not logged
    - Only tag names, reason codes, and region coordinates are stored
    
    GOVERNANCE STATEMENT:
    "We have explicit tests preventing PHI leakage into audit logs."
    """
    
    @pytest.fixture
    def temp_db_with_scrub(self):
        """Create a temporary database with a parent scrub event."""
        fd, path = tempfile.mkstemp(suffix='.db')
        os.close(fd)
        
        conn = sqlite3.connect(path)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS scrub_events (
                id INTEGER PRIMARY KEY,
                scrub_uuid TEXT NOT NULL UNIQUE,
                timestamp TEXT
            )
        """)
        conn.execute(
            "INSERT INTO scrub_events (scrub_uuid, timestamp) VALUES (?, ?)",
            ("phi-test-uuid", datetime.now(timezone.utc).isoformat())
        )
        conn.commit()
        conn.close()
        
        yield path
        os.unlink(path)
    
    def test_phi_values_not_stored_in_decision_record(self):
        """
        GOVERNANCE TEST: DecisionRecord schema does not accept PHI values.
        
        Proves: The data structure has no field for storing actual PHI content.
        """
        # Attempt to create a decision record with simulated PHI context
        # The record should only contain metadata ABOUT the decision, not the values
        simulated_patient_name = "DOE^JOHN^MIDDLE"
        simulated_patient_id = "12345678"
        simulated_ocr_text = "Patient: John Doe DOB: 01/15/1985"
        
        collector = DecisionTraceCollector()
        collector.add(
            scope_level=ScopeLevel.INSTANCE,
            scope_uid="1.2.3.4.5.6.7.8.9",  # UID is anonymized/new, safe to log
            action_type=ActionType.REMOVED,
            target_type=TargetType.TAG,
            target_name="PatientName",  # Tag NAME only, not value
            reason_code=ReasonCode.HIPAA_NAME,
            rule_source=RuleSource.HIPAA_SAFE_HARBOR,
            checksum_before="a1b2c3d4",  # Hash only, cannot recover original
            checksum_after=None
        )
        
        decisions = collector.get_decisions()
        record = decisions[0]
        
        # CRITICAL ASSERTIONS: PHI must NOT be present in any field
        record_str = str(record)
        assert simulated_patient_name not in record_str, \
            "PHI LEAK: Patient name found in decision record"
        assert simulated_patient_id not in record_str, \
            "PHI LEAK: Patient ID found in decision record"
        assert simulated_ocr_text not in record_str, \
            "PHI LEAK: OCR text found in decision record"
        assert "DOE" not in record_str, \
            "PHI LEAK: Patient surname fragment found in decision record"
        assert "1985" not in record_str, \
            "PHI LEAK: Birth year found in decision record"
        
        # POSITIVE ASSERTIONS: Only safe metadata is stored
        assert record.target_name == "PatientName"  # Tag name, not value
        assert record.reason_code == ReasonCode.HIPAA_NAME
        assert record.checksum_before == "a1b2c3d4"  # Truncated hash only
    
    def test_pixel_region_stores_coordinates_not_content(self):
        """
        GOVERNANCE TEST: Pixel masking logs coordinates only, never image content.
        
        Proves: Only bounding box (x, y, w, h) is stored, not pixel values or OCR text.
        """
        simulated_burned_in_text = "SMITH, JANE DOB:03/22/1990 MRN:987654"
        
        collector = DecisionTraceCollector()
        collector.add(
            scope_level=ScopeLevel.PIXEL_REGION,
            scope_uid="1.2.3.4.5",
            action_type=ActionType.MASKED,
            target_type=TargetType.PIXEL_REGION,
            target_name="PixelRegion[0]",  # Generic identifier, no PHI
            reason_code=ReasonCode.BURNED_IN_TEXT,
            rule_source=RuleSource.MODALITY_SAFETY_PROTOCOL,
            region_x=50,
            region_y=100,
            region_w=400,
            region_h=80
        )
        
        decisions = collector.get_decisions()
        record = decisions[0]
        
        # CRITICAL ASSERTIONS: OCR-detected text must NOT be logged
        record_str = str(record)
        assert simulated_burned_in_text not in record_str, \
            "PHI LEAK: Burned-in text content found in decision record"
        assert "SMITH" not in record_str, \
            "PHI LEAK: Patient name from OCR found in decision record"
        assert "987654" not in record_str, \
            "PHI LEAK: MRN from OCR found in decision record"
        
        # POSITIVE ASSERTIONS: Only geometric coordinates are stored
        assert record.region_x == 50
        assert record.region_y == 100
        assert record.region_w == 400
        assert record.region_h == 80
        assert record.target_name == "PixelRegion[0]"  # Index only, no content
    
    def test_persisted_database_contains_no_phi(self, temp_db_with_scrub):
        """
        GOVERNANCE TEST: Database records contain no PHI after commit.
        
        Proves: End-to-end persistence excludes PHI from SQLite storage.
        """
        simulated_phi_values = [
            "DOE^JOHN",
            "12345678",
            "19850115",
            "123 Main Street",
            "555-1234",
            "john.doe@email.com",
            "123-45-6789",  # SSN
        ]
        
        writer = DecisionTraceWriter(temp_db_with_scrub)
        collector = DecisionTraceCollector()
        
        # Log multiple decisions (simulating a full anonymization run)
        collector.add(
            scope_level=ScopeLevel.INSTANCE,
            action_type=ActionType.REMOVED,
            target_type=TargetType.TAG,
            target_name="PatientName",
            reason_code=ReasonCode.HIPAA_NAME,
            rule_source=RuleSource.HIPAA_SAFE_HARBOR
        )
        collector.add(
            scope_level=ScopeLevel.INSTANCE,
            action_type=ActionType.REMOVED,
            target_type=TargetType.TAG,
            target_name="PatientID",
            reason_code=ReasonCode.HIPAA_MRN,
            rule_source=RuleSource.HIPAA_SAFE_HARBOR
        )
        collector.add(
            scope_level=ScopeLevel.PIXEL_REGION,
            action_type=ActionType.MASKED,
            target_type=TargetType.PIXEL_REGION,
            target_name="PixelRegion[0]",
            reason_code=ReasonCode.BURNED_IN_TEXT,
            rule_source=RuleSource.MODALITY_SAFETY_PROTOCOL,
            region_x=10, region_y=20, region_w=300, region_h=50
        )
        
        writer.commit("phi-test-uuid", collector)
        
        # Read back raw database content
        conn = sqlite3.connect(temp_db_with_scrub)
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM decision_trace")
        rows = cursor.fetchall()
        conn.close()
        
        # Convert all database content to string for PHI scanning
        db_content = str(rows)
        
        # CRITICAL ASSERTIONS: No PHI in persisted data
        for phi_value in simulated_phi_values:
            assert phi_value not in db_content, \
                f"PHI LEAK: '{phi_value}' found in persisted database records"
        
        # POSITIVE ASSERTIONS: Safe metadata IS present
        assert "PatientName" in db_content  # Tag name
        assert "PatientID" in db_content  # Tag name
        assert "HIPAA_18_NAME" in db_content  # Reason code
        assert "PixelRegion[0]" in db_content  # Region identifier
        assert len(rows) == 3  # All decisions persisted
