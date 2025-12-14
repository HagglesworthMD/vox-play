"""
Unit tests for src/run_on_dicom.process_dataset()

This tests the thin, test-friendly seam that:
1. Calls anonymize_metadata()
2. Short-circuits if no PixelData
3. Returns the mutated dataset

Does NOT test: process_dicom(), OCR, OpenCV, file I/O
"""
import sys
from unittest.mock import MagicMock, patch

import numpy as np
import pydicom
import pytest


# ============================================================================
# FIXTURES
# ============================================================================

def make_minimal_ds(with_pixels=False):
    """
    Create a minimal pydicom Dataset for testing.
    
    Args:
        with_pixels: If True, add minimal PixelData
    """
    ds = pydicom.Dataset()
    ds.PatientName = "TEST^PATIENT"
    ds.PatientID = "123"
    ds.StudyInstanceUID = "1.2.3.4.5"
    ds.SeriesInstanceUID = "1.2.3.4.6"
    ds.SOPInstanceUID = "1.2.3.4.7"
    ds.StudyDate = "20231201"
    ds.Modality = "US"

    if with_pixels:
        ds.Rows = 2
        ds.Columns = 2
        ds.SamplesPerPixel = 1
        ds.PhotometricInterpretation = "MONOCHROME2"
        ds.BitsAllocated = 8
        ds.BitsStored = 8
        ds.HighBit = 7
        ds.PixelRepresentation = 0
        ds.PixelData = b"\x00\x01\x02\x03"

    return ds


@pytest.fixture
def mock_dependencies():
    """
    Mock the problematic imports in run_on_dicom to allow importing the module.
    
    run_on_dicom.py imports:
    - clinical_corrector.ClinicalCorrector (not src.clinical_corrector)
    - compliance.enforce_dicom_compliance
    - utils.apply_deterministic_sanitization
    
    We mock these at the sys.modules level before importing.
    """
    # Create mock modules
    mock_clinical_corrector = MagicMock()
    mock_compliance = MagicMock()
    mock_utils = MagicMock()
    
    # Mock the functions/classes that will be used
    mock_clinical_corrector.ClinicalCorrector = MagicMock()
    mock_compliance.enforce_dicom_compliance = MagicMock(side_effect=lambda ds, *a, **k: ds)
    mock_utils.apply_deterministic_sanitization = MagicMock()
    
    # Inject into sys.modules
    original_modules = {}
    for name, mock in [
        ('clinical_corrector', mock_clinical_corrector),
        ('compliance', mock_compliance),
        ('utils', mock_utils),
    ]:
        if name in sys.modules:
            original_modules[name] = sys.modules[name]
        sys.modules[name] = mock
    
    yield {
        'clinical_corrector': mock_clinical_corrector,
        'compliance': mock_compliance,
        'utils': mock_utils,
    }
    
    # Restore original modules
    for name in ['clinical_corrector', 'compliance', 'utils']:
        if name in original_modules:
            sys.modules[name] = original_modules[name]
        elif name in sys.modules:
            del sys.modules[name]


# ============================================================================
# TESTS: process_dataset()
# ============================================================================

class TestProcessDataset:
    """Tests for the process_dataset() function."""
    
    def test_calls_anonymize_metadata(self, mock_dependencies):
        """anonymize_metadata() should always be called."""
        # Import after mocking dependencies
        import importlib
        if 'src.run_on_dicom' in sys.modules:
            del sys.modules['src.run_on_dicom']
        
        import src.run_on_dicom as rod
        
        calls = {}
        
        def fake_anonymize(ds, new_name, research_context=None, clinical_context=None):
            calls["called"] = True
            calls["new_name"] = new_name
            return ds
        
        # Patch anonymize_metadata on the module
        original_fn = rod.anonymize_metadata
        rod.anonymize_metadata = fake_anonymize
        
        try:
            ds = make_minimal_ds()
            out = rod.process_dataset(
                ds,
                old_name_text="OLD",
                new_name_text="NEW",
            )
            
            assert calls.get("called") is True
            assert calls.get("new_name") == "NEW"
            assert out is ds
        finally:
            rod.anonymize_metadata = original_fn
    
    def test_no_pixeldata_returns_dataset(self, mock_dependencies):
        """When no PixelData, should return dataset immediately after metadata."""
        import importlib
        if 'src.run_on_dicom' in sys.modules:
            del sys.modules['src.run_on_dicom']
        
        import src.run_on_dicom as rod
        
        # Stub anonymize_metadata to do nothing
        original_fn = rod.anonymize_metadata
        rod.anonymize_metadata = lambda ds, *a, **k: ds
        
        try:
            ds = make_minimal_ds(with_pixels=False)
            
            out = rod.process_dataset(
                ds,
                old_name_text="OLD",
                new_name_text="NEW",
            )
            
            assert out is ds
            assert not hasattr(out, "PixelData") or out.PixelData is None
        finally:
            rod.anonymize_metadata = original_fn
    
    def test_with_pixeldata_returns_dataset(self, mock_dependencies):
        """When PixelData present, should still return the dataset."""
        import importlib
        if 'src.run_on_dicom' in sys.modules:
            del sys.modules['src.run_on_dicom']
        
        import src.run_on_dicom as rod
        
        original_fn = rod.anonymize_metadata
        rod.anonymize_metadata = lambda ds, *a, **k: ds
        
        try:
            ds = make_minimal_ds(with_pixels=True)
            
            out = rod.process_dataset(
                ds,
                old_name_text="OLD",
                new_name_text="NEW",
            )
            
            assert out is ds
            assert out.PixelData is not None
        finally:
            rod.anonymize_metadata = original_fn
    
    def test_passes_research_context(self, mock_dependencies):
        """research_context should be forwarded to anonymize_metadata."""
        import importlib
        if 'src.run_on_dicom' in sys.modules:
            del sys.modules['src.run_on_dicom']
        
        import src.run_on_dicom as rod
        
        seen = {}
        
        def fake_anonymize(ds, new_name, research_context=None, clinical_context=None):
            seen["research_context"] = research_context
            seen["clinical_context"] = clinical_context
            return ds
        
        original_fn = rod.anonymize_metadata
        rod.anonymize_metadata = fake_anonymize
        
        try:
            rod.process_dataset(
                make_minimal_ds(),
                old_name_text="OLD",
                new_name_text="NEW",
                research_context={"study_id": "TRIAL_001", "subject_id": "SUB_001"},
            )
            
            assert seen.get("research_context") is not None
            assert seen["research_context"]["study_id"] == "TRIAL_001"
        finally:
            rod.anonymize_metadata = original_fn
    
    def test_passes_clinical_context(self, mock_dependencies):
        """clinical_context should be forwarded to anonymize_metadata."""
        import importlib
        if 'src.run_on_dicom' in sys.modules:
            del sys.modules['src.run_on_dicom']
        
        import src.run_on_dicom as rod
        
        seen = {}
        
        def fake_anonymize(ds, new_name, research_context=None, clinical_context=None):
            seen["research_context"] = research_context
            seen["clinical_context"] = clinical_context
            return ds
        
        original_fn = rod.anonymize_metadata
        rod.anonymize_metadata = fake_anonymize
        
        try:
            rod.process_dataset(
                make_minimal_ds(),
                old_name_text="OLD",
                new_name_text="NEW",
                clinical_context={"patient_name": "JONES^MARY", "study_date": "2024-01-15"},
            )
            
            assert seen.get("clinical_context") is not None
            assert seen["clinical_context"]["patient_name"] == "JONES^MARY"
        finally:
            rod.anonymize_metadata = original_fn
    
    def test_passes_both_contexts(self, mock_dependencies):
        """Both contexts should be forwarded when provided."""
        import importlib
        if 'src.run_on_dicom' in sys.modules:
            del sys.modules['src.run_on_dicom']
        
        import src.run_on_dicom as rod
        
        seen = {}
        
        def fake_anonymize(ds, new_name, research_context=None, clinical_context=None):
            seen["research_context"] = research_context
            seen["clinical_context"] = clinical_context
            return ds
        
        original_fn = rod.anonymize_metadata
        rod.anonymize_metadata = fake_anonymize
        
        try:
            rod.process_dataset(
                make_minimal_ds(),
                old_name_text="OLD",
                new_name_text="NEW",
                research_context={"mode": "research"},
                clinical_context={"mode": "clinical"},
            )
            
            assert "research_context" in seen
            assert "clinical_context" in seen
            assert seen["research_context"]["mode"] == "research"
            assert seen["clinical_context"]["mode"] == "clinical"
        finally:
            rod.anonymize_metadata = original_fn
    
    def test_returns_same_dataset_object(self, mock_dependencies):
        """Should return the exact same dataset object (mutated in-place)."""
        import importlib
        if 'src.run_on_dicom' in sys.modules:
            del sys.modules['src.run_on_dicom']
        
        import src.run_on_dicom as rod
        
        original_fn = rod.anonymize_metadata
        rod.anonymize_metadata = lambda ds, *a, **k: ds
        
        try:
            ds = make_minimal_ds()
            original_id = id(ds)
            
            out = rod.process_dataset(
                ds,
                old_name_text="OLD",
                new_name_text="NEW",
            )
            
            assert id(out) == original_id
        finally:
            rod.anonymize_metadata = original_fn
    
    def test_pixeldata_none_treated_as_missing(self, mock_dependencies):
        """PixelData=None should be treated the same as missing PixelData."""
        import importlib
        if 'src.run_on_dicom' in sys.modules:
            del sys.modules['src.run_on_dicom']
        
        import src.run_on_dicom as rod
        
        original_fn = rod.anonymize_metadata
        rod.anonymize_metadata = lambda ds, *a, **k: ds
        
        try:
            ds = make_minimal_ds(with_pixels=False)
            ds.PixelData = None  # Explicitly set to None
            
            out = rod.process_dataset(
                ds,
                old_name_text="OLD",
                new_name_text="NEW",
            )
            
            # Should return without error
            assert out is ds
        finally:
            rod.anonymize_metadata = original_fn
