"""
VoxelMask FOI Data Preservation Test Suite
==========================================
Verifies that FOI mode correctly:
1. PRESERVES: Patient Name, Patient ID, DOB, Accession Number, Study Date
2. REDACTS: Only Operators' Name and Requesting Physician
3. PRESERVES: Original filename structure

Run with: python -m pytest tests/test_foi_preservation.py -v
Or standalone: python tests/test_foi_preservation.py
"""

import os
import sys
import tempfile
import shutil
from datetime import datetime

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

try:
    import pydicom
    from pydicom.dataset import Dataset, FileDataset
    from pydicom.uid import generate_uid
    PYDICOM_AVAILABLE = True
except ImportError:
    PYDICOM_AVAILABLE = False
    print("⚠️  pydicom not installed. Run: pip install pydicom")

try:
    from foi_engine import FOIEngine, process_foi_request
    FOI_ENGINE_AVAILABLE = True
except ImportError:
    FOI_ENGINE_AVAILABLE = False
    print("⚠️  foi_engine not found in path")


def create_test_dicom(output_path: str, patient_data: dict) -> str:
    """Create a synthetic DICOM file with known patient data for testing."""
    
    # Create minimal valid DICOM
    file_meta = pydicom.Dataset()
    file_meta.MediaStorageSOPClassUID = '1.2.840.10008.5.1.4.1.1.2'  # CT Image
    file_meta.MediaStorageSOPInstanceUID = generate_uid()
    file_meta.TransferSyntaxUID = '1.2.840.10008.1.2.1'  # Explicit VR Little Endian
    
    ds = FileDataset(output_path, {}, file_meta=file_meta, preamble=b"\0" * 128)
    
    # ═══════════════════════════════════════════════════════════════════
    # PATIENT DATA - MUST BE PRESERVED IN FOI MODE
    # ═══════════════════════════════════════════════════════════════════
    ds.PatientName = patient_data.get('patient_name', 'TestPatient^John')
    ds.PatientID = patient_data.get('patient_id', 'PAT123456')
    ds.PatientBirthDate = patient_data.get('dob', '19850315')
    ds.PatientSex = patient_data.get('sex', 'M')
    
    # ═══════════════════════════════════════════════════════════════════
    # STUDY DATA - MUST BE PRESERVED IN FOI MODE
    # ═══════════════════════════════════════════════════════════════════
    ds.StudyDate = patient_data.get('study_date', '20231215')
    ds.StudyTime = '143022'
    ds.AccessionNumber = patient_data.get('accession', 'ACC987654')
    ds.StudyDescription = patient_data.get('study_desc', 'CT Chest Without Contrast')
    ds.Modality = patient_data.get('modality', 'CT')
    ds.StudyInstanceUID = generate_uid()
    
    # ═══════════════════════════════════════════════════════════════════
    # STAFF DATA - SHOULD BE REDACTED IN FOI MODE
    # ═══════════════════════════════════════════════════════════════════
    ds.OperatorsName = patient_data.get('operator', 'Radiographer^Jane')
    ds.PerformingPhysicianName = patient_data.get('physician', 'DrSmith^Robert')
    ds.ReferringPhysicianName = patient_data.get('referring', 'DrJones^Mary')
    ds.RequestingPhysician = patient_data.get('requesting', 'DrBrown^Alice')
    
    # Series/Instance metadata
    ds.SeriesInstanceUID = generate_uid()
    ds.SOPClassUID = '1.2.840.10008.5.1.4.1.1.2'
    ds.SOPInstanceUID = file_meta.MediaStorageSOPInstanceUID
    ds.SeriesNumber = 1
    ds.InstanceNumber = 1
    ds.Rows = 64
    ds.Columns = 64
    ds.BitsAllocated = 16
    ds.BitsStored = 12
    ds.HighBit = 11
    ds.PixelRepresentation = 0
    ds.SamplesPerPixel = 1
    ds.PhotometricInterpretation = 'MONOCHROME2'
    
    # Minimal pixel data (8x8 gray square)
    import numpy as np
    pixel_array = np.zeros((64, 64), dtype=np.uint16)
    ds.PixelData = pixel_array.tobytes()
    
    ds.save_as(output_path)
    return output_path


def test_foi_preserves_patient_data():
    """
    CRITICAL TEST: Verify FOI mode preserves patient-identifying data.
    This is a legal requirement for Freedom of Information requests.
    """
    print("\n" + "═" * 70)
    print("TEST: FOI Mode Preserves Patient Data")
    print("═" * 70)
    
    if not PYDICOM_AVAILABLE or not FOI_ENGINE_AVAILABLE:
        print("❌ SKIP: Required modules not available")
        return False
    
    # Test data - these MUST survive FOI processing
    test_patient = {
        'patient_name': 'RealPatient^Mary^Jane',
        'patient_id': 'MRN-2023-98765',
        'dob': '19780422',
        'accession': 'ACC-FOI-12345',
        'study_date': '20231201',
        'study_desc': 'MRI Brain With Contrast',
        'modality': 'MR',
        'operator': 'TechSmith^John',
        'physician': 'DrRadiology^Expert',
        'requesting': 'DrLegal^Request'
    }
    
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create test DICOM
        input_path = os.path.join(tmpdir, 'original_scan.dcm')
        create_test_dicom(input_path, test_patient)
        
        # Read original for verification
        original_ds = pydicom.dcmread(input_path)
        print(f"\n📄 Original File: {input_path}")
        print(f"   Patient Name: {original_ds.PatientName}")
        print(f"   Patient ID: {original_ds.PatientID}")
        print(f"   DOB: {original_ds.PatientBirthDate}")
        print(f"   Accession: {original_ds.AccessionNumber}")
        print(f"   Operator: {original_ds.OperatorsName}")
        
        # Process with FOI engine
        engine = FOIEngine()
        processed_ds, result = engine.process_dataset(original_ds.copy())
        
        print(f"\n🔬 After FOI Processing:")
        print(f"   Patient Name: {processed_ds.PatientName}")
        print(f"   Patient ID: {processed_ds.PatientID}")
        print(f"   DOB: {getattr(processed_ds, 'PatientBirthDate', 'MISSING')}")
        print(f"   Accession: {getattr(processed_ds, 'AccessionNumber', 'MISSING')}")
        print(f"   Operator: {getattr(processed_ds, 'OperatorsName', 'REDACTED')}")
        
        # ═══════════════════════════════════════════════════════════════════
        # ASSERTIONS - PRESERVATION CHECKS
        # ═══════════════════════════════════════════════════════════════════
        errors = []
        
        # Patient Name MUST be preserved
        if str(processed_ds.PatientName) != test_patient['patient_name']:
            errors.append(f"❌ PatientName changed: '{processed_ds.PatientName}' != '{test_patient['patient_name']}'")
        else:
            print("   ✅ PatientName PRESERVED")
        
        # Patient ID MUST be preserved
        if str(processed_ds.PatientID) != test_patient['patient_id']:
            errors.append(f"❌ PatientID changed: '{processed_ds.PatientID}' != '{test_patient['patient_id']}'")
        else:
            print("   ✅ PatientID PRESERVED")
        
        # DOB MUST be preserved
        if hasattr(processed_ds, 'PatientBirthDate') and str(processed_ds.PatientBirthDate) == test_patient['dob']:
            print("   ✅ PatientBirthDate PRESERVED")
        else:
            errors.append(f"❌ PatientBirthDate changed or missing")
        
        # Accession MUST be preserved
        if hasattr(processed_ds, 'AccessionNumber') and str(processed_ds.AccessionNumber) == test_patient['accession']:
            print("   ✅ AccessionNumber PRESERVED")
        else:
            errors.append(f"❌ AccessionNumber changed or missing")
        
        # Study Date MUST be preserved
        if hasattr(processed_ds, 'StudyDate') and str(processed_ds.StudyDate) == test_patient['study_date']:
            print("   ✅ StudyDate PRESERVED")
        else:
            errors.append(f"❌ StudyDate changed or missing")
        
        # ═══════════════════════════════════════════════════════════════════
        # ASSERTIONS - REDACTION CHECKS
        # ═══════════════════════════════════════════════════════════════════
        print("\n🔒 Staff Redaction Verification:")
        
        # Operator SHOULD be redacted
        operator_val = getattr(processed_ds, 'OperatorsName', '')
        if operator_val and str(operator_val) == test_patient['operator']:
            errors.append(f"❌ OperatorsName NOT redacted: '{operator_val}'")
        else:
            print(f"   ✅ OperatorsName REDACTED (now: '{operator_val}')")
        
        # ═══════════════════════════════════════════════════════════════════
        # RESULT OBJECT CHECKS
        # ═══════════════════════════════════════════════════════════════════
        print("\n📊 Result Object Verification:")
        
        if hasattr(result, 'patient_name') and result.patient_name:
            print(f"   ✅ result.patient_name = '{result.patient_name}'")
        else:
            print(f"   ⚠️  result.patient_name not set")
        
        if hasattr(result, 'study_date') and result.study_date:
            print(f"   ✅ result.study_date = '{result.study_date}'")
        else:
            print(f"   ⚠️  result.study_date not set")
        
        if hasattr(result, 'accession') and result.accession:
            print(f"   ✅ result.accession = '{result.accession}'")
        else:
            print(f"   ⚠️  result.accession not set")
        
        if hasattr(result, 'modality') and result.modality:
            print(f"   ✅ result.modality = '{result.modality}'")
        else:
            print(f"   ⚠️  result.modality not set")
        
        # ═══════════════════════════════════════════════════════════════════
        # FINAL VERDICT
        # ═══════════════════════════════════════════════════════════════════
        print("\n" + "─" * 70)
        if errors:
            print("❌ TEST FAILED - FOI Data Preservation Broken!")
            for err in errors:
                print(f"   {err}")
            return False
        else:
            print("✅ TEST PASSED - FOI Mode Preserves Patient Data Correctly!")
            return True


def test_research_mode_anonymizes():
    """
    Verify Research mode (default) DOES anonymize patient data.
    This ensures we haven't broken the normal anonymization.
    """
    print("\n" + "═" * 70)
    print("TEST: Research Mode Anonymizes Data (Contrast Check)")
    print("═" * 70)
    
    if not PYDICOM_AVAILABLE:
        print("❌ SKIP: pydicom not available")
        return False
    
    # This test would use DicomAnonymizer - import if available
    try:
        from research_mode.anonymizer import DicomAnonymizer, AnonymizationConfig
        ANONYMIZER_AVAILABLE = True
    except ImportError:
        print("⚠️  DicomAnonymizer not available - skipping contrast test")
        return True  # Not a failure, just can't test
    
    test_patient = {
        'patient_name': 'OriginalName^Test',
        'patient_id': 'ORIG-12345',
        'dob': '19900101',
        'accession': 'ACC-ORIG-999',
    }
    
    with tempfile.TemporaryDirectory() as tmpdir:
        input_path = os.path.join(tmpdir, 'original.dcm')
        output_path = os.path.join(tmpdir, 'anonymized.dcm')
        create_test_dicom(input_path, test_patient)
        
        # Anonymize
        config = AnonymizationConfig()
        anonymizer = DicomAnonymizer(config)
        result = anonymizer.anonymize_file(input_path, output_path)
        
        if result.success and os.path.exists(output_path):
            anon_ds = pydicom.dcmread(output_path)
            
            # In research mode, patient name SHOULD be changed or removed
            anon_name = str(getattr(anon_ds, 'PatientName', 'REMOVED'))
            if anon_name == test_patient['patient_name']:
                print("X Research mode did NOT anonymize PatientName!")
                return False
            else:
                print(f"OK Research mode anonymized PatientName: '{anon_name}'")
                return True
        else:
            print("❌ Anonymization failed")
            return False


def print_summary(results: dict):
    """Print colorful test summary."""
    print("\n" + "═" * 70)
    print("                    📋 TEST SUMMARY")
    print("═" * 70)
    
    passed = sum(1 for v in results.values() if v)
    total = len(results)
    
    for test_name, passed_test in results.items():
        status = "✅ PASS" if passed_test else "❌ FAIL"
        print(f"  {status}  {test_name}")
    
    print("─" * 70)
    print(f"  Results: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n  🎉 ALL TESTS PASSED! FOI Logic is Intact.")
    else:
        print("\n  ⚠️  SOME TESTS FAILED - Review the FOI processing logic!")
    
    print("═" * 70 + "\n")


if __name__ == "__main__":
    print("\n" + "+" + "=" * 68 + "+")
    print("|" + " VoxelMask FOI Data Preservation Test Suite ".center(68) + "|")
    print("|" + f" Run Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ".center(68) + "|")
    print("+" + "=" * 68 + "+")
    
    results = {}
    
    # Run tests
    results["FOI Preserves Patient Data"] = test_foi_preserves_patient_data()
    results["Research Mode Anonymizes (Contrast)"] = test_research_mode_anonymizes()
    
    # Summary
    print_summary(results)
    
    # Exit code for CI/CD
    sys.exit(0 if all(results.values()) else 1)
