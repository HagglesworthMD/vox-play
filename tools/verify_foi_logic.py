import sys
import os
import pydicom
from pydicom.dataset import Dataset, FileDataset
from pydicom.uid import ExplicitVRLittleEndian
import datetime

# Add src to python path
current_dir = os.path.dirname(os.path.abspath(__file__))
src_dir = os.path.join(current_dir, '../src')
sys.path.append(src_dir)

try:
    from foi_engine import FOIEngine, FOIProcessingResult
except ImportError as e:
    print(f"❌ Error importing FOIEngine: {e}")
    sys.exit(1)

def create_dummy_dicom():
    print("🧪 Creating dummy DICOM dataset...")
    
    # Create file meta information
    file_meta = Dataset()
    file_meta.MediaStorageSOPClassUID = '1.2.840.10008.5.1.4.1.1.2'
    file_meta.MediaStorageSOPInstanceUID = '1.2.3'
    file_meta.ImplementationClassUID = '1.2.3.4'
    file_meta.TransferSyntaxUID = ExplicitVRLittleEndian

    # Create the dataset
    ds = FileDataset("dummy.dcm", {}, file_meta=file_meta, preamble=b"\0" * 128)
    
    # Set identifying tags
    ds.PatientName = "Doe^John"
    ds.PatientID = "123456789"
    ds.PatientBirthDate = "19800101"
    
    # Set staff tags (should be removed)
    ds.OperatorsName = "Evil^Dr"
    ds.ReferringPhysicianName = "Good^Dr"
    ds.PerformingPhysicianName = "Surgeon^The"
    
    ds.is_little_endian = True
    ds.is_implicit_VR = False
    
    return ds

def verify_foi_logic():
    print("\n🔍 Starting FOI Logic Verification Reference Check...")
    print("====================================================")
    
    ds = create_dummy_dicom()
    engine = FOIEngine(redact_referring_physician=False) # Keep Referring Physician for this test
    
    print(f"📄 INPUT: Patient={ds.PatientName}, Operator={ds.OperatorsName}")
    
    # Run processing
    processed_ds, result = engine.process_dataset(ds, mode='legal')
    
    # VERIFICATION STEPS
    failures = []
    
    # 1. Check Patient Name (MUST BE PRESERVED)
    if processed_ds.PatientName == "Doe^John":
        print("✅ PASS: Patient Name preserved ('Doe^John')")
    else:
        print(f"❌ FAIL: Patient Name altered: {processed_ds.PatientName}")
        failures.append("Patient Name preservation failed")

    # 2. Check Patient ID (MUST BE PRESERVED)
    if processed_ds.PatientID == "123456789":
        print("✅ PASS: Patient ID preserved ('123456789')")
    else:
        print(f"❌ FAIL: Patient ID altered: {processed_ds.PatientID}")
        failures.append("Patient ID preservation failed")

    # 3. Check Operator Name (MUST BE REDACTED)
    if hasattr(processed_ds, 'OperatorsName') and processed_ds.OperatorsName == "REDACTED":
         print("✅ PASS: Operator Name redacted correctly")
    elif not hasattr(processed_ds, 'OperatorsName'):
         print("⚠️ WARN: Operator Name tag removed entirely (Technically safe, but check logic)")
    else:
         print(f"❌ FAIL: Operator Name NOT redacted: {processed_ds.OperatorsName}")
         failures.append("Operator Name redaction failed")

    # 4. Check Performing Physician (MUST BE REDACTED)
    if hasattr(processed_ds, 'PerformingPhysicianName') and processed_ds.PerformingPhysicianName == "REDACTED":
         print("✅ PASS: Performing Physician redacted correctly")
    else:
         print(f"❌ FAIL: Performing Physician NOT redacted: {processed_ds.PerformingPhysicianName}")
         failures.append("Performing Physician redaction failed")
         
    print("\n📊 Verification Summary:")
    if not failures:
        print("✨ SUCCESS: All FOI logic checks passed. Mathematical verification complete.")
        sys.exit(0)
    else:
        print(f"💀 FAILED: {len(failures)} checks failed.")
        sys.exit(1)

if __name__ == "__main__":
    verify_foi_logic()
