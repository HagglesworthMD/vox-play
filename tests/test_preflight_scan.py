"""
Unit Tests for Preflight Scan Module
=====================================
Sprint 2.5: Review-Only Preflight Scan

Tests for ReviewFinding, preflight_scan_dataset, and integration with ReviewSession.

SOP Class UIDs:
- Secondary Capture Image Storage: 1.2.840.10008.5.1.4.1.1.7
- Encapsulated PDF Storage: 1.2.840.10008.5.1.4.1.1.104.1

Run: PYTHONPATH=src pytest tests/test_preflight_scan.py -v
"""

import pytest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from review_session import (
    ReviewFinding,
    ReviewSession,
    FindingType,
    SOP_CLASS_UIDS,
    preflight_scan_dataset,
    preflight_scan_datasets,
)

# Use pydicom for creating test datasets
import pydicom
from pydicom.dataset import Dataset, FileDataset
from pydicom.uid import ExplicitVRLittleEndian, generate_uid
import numpy as np


# ═══════════════════════════════════════════════════════════════════════════════
# TEST FIXTURES
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.fixture
def secondary_capture_dataset():
    """Create a Secondary Capture DICOM dataset for testing."""
    ds = Dataset()
    ds.SOPClassUID = SOP_CLASS_UIDS["SECONDARY_CAPTURE"]  # 1.2.840.10008.5.1.4.1.1.7
    ds.SOPInstanceUID = generate_uid()
    ds.SeriesInstanceUID = generate_uid()
    ds.StudyInstanceUID = generate_uid()
    ds.Modality = "SC"
    ds.PatientName = "Test^Patient"
    ds.PatientID = "TEST001"
    return ds


@pytest.fixture
def encapsulated_pdf_dataset():
    """Create an Encapsulated PDF DICOM dataset for testing."""
    ds = Dataset()
    ds.SOPClassUID = SOP_CLASS_UIDS["ENCAPSULATED_PDF"]  # 1.2.840.10008.5.1.4.1.1.104.1
    ds.SOPInstanceUID = generate_uid()
    ds.SeriesInstanceUID = generate_uid()
    ds.StudyInstanceUID = generate_uid()
    ds.Modality = "DOC"
    ds.PatientName = "Test^Patient"
    ds.PatientID = "TEST001"
    return ds


@pytest.fixture
def standard_ct_dataset():
    """Create a standard CT DICOM dataset that should NOT be flagged."""
    ds = Dataset()
    ds.SOPClassUID = "1.2.840.10008.5.1.4.1.1.2"  # CT Image Storage
    ds.SOPInstanceUID = generate_uid()
    ds.SeriesInstanceUID = generate_uid()
    ds.StudyInstanceUID = generate_uid()
    ds.Modality = "CT"
    ds.PatientName = "Test^Patient"
    ds.PatientID = "TEST001"
    return ds


@pytest.fixture
def standard_us_dataset():
    """Create a standard Ultrasound DICOM dataset that should NOT be flagged."""
    ds = Dataset()
    ds.SOPClassUID = "1.2.840.10008.5.1.4.1.1.6.1"  # Ultrasound Image Storage
    ds.SOPInstanceUID = generate_uid()
    ds.SeriesInstanceUID = generate_uid()
    ds.StudyInstanceUID = generate_uid()
    ds.Modality = "US"
    ds.PatientName = "Test^Patient"
    ds.PatientID = "TEST001"
    return ds


@pytest.fixture
def minimal_dataset():
    """Create a minimal dataset with only SOPClassUID."""
    ds = Dataset()
    ds.SOPClassUID = SOP_CLASS_UIDS["SECONDARY_CAPTURE"]
    return ds


@pytest.fixture
def empty_dataset():
    """Create an empty dataset with no attributes."""
    return Dataset()


# ═══════════════════════════════════════════════════════════════════════════════
# SOP CLASS UID CONSTANTS TESTS
# ═══════════════════════════════════════════════════════════════════════════════

class TestSOPClassUIDs:
    """Tests for SOP Class UID constants."""
    
    def test_secondary_capture_uid_is_correct(self):
        """Secondary Capture UID should match DICOM standard."""
        assert SOP_CLASS_UIDS["SECONDARY_CAPTURE"] == "1.2.840.10008.5.1.4.1.1.7"
    
    def test_encapsulated_pdf_uid_is_correct(self):
        """Encapsulated PDF UID should match DICOM standard."""
        assert SOP_CLASS_UIDS["ENCAPSULATED_PDF"] == "1.2.840.10008.5.1.4.1.1.104.1"
    
    def test_finding_types_are_defined(self):
        """FindingType enum should have expected values."""
        assert FindingType.SECONDARY_CAPTURE == "SECONDARY_CAPTURE"
        assert FindingType.ENCAPSULATED_PDF == "ENCAPSULATED_PDF"


# ═══════════════════════════════════════════════════════════════════════════════
# REVIEW FINDING CREATION TESTS
# ═══════════════════════════════════════════════════════════════════════════════

class TestReviewFindingCreation:
    """Tests for ReviewFinding dataclass creation."""
    
    def test_create_secondary_capture_finding(self):
        """Should create finding for Secondary Capture SOP Class."""
        finding = ReviewFinding.from_sop_class(
            sop_instance_uid="1.2.3.4.5",
            sop_class_uid=SOP_CLASS_UIDS["SECONDARY_CAPTURE"],
            series_instance_uid="1.2.3.4.6",
            modality="SC",
        )
        
        assert finding is not None
        assert finding.finding_type == FindingType.SECONDARY_CAPTURE
        assert finding.sop_instance_uid == "1.2.3.4.5"
        assert finding.sop_class_uid == SOP_CLASS_UIDS["SECONDARY_CAPTURE"]
        assert finding.series_instance_uid == "1.2.3.4.6"
        assert finding.modality == "SC"
        assert "Secondary Capture" in finding.description
    
    def test_create_encapsulated_pdf_finding(self):
        """Should create finding for Encapsulated PDF SOP Class."""
        finding = ReviewFinding.from_sop_class(
            sop_instance_uid="1.2.3.4.5",
            sop_class_uid=SOP_CLASS_UIDS["ENCAPSULATED_PDF"],
            series_instance_uid="1.2.3.4.6",
            modality="DOC",
        )
        
        assert finding is not None
        assert finding.finding_type == FindingType.ENCAPSULATED_PDF
        assert finding.sop_instance_uid == "1.2.3.4.5"
        assert finding.sop_class_uid == SOP_CLASS_UIDS["ENCAPSULATED_PDF"]
        assert finding.series_instance_uid == "1.2.3.4.6"
        assert finding.modality == "DOC"
        assert "PDF" in finding.description
    
    def test_returns_none_for_unknown_sop_class(self):
        """Should return None for unrecognized SOP Class UIDs."""
        finding = ReviewFinding.from_sop_class(
            sop_instance_uid="1.2.3.4.5",
            sop_class_uid="1.2.840.10008.5.1.4.1.1.2",  # CT Image Storage
            series_instance_uid="1.2.3.4.6",
            modality="CT",
        )
        
        assert finding is None
    
    def test_optional_modality(self):
        """Should handle missing modality gracefully."""
        finding = ReviewFinding.from_sop_class(
            sop_instance_uid="1.2.3.4.5",
            sop_class_uid=SOP_CLASS_UIDS["SECONDARY_CAPTURE"],
            series_instance_uid="1.2.3.4.6",
            modality=None,
        )
        
        assert finding is not None
        assert finding.modality is None
    
    def test_to_dict_serialization(self):
        """to_dict should return complete dictionary representation."""
        finding = ReviewFinding.from_sop_class(
            sop_instance_uid="1.2.3.4.5",
            sop_class_uid=SOP_CLASS_UIDS["SECONDARY_CAPTURE"],
            series_instance_uid="1.2.3.4.6",
            modality="SC",
        )
        
        d = finding.to_dict()
        
        assert d["sop_instance_uid"] == "1.2.3.4.5"
        assert d["sop_class_uid"] == SOP_CLASS_UIDS["SECONDARY_CAPTURE"]
        assert d["series_instance_uid"] == "1.2.3.4.6"
        assert d["finding_type"] == FindingType.SECONDARY_CAPTURE
        assert d["modality"] == "SC"
        assert "description" in d


# ═══════════════════════════════════════════════════════════════════════════════
# PREFLIGHT SCAN DATASET TESTS
# ═══════════════════════════════════════════════════════════════════════════════

class TestPreflightScanDataset:
    """Tests for preflight_scan_dataset function."""
    
    def test_detect_secondary_capture(self, secondary_capture_dataset):
        """Should detect Secondary Capture dataset."""
        finding = preflight_scan_dataset(secondary_capture_dataset)
        
        assert finding is not None
        assert finding.finding_type == FindingType.SECONDARY_CAPTURE
        assert finding.sop_class_uid == SOP_CLASS_UIDS["SECONDARY_CAPTURE"]
        assert finding.modality == "SC"
    
    def test_detect_encapsulated_pdf(self, encapsulated_pdf_dataset):
        """Should detect Encapsulated PDF dataset."""
        finding = preflight_scan_dataset(encapsulated_pdf_dataset)
        
        assert finding is not None
        assert finding.finding_type == FindingType.ENCAPSULATED_PDF
        assert finding.sop_class_uid == SOP_CLASS_UIDS["ENCAPSULATED_PDF"]
        assert finding.modality == "DOC"
    
    def test_no_finding_for_ct(self, standard_ct_dataset):
        """CT dataset should NOT produce a finding."""
        finding = preflight_scan_dataset(standard_ct_dataset)
        
        assert finding is None
    
    def test_no_finding_for_ultrasound(self, standard_us_dataset):
        """Ultrasound dataset should NOT produce a finding."""
        finding = preflight_scan_dataset(standard_us_dataset)
        
        assert finding is None
    
    def test_handles_minimal_dataset(self, minimal_dataset):
        """Should handle dataset with minimal attributes."""
        finding = preflight_scan_dataset(minimal_dataset)
        
        assert finding is not None
        assert finding.finding_type == FindingType.SECONDARY_CAPTURE
        assert finding.sop_instance_uid == "UNKNOWN"  # Missing attribute
        assert finding.series_instance_uid == "UNKNOWN"
        assert finding.modality is None
    
    def test_handles_empty_dataset(self, empty_dataset):
        """Should handle empty dataset without error."""
        finding = preflight_scan_dataset(empty_dataset)
        
        assert finding is None  # No SOPClassUID = no finding
    
    def test_deterministic_output(self, secondary_capture_dataset):
        """Same dataset should produce identical findings."""
        finding1 = preflight_scan_dataset(secondary_capture_dataset)
        finding2 = preflight_scan_dataset(secondary_capture_dataset)
        
        assert finding1.sop_instance_uid == finding2.sop_instance_uid
        assert finding1.finding_type == finding2.finding_type
        assert finding1.description == finding2.description
    
    def test_extracts_sop_instance_uid(self, secondary_capture_dataset):
        """Should correctly extract SOP Instance UID from dataset."""
        expected_uid = str(secondary_capture_dataset.SOPInstanceUID)
        finding = preflight_scan_dataset(secondary_capture_dataset)
        
        assert finding.sop_instance_uid == expected_uid
    
    def test_extracts_series_instance_uid(self, secondary_capture_dataset):
        """Should correctly extract Series Instance UID from dataset."""
        expected_uid = str(secondary_capture_dataset.SeriesInstanceUID)
        finding = preflight_scan_dataset(secondary_capture_dataset)
        
        assert finding.series_instance_uid == expected_uid


# ═══════════════════════════════════════════════════════════════════════════════
# PREFLIGHT SCAN DATASETS (BATCH) TESTS
# ═══════════════════════════════════════════════════════════════════════════════

class TestPreflightScanDatasets:
    """Tests for preflight_scan_datasets batch function."""
    
    def test_batch_scan_empty_list(self):
        """Should return empty list for empty input."""
        findings = preflight_scan_datasets([])
        
        assert findings == []
    
    def test_batch_scan_mixed_datasets(
        self,
        secondary_capture_dataset,
        encapsulated_pdf_dataset,
        standard_ct_dataset,
    ):
        """Should return findings only for reviewable datasets."""
        datasets = [
            secondary_capture_dataset,
            standard_ct_dataset,  # Should not produce finding
            encapsulated_pdf_dataset,
        ]
        
        findings = preflight_scan_datasets(datasets)
        
        assert len(findings) == 2
        types = [f.finding_type for f in findings]
        assert FindingType.SECONDARY_CAPTURE in types
        assert FindingType.ENCAPSULATED_PDF in types
    
    def test_batch_scan_all_normal(
        self,
        standard_ct_dataset,
        standard_us_dataset,
    ):
        """Should return empty list when no reviewable datasets."""
        datasets = [standard_ct_dataset, standard_us_dataset]
        
        findings = preflight_scan_datasets(datasets)
        
        assert findings == []
    
    def test_batch_scan_preserves_order(
        self,
        secondary_capture_dataset,
        encapsulated_pdf_dataset,
    ):
        """Findings should be in same order as input datasets."""
        datasets = [secondary_capture_dataset, encapsulated_pdf_dataset]
        
        findings = preflight_scan_datasets(datasets)
        
        assert findings[0].finding_type == FindingType.SECONDARY_CAPTURE
        assert findings[1].finding_type == FindingType.ENCAPSULATED_PDF


# ═══════════════════════════════════════════════════════════════════════════════
# REVIEW SESSION INTEGRATION TESTS
# ═══════════════════════════════════════════════════════════════════════════════

class TestReviewSessionFindings:
    """Tests for ReviewSession integration with preflight findings."""
    
    def test_new_session_has_no_findings(self):
        """New session should have empty findings list."""
        session = ReviewSession.create(sop_instance_uid="1.2.3.4.5")
        
        assert session.review_findings == []
        assert not session.has_findings()
    
    def test_add_finding(self, secondary_capture_dataset):
        """Should be able to add finding to session."""
        session = ReviewSession.create(sop_instance_uid="1.2.3.4.5")
        finding = preflight_scan_dataset(secondary_capture_dataset)
        
        session.add_finding(finding)
        
        assert len(session.review_findings) == 1
        assert session.has_findings()
    
    def test_get_findings_returns_copy(self, secondary_capture_dataset):
        """get_findings should return a copy of the list."""
        session = ReviewSession.create(sop_instance_uid="1.2.3.4.5")
        finding = preflight_scan_dataset(secondary_capture_dataset)
        session.add_finding(finding)
        
        findings = session.get_findings()
        findings.clear()  # Modify the returned list
        
        assert session.has_findings()  # Original should be unaffected
    
    def test_get_findings_by_type(
        self,
        secondary_capture_dataset,
        encapsulated_pdf_dataset,
    ):
        """Should filter findings by type correctly."""
        session = ReviewSession.create(sop_instance_uid="1.2.3.4.5")
        session.add_finding(preflight_scan_dataset(secondary_capture_dataset))
        session.add_finding(preflight_scan_dataset(encapsulated_pdf_dataset))
        
        sc_findings = session.get_findings_by_type(FindingType.SECONDARY_CAPTURE)
        pdf_findings = session.get_findings_by_type(FindingType.ENCAPSULATED_PDF)
        
        assert len(sc_findings) == 1
        assert len(pdf_findings) == 1
        assert sc_findings[0].finding_type == FindingType.SECONDARY_CAPTURE
        assert pdf_findings[0].finding_type == FindingType.ENCAPSULATED_PDF
    
    def test_get_findings_summary(
        self,
        secondary_capture_dataset,
        encapsulated_pdf_dataset,
    ):
        """Should return correct summary counts."""
        session = ReviewSession.create(sop_instance_uid="1.2.3.4.5")
        session.add_finding(preflight_scan_dataset(secondary_capture_dataset))
        session.add_finding(preflight_scan_dataset(encapsulated_pdf_dataset))
        
        summary = session.get_findings_summary()
        
        assert summary["total_findings"] == 2
        assert summary["secondary_capture"] == 1
        assert summary["encapsulated_pdf"] == 1
    
    def test_get_summary_includes_findings_count(
        self,
        secondary_capture_dataset,
    ):
        """get_summary should include review_findings count."""
        session = ReviewSession.create(sop_instance_uid="1.2.3.4.5")
        session.add_finding(preflight_scan_dataset(secondary_capture_dataset))
        
        summary = session.get_summary()
        
        assert "review_findings" in summary
        assert summary["review_findings"] == 1


# ═══════════════════════════════════════════════════════════════════════════════
# PROCESSING ISOLATION TESTS
# Critical: Verify findings do NOT affect processing results
# ═══════════════════════════════════════════════════════════════════════════════

class TestFindingsDoNotAffectProcessing:
    """
    Critical tests to verify that preflight findings do NOT affect:
    - Masking decisions
    - Region detection
    - Accept gating
    - Export behavior
    """
    
    def test_findings_do_not_affect_region_counts(
        self,
        secondary_capture_dataset,
    ):
        """Findings should not change region counts."""
        session = ReviewSession.create(sop_instance_uid="1.2.3.4.5")
        
        # Add regions
        session.add_ocr_region(x=50, y=100, w=400, h=80)
        session.add_manual_region(x=200, y=300, w=150, h=40)
        
        regions_before = len(session.get_regions())
        
        # Add findings
        session.add_finding(preflight_scan_dataset(secondary_capture_dataset))
        
        regions_after = len(session.get_regions())
        
        assert regions_before == regions_after == 2
    
    def test_findings_do_not_affect_masked_regions(
        self,
        secondary_capture_dataset,
    ):
        """Findings should not change which regions will be masked."""
        session = ReviewSession.create(sop_instance_uid="1.2.3.4.5")
        
        # Add regions with known state
        session.add_ocr_region(x=50, y=100, w=400, h=80)  # Default MASK
        session.add_ocr_region(x=50, y=200, w=300, h=60)
        session.regions[1].toggle()  # Toggle to UNMASK
        
        masked_before = [r.get_effective_action() for r in session.get_masked_regions()]
        
        # Add findings
        session.add_finding(preflight_scan_dataset(secondary_capture_dataset))
        
        masked_after = [r.get_effective_action() for r in session.get_masked_regions()]
        
        assert masked_before == masked_after
    
    def test_findings_do_not_affect_accept_gating(
        self,
        secondary_capture_dataset,
    ):
        """Findings should not change accept gating behavior."""
        session = ReviewSession.create(sop_instance_uid="1.2.3.4.5")
        
        # Verify can't accept before starting review
        assert not session.can_accept()
        
        # Add findings (should not change gating)
        session.add_finding(preflight_scan_dataset(secondary_capture_dataset))
        
        assert not session.can_accept()
        
        # Start review and verify accept works normally
        session.start_review()
        assert session.can_accept()
        
        session.accept()
        assert session.is_sealed()
    
    def test_findings_can_be_added_after_seal(
        self,
        secondary_capture_dataset,
    ):
        """Findings can be added even after session is sealed."""
        session = ReviewSession.create(sop_instance_uid="1.2.3.4.5")
        session.start_review()
        session.accept()
        
        # This should NOT raise (findings are informational)
        session.add_finding(preflight_scan_dataset(secondary_capture_dataset))
        
        assert session.has_findings()
    
    def test_findings_persist_through_session_lifecycle(
        self,
        secondary_capture_dataset,
        encapsulated_pdf_dataset,
    ):
        """Findings should persist through entire session lifecycle."""
        session = ReviewSession.create(sop_instance_uid="1.2.3.4.5")
        
        # Add finding before review
        session.add_finding(preflight_scan_dataset(secondary_capture_dataset))
        
        # Start review, add regions
        session.start_review()
        session.add_ocr_region(x=50, y=100, w=400, h=80)
        
        # Accept
        session.accept()
        
        # Add another finding after seal
        session.add_finding(preflight_scan_dataset(encapsulated_pdf_dataset))
        
        # All findings should be present
        assert len(session.get_findings()) == 2


# ═══════════════════════════════════════════════════════════════════════════════
# DETERMINISM / REPRODUCIBILITY TESTS
# ═══════════════════════════════════════════════════════════════════════════════

class TestDeterminism:
    """Tests to verify deterministic, reproducible behavior."""
    
    def test_same_dataset_produces_same_finding(self, secondary_capture_dataset):
        """Scanning the same dataset should always produce identical findings."""
        # Scan multiple times
        findings = [preflight_scan_dataset(secondary_capture_dataset) for _ in range(5)]
        
        # All should have identical attributes
        for finding in findings:
            assert finding.sop_instance_uid == findings[0].sop_instance_uid
            assert finding.sop_class_uid == findings[0].sop_class_uid
            assert finding.series_instance_uid == findings[0].series_instance_uid
            assert finding.finding_type == findings[0].finding_type
            assert finding.modality == findings[0].modality
            assert finding.description == findings[0].description
    
    def test_finding_type_is_deterministic_by_sop_class(self):
        """Finding type should always map to same SOP Class UID."""
        for _ in range(10):
            sc_finding = ReviewFinding.from_sop_class(
                sop_instance_uid="test",
                sop_class_uid=SOP_CLASS_UIDS["SECONDARY_CAPTURE"],
                series_instance_uid="test",
            )
            pdf_finding = ReviewFinding.from_sop_class(
                sop_instance_uid="test",
                sop_class_uid=SOP_CLASS_UIDS["ENCAPSULATED_PDF"],
                series_instance_uid="test",
            )
            
            assert sc_finding.finding_type == FindingType.SECONDARY_CAPTURE
            assert pdf_finding.finding_type == FindingType.ENCAPSULATED_PDF


# ═══════════════════════════════════════════════════════════════════════════════
# EDGE CASE TESTS
# ═══════════════════════════════════════════════════════════════════════════════

class TestEdgeCases:
    """Tests for edge cases and boundary conditions."""
    
    def test_dataset_with_pydicom_uid_object(self):
        """Should handle pydicom UID objects (not just strings)."""
        from pydicom.uid import UID
        
        ds = Dataset()
        # pydicom often wraps UIDs in UID objects
        ds.SOPClassUID = UID(SOP_CLASS_UIDS["SECONDARY_CAPTURE"])
        ds.SOPInstanceUID = UID("1.2.3.4.5")
        ds.SeriesInstanceUID = UID("1.2.3.4.6")
        ds.Modality = "SC"
        
        finding = preflight_scan_dataset(ds)
        
        assert finding is not None
        assert finding.finding_type == FindingType.SECONDARY_CAPTURE
        # UIDs should be converted to strings
        assert isinstance(finding.sop_instance_uid, str)
        assert isinstance(finding.sop_class_uid, str)
    
    def test_dataset_with_none_sop_class(self):
        """Should handle dataset with None SOPClassUID."""
        ds = Dataset()
        ds.SOPClassUID = None
        
        finding = preflight_scan_dataset(ds)
        
        # Actually, pydicom will set this as a Sequence element,
        # but we check for None explicitly
        # For safety, this test verifies no exception is raised
        assert finding is None
    
    def test_very_long_uids(self):
        """Should handle unusually long UIDs."""
        ds = Dataset()
        long_uid = "1.2.3.4.5.6.7.8.9.10.11.12.13.14.15.16.17.18.19.20.21.22.23.24.25"
        ds.SOPClassUID = SOP_CLASS_UIDS["SECONDARY_CAPTURE"]
        ds.SOPInstanceUID = long_uid
        ds.SeriesInstanceUID = long_uid
        ds.Modality = "SC"
        
        finding = preflight_scan_dataset(ds)
        
        assert finding is not None
        assert finding.sop_instance_uid == long_uid
    
    def test_multiple_findings_same_session(self):
        """Should handle many findings in a single session."""
        session = ReviewSession.create(sop_instance_uid="1.2.3.4.5")
        
        # Add 100 findings
        for i in range(100):
            ds = Dataset()
            ds.SOPClassUID = SOP_CLASS_UIDS["SECONDARY_CAPTURE"]
            ds.SOPInstanceUID = f"1.2.3.4.{i}"
            ds.SeriesInstanceUID = "1.2.3.4.0"
            ds.Modality = "SC"
            
            finding = preflight_scan_dataset(ds)
            session.add_finding(finding)
        
        assert len(session.get_findings()) == 100
        summary = session.get_findings_summary()
        assert summary["total_findings"] == 100
        assert summary["secondary_capture"] == 100


# ═══════════════════════════════════════════════════════════════════════════════
# APP INTEGRATION WORKFLOW TEST
# Simulates the exact workflow pattern used in app.py for wiring preflight scan
# ═══════════════════════════════════════════════════════════════════════════════

class TestAppIntegrationWorkflow:
    """
    Tests simulating the app.py integration pattern.
    
    This verifies that:
    1. Session is created first
    2. Datasets are scanned and findings added
    3. Normal processing remains unaffected
    """
    
    def test_session_creation_then_scan_workflow(
        self,
        secondary_capture_dataset,
        encapsulated_pdf_dataset,
        standard_us_dataset,
        standard_ct_dataset,
    ):
        """Simulate exact app.py workflow: create session, then scan datasets."""
        # Step 1: Create session (as in app.py line ~2248)
        session = ReviewSession.create(sop_instance_uid="1.2.3.4.5")
        
        # Step 2: Scan all available datasets (as in app.py preflight scan block)
        datasets = [
            secondary_capture_dataset,  # Should produce SC finding
            encapsulated_pdf_dataset,   # Should produce PDF finding
            standard_us_dataset,        # Should NOT produce finding
            standard_ct_dataset,        # Should NOT produce finding
        ]
        
        for ds in datasets:
            try:
                finding = preflight_scan_dataset(ds)
                if finding is not None:
                    session.add_finding(finding)
            except Exception:
                pass  # Non-fatal, as in app.py
        
        # Verify findings are populated correctly
        assert session.has_findings()
        assert len(session.get_findings()) == 2
        
        summary = session.get_findings_summary()
        assert summary["secondary_capture"] == 1
        assert summary["encapsulated_pdf"] == 1
    
    def test_findings_populated_but_processing_unaffected(
        self,
        secondary_capture_dataset,
    ):
        """
        KEY TEST: Findings are populated but don't alter processing behavior.
        
        This is the critical guarantee for freeze-safety.
        """
        # Create session and add findings
        session = ReviewSession.create(sop_instance_uid="1.2.3.4.5")
        session.add_finding(preflight_scan_dataset(secondary_capture_dataset))
        
        # Now simulate normal processing workflow
        session.add_ocr_region(x=50, y=100, w=400, h=80)
        session.add_ocr_region(x=50, y=200, w=300, h=60)
        session.add_manual_region(x=200, y=300, w=150, h=40)
        
        # Verify regions are tracked separately from findings
        assert len(session.get_regions()) == 3
        assert len(session.get_findings()) == 1
        
        # Toggle region
        session.regions[0].toggle()
        
        # Start review and accept
        session.start_review()
        assert session.can_accept()
        session.accept()
        
        # After seal, verify:
        # 1. Findings still present
        assert session.has_findings()
        # 2. Regions still present
        assert len(session.get_regions()) == 3
        # 3. Masked regions computed correctly (NOT affected by findings)
        masked = session.get_masked_regions()
        assert len(masked) == 2  # 2 regions masked (1 OCR toggled to unmask, 1 OCR + 1 manual = 2 masked)
    
    def test_scan_failure_is_non_fatal(self):
        """
        Preflight scan failures should not block session creation.
        
        This matches the try/except pattern in app.py.
        """
        # Create session
        session = ReviewSession.create(sop_instance_uid="1.2.3.4.5")
        
        # Simulate scan with mixed valid/invalid datasets
        datasets = [
            Dataset(),  # Empty - will return None, not raise
            None,       # Invalid - will raise in real scan
        ]
        
        scan_errors = 0
        for ds in datasets:
            try:
                if ds is not None:
                    finding = preflight_scan_dataset(ds)
                    if finding is not None:
                        session.add_finding(finding)
                else:
                    raise ValueError("None dataset")
            except Exception:
                scan_errors += 1
        
        # Session should still be valid
        assert session is not None
        assert session.sop_instance_uid == "1.2.3.4.5"
        assert scan_errors == 1  # Only the None raised


# ═══════════════════════════════════════════════════════════════════════════════
# PDF EXCLUSION TESTS
# Phase 2: User-driven exclusion of Encapsulated PDFs
# ═══════════════════════════════════════════════════════════════════════════════

class TestPDFExclusion:
    """Tests for manual PDF exclusion functionality."""
    
    def test_pdf_finding_default_not_excluded(self, encapsulated_pdf_dataset):
        """PDF findings should be included by default."""
        finding = preflight_scan_dataset(encapsulated_pdf_dataset)
        
        assert finding is not None
        assert finding.excluded is False
        assert finding.excluded_at is None
    
    def test_set_excluded_on_finding(self, encapsulated_pdf_dataset):
        """Should be able to set exclusion state on a finding."""
        finding = preflight_scan_dataset(encapsulated_pdf_dataset)
        
        finding.set_excluded(True)
        
        assert finding.excluded is True
        assert finding.excluded_at is not None
        # Timestamp should be in ISO format with Z suffix
        assert finding.excluded_at.endswith("Z")
    
    def test_set_excluded_clears_timestamp_on_include(self, encapsulated_pdf_dataset):
        """Re-including should clear the exclusion timestamp."""
        finding = preflight_scan_dataset(encapsulated_pdf_dataset)
        
        finding.set_excluded(True)
        assert finding.excluded_at is not None
        
        finding.set_excluded(False)
        assert finding.excluded is False
        assert finding.excluded_at is None
    
    def test_session_set_pdf_excluded(self, encapsulated_pdf_dataset):
        """Session should be able to set PDF exclusion by UID."""
        session = ReviewSession.create(sop_instance_uid="1.2.3.4.5")
        finding = preflight_scan_dataset(encapsulated_pdf_dataset)
        session.add_finding(finding)
        
        # Exclude the PDF
        result = session.set_pdf_excluded(finding.sop_instance_uid, True)
        
        assert result is True
        assert finding.excluded is True
    
    def test_session_set_pdf_excluded_returns_false_for_unknown_uid(self, encapsulated_pdf_dataset):
        """Should return False if UID not found."""
        session = ReviewSession.create(sop_instance_uid="1.2.3.4.5")
        finding = preflight_scan_dataset(encapsulated_pdf_dataset)
        session.add_finding(finding)
        
        result = session.set_pdf_excluded("UNKNOWN_UID", True)
        
        assert result is False
    
    def test_session_set_pdf_excluded_blocked_after_seal(self, encapsulated_pdf_dataset):
        """Should not allow exclusion changes after session is sealed."""
        session = ReviewSession.create(sop_instance_uid="1.2.3.4.5")
        finding = preflight_scan_dataset(encapsulated_pdf_dataset)
        session.add_finding(finding)
        session.start_review()
        session.accept()  # Seal the session
        
        result = session.set_pdf_excluded(finding.sop_instance_uid, True)
        
        assert result is False
        assert finding.excluded is False  # Should remain unchanged
    
    def test_get_excluded_pdf_uids(self, encapsulated_pdf_dataset):
        """Should return list of excluded PDF UIDs."""
        session = ReviewSession.create(sop_instance_uid="1.2.3.4.5")
        
        # Add multiple PDF findings
        pdf1 = preflight_scan_dataset(encapsulated_pdf_dataset)
        session.add_finding(pdf1)
        
        # Create second PDF with different UID
        ds2 = Dataset()
        ds2.SOPClassUID = SOP_CLASS_UIDS["ENCAPSULATED_PDF"]
        ds2.SOPInstanceUID = "1.2.3.999.888.777"
        ds2.SeriesInstanceUID = "1.2.3.999.888"
        ds2.Modality = "DOC"
        pdf2 = preflight_scan_dataset(ds2)
        session.add_finding(pdf2)
        
        # Exclude only the first PDF
        session.set_pdf_excluded(pdf1.sop_instance_uid, True)
        
        excluded_uids = session.get_excluded_pdf_uids()
        
        assert len(excluded_uids) == 1
        assert pdf1.sop_instance_uid in excluded_uids
        assert pdf2.sop_instance_uid not in excluded_uids
    
    def test_get_pdf_findings(self, encapsulated_pdf_dataset, secondary_capture_dataset):
        """Should return only PDF findings, not SC."""
        session = ReviewSession.create(sop_instance_uid="1.2.3.4.5")
        session.add_finding(preflight_scan_dataset(encapsulated_pdf_dataset))
        session.add_finding(preflight_scan_dataset(secondary_capture_dataset))
        
        pdf_findings = session.get_pdf_findings()
        
        assert len(pdf_findings) == 1
        assert pdf_findings[0].finding_type == FindingType.ENCAPSULATED_PDF
    
    def test_exclusion_does_not_affect_sc_findings(self, secondary_capture_dataset):
        """SC findings should not be affected by PDF exclusion logic."""
        session = ReviewSession.create(sop_instance_uid="1.2.3.4.5")
        sc_finding = preflight_scan_dataset(secondary_capture_dataset)
        session.add_finding(sc_finding)
        
        # Try to exclude SC as if it were a PDF (should fail)
        result = session.set_pdf_excluded(sc_finding.sop_instance_uid, True)
        
        assert result is False
        assert sc_finding.excluded is False
    
    def test_findings_summary_includes_excluded_count(self, encapsulated_pdf_dataset):
        """Summary should include count of excluded PDFs."""
        session = ReviewSession.create(sop_instance_uid="1.2.3.4.5")
        pdf = preflight_scan_dataset(encapsulated_pdf_dataset)
        session.add_finding(pdf)
        session.set_pdf_excluded(pdf.sop_instance_uid, True)
        
        summary = session.get_findings_summary()
        
        assert summary["encapsulated_pdf"] == 1
        assert summary["excluded_pdf"] == 1
    
    def test_to_dict_includes_exclusion_state(self, encapsulated_pdf_dataset):
        """to_dict should include exclusion fields."""
        finding = preflight_scan_dataset(encapsulated_pdf_dataset)
        finding.set_excluded(True)
        
        d = finding.to_dict()
        
        assert "excluded" in d
        assert "excluded_at" in d
        assert d["excluded"] is True
        assert d["excluded_at"] is not None


class TestPDFExclusionDoesNotAffectProcessing:
    """
    Critical tests to verify PDF exclusion does NOT affect:
    - Masking decisions
    - Region detection
    - Accept gating
    - Anonymisation outputs
    """
    
    def test_exclusion_does_not_affect_region_counts(self, encapsulated_pdf_dataset):
        """Excluding PDFs should not change region counts."""
        session = ReviewSession.create(sop_instance_uid="1.2.3.4.5")
        session.add_ocr_region(x=50, y=100, w=400, h=80)
        session.add_manual_region(x=200, y=300, w=150, h=40)
        
        regions_before = len(session.get_regions())
        
        # Add and exclude PDF
        pdf = preflight_scan_dataset(encapsulated_pdf_dataset)
        session.add_finding(pdf)
        session.set_pdf_excluded(pdf.sop_instance_uid, True)
        
        regions_after = len(session.get_regions())
        
        assert regions_before == regions_after == 2
    
    def test_exclusion_does_not_affect_masked_regions(self, encapsulated_pdf_dataset):
        """Excluding PDFs should not change which regions will be masked."""
        session = ReviewSession.create(sop_instance_uid="1.2.3.4.5")
        session.add_ocr_region(x=50, y=100, w=400, h=80)
        
        masked_before = len(session.get_masked_regions())
        
        pdf = preflight_scan_dataset(encapsulated_pdf_dataset)
        session.add_finding(pdf)
        session.set_pdf_excluded(pdf.sop_instance_uid, True)
        
        masked_after = len(session.get_masked_regions())
        
        assert masked_before == masked_after
    
    def test_exclusion_does_not_affect_accept_gating(self, encapsulated_pdf_dataset):
        """PDF exclusion should not change accept gating behavior."""
        session = ReviewSession.create(sop_instance_uid="1.2.3.4.5")
        pdf = preflight_scan_dataset(encapsulated_pdf_dataset)
        session.add_finding(pdf)
        session.set_pdf_excluded(pdf.sop_instance_uid, True)
        
        # Verify gating still works normally
        assert not session.can_accept()
        
        session.start_review()
        assert session.can_accept()
        
        session.accept()
        assert session.is_sealed()
    
    def test_exclusion_reversible_before_seal(self, encapsulated_pdf_dataset):
        """Exclusion should be reversible until session is sealed."""
        session = ReviewSession.create(sop_instance_uid="1.2.3.4.5")
        pdf = preflight_scan_dataset(encapsulated_pdf_dataset)
        session.add_finding(pdf)
        
        # Exclude
        session.set_pdf_excluded(pdf.sop_instance_uid, True)
        assert pdf.excluded is True
        
        # Re-include
        session.set_pdf_excluded(pdf.sop_instance_uid, False)
        assert pdf.excluded is False
        
        # Seal
        session.start_review()
        session.accept()
        
        # Now changes should be blocked
        result = session.set_pdf_excluded(pdf.sop_instance_uid, True)
        assert result is False
        assert pdf.excluded is False  # Still included


# ═══════════════════════════════════════════════════════════════════════════════
# DETERMINISTIC FILE UID MAPPING TESTS
# Phase 2 Hardening: Reliable filename ↔ SOPInstanceUID resolution
# ═══════════════════════════════════════════════════════════════════════════════

class TestFileUIDMapping:
    """Tests for deterministic file-to-UID mapping."""
    
    def test_register_file_uid(self):
        """Should register filename to UID mapping."""
        session = ReviewSession.create(sop_instance_uid="1.2.3.4.5")
        
        session.register_file_uid(
            filename="test.dcm",
            sop_instance_uid="1.2.840.999.1",
            sop_class_uid="1.2.840.10008.5.1.4.1.1.1"  # CT
        )
        
        assert session.has_file_uid_mapping()
        assert session.get_sop_uid_for_file("test.dcm") == "1.2.840.999.1"
    
    def test_get_sop_uid_for_unknown_file(self):
        """Should return None for unknown filename."""
        session = ReviewSession.create(sop_instance_uid="1.2.3.4.5")
        
        result = session.get_sop_uid_for_file("unknown.dcm")
        
        assert result is None
    
    def test_get_excluded_filenames_empty_when_no_exclusions(self, encapsulated_pdf_dataset):
        """Should return empty list when no PDFs are excluded."""
        session = ReviewSession.create(sop_instance_uid="1.2.3.4.5")
        finding = preflight_scan_dataset(encapsulated_pdf_dataset)
        session.add_finding(finding)
        session.register_file_uid(
            filename="pdf.dcm",
            sop_instance_uid=finding.sop_instance_uid,
            sop_class_uid=SOP_CLASS_UIDS["ENCAPSULATED_PDF"]
        )
        
        # Not excluded yet
        excluded = session.get_excluded_filenames()
        
        assert excluded == []
    
    def test_get_excluded_filenames_returns_correct_file(self, encapsulated_pdf_dataset):
        """Should return correct filename when PDF is excluded."""
        session = ReviewSession.create(sop_instance_uid="1.2.3.4.5")
        finding = preflight_scan_dataset(encapsulated_pdf_dataset)
        session.add_finding(finding)
        session.register_file_uid(
            filename="report.dcm",
            sop_instance_uid=finding.sop_instance_uid,
            sop_class_uid=SOP_CLASS_UIDS["ENCAPSULATED_PDF"]
        )
        
        # Exclude the PDF
        session.set_pdf_excluded(finding.sop_instance_uid, True)
        excluded = session.get_excluded_filenames()
        
        assert excluded == ["report.dcm"]
    
    def test_cannot_exclude_non_pdf_via_mapping(self, secondary_capture_dataset):
        """Non-PDF files should NEVER appear in excluded filenames."""
        session = ReviewSession.create(sop_instance_uid="1.2.3.4.5")
        sc_finding = preflight_scan_dataset(secondary_capture_dataset)
        session.add_finding(sc_finding)
        
        # Register SC file
        session.register_file_uid(
            filename="secondary.dcm",
            sop_instance_uid=sc_finding.sop_instance_uid,
            sop_class_uid=SOP_CLASS_UIDS["SECONDARY_CAPTURE"]  # NOT PDF
        )
        
        # Try to exclude SC (should fail)
        result = session.set_pdf_excluded(sc_finding.sop_instance_uid, True)
        assert result is False
        
        # Verify SC does NOT appear in excluded filenames
        excluded = session.get_excluded_filenames()
        assert excluded == []
        assert "secondary.dcm" not in excluded
    
    def test_mapping_stable_across_operations(self, encapsulated_pdf_dataset):
        """Mapping should remain stable across session operations."""
        session = ReviewSession.create(sop_instance_uid="1.2.3.4.5")
        finding = preflight_scan_dataset(encapsulated_pdf_dataset)
        session.add_finding(finding)
        session.register_file_uid(
            filename="stable.dcm",
            sop_instance_uid=finding.sop_instance_uid,
            sop_class_uid=SOP_CLASS_UIDS["ENCAPSULATED_PDF"]
        )
        
        # Toggle exclusion multiple times
        session.set_pdf_excluded(finding.sop_instance_uid, True)
        assert session.get_excluded_filenames() == ["stable.dcm"]
        
        session.set_pdf_excluded(finding.sop_instance_uid, False)
        assert session.get_excluded_filenames() == []
        
        session.set_pdf_excluded(finding.sop_instance_uid, True)
        assert session.get_excluded_filenames() == ["stable.dcm"]
        
        # Add regions and start review
        session.add_ocr_region(x=10, y=20, w=100, h=50)
        session.start_review()
        
        # Mapping still works
        assert session.get_excluded_filenames() == ["stable.dcm"]
    
    def test_only_pdf_with_matching_sop_class_excluded(self):
        """Only files with PDF SOP Class should be excluded."""
        session = ReviewSession.create(sop_instance_uid="1.2.3.4.5")
        
        # Create PDF finding
        ds = Dataset()
        ds.SOPClassUID = SOP_CLASS_UIDS["ENCAPSULATED_PDF"]
        ds.SOPInstanceUID = "1.2.3.999.PDF"
        ds.SeriesInstanceUID = "1.2.3.999"
        ds.Modality = "DOC"
        pdf_finding = preflight_scan_dataset(ds)
        session.add_finding(pdf_finding)
        
        # Register two files - one PDF, one NOT
        session.register_file_uid(
            filename="real_pdf.dcm",
            sop_instance_uid="1.2.3.999.PDF",
            sop_class_uid=SOP_CLASS_UIDS["ENCAPSULATED_PDF"]
        )
        session.register_file_uid(
            filename="not_pdf.dcm",
            sop_instance_uid="1.2.3.999.PDF",  # Same UID but wrong SOP Class!
            sop_class_uid="1.2.840.10008.5.1.4.1.1.1"  # CT
        )
        
        # Exclude the PDF UID
        session.set_pdf_excluded("1.2.3.999.PDF", True)
        excluded = session.get_excluded_filenames()
        
        # Only the file with PDF SOP Class should be excluded
        assert "real_pdf.dcm" in excluded
        assert "not_pdf.dcm" not in excluded
    
    def test_multiple_pdfs_independent_exclusion(self):
        """Multiple PDFs can be excluded independently."""
        session = ReviewSession.create(sop_instance_uid="1.2.3.4.5")
        
        # Create two PDF findings
        ds1 = Dataset()
        ds1.SOPClassUID = SOP_CLASS_UIDS["ENCAPSULATED_PDF"]
        ds1.SOPInstanceUID = "1.2.3.PDF1"
        ds1.SeriesInstanceUID = "1.2.3"
        ds1.Modality = "DOC"
        
        ds2 = Dataset()
        ds2.SOPClassUID = SOP_CLASS_UIDS["ENCAPSULATED_PDF"]
        ds2.SOPInstanceUID = "1.2.3.PDF2"
        ds2.SeriesInstanceUID = "1.2.3"
        ds2.Modality = "DOC"
        
        session.add_finding(preflight_scan_dataset(ds1))
        session.add_finding(preflight_scan_dataset(ds2))
        
        session.register_file_uid("pdf1.dcm", "1.2.3.PDF1", SOP_CLASS_UIDS["ENCAPSULATED_PDF"])
        session.register_file_uid("pdf2.dcm", "1.2.3.PDF2", SOP_CLASS_UIDS["ENCAPSULATED_PDF"])
        
        # Exclude only first PDF
        session.set_pdf_excluded("1.2.3.PDF1", True)
        
        excluded = session.get_excluded_filenames()
        assert "pdf1.dcm" in excluded
        assert "pdf2.dcm" not in excluded
        assert len(excluded) == 1


class TestMappingStabilityAcrossReruns:
    """
    Tests to verify mapping remains stable across simulated Streamlit reruns.
    This is critical for UI reliability.
    """
    
    def test_mapping_survives_session_object_reuse(self, encapsulated_pdf_dataset):
        """Mapping should persist in session object across operations."""
        # Simulates a Streamlit session_state scenario
        session = ReviewSession.create(sop_instance_uid="1.2.3.4.5")
        
        # First "run" - register mapping
        finding = preflight_scan_dataset(encapsulated_pdf_dataset)
        session.add_finding(finding)
        session.register_file_uid(
            "persistent.dcm",
            finding.sop_instance_uid,
            SOP_CLASS_UIDS["ENCAPSULATED_PDF"]
        )
        
        # "Rerun 1" - check mapping still there
        assert session.has_file_uid_mapping()
        assert session.get_sop_uid_for_file("persistent.dcm") == finding.sop_instance_uid
        
        # "Rerun 2" - exclude and verify
        session.set_pdf_excluded(finding.sop_instance_uid, True)
        assert session.get_excluded_filenames() == ["persistent.dcm"]
        
        # "Rerun 3" - still correct
        assert session.get_excluded_filenames() == ["persistent.dcm"]
    
    def test_new_session_has_empty_mapping(self):
        """New session should have no file mappings."""
        session = ReviewSession.create(sop_instance_uid="1.2.3.4.5")
        
        assert not session.has_file_uid_mapping()
        assert session.get_excluded_filenames() == []


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
