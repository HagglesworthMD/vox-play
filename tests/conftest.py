"""
Pytest configuration and fixtures for VoxelMask tests.
"""
import tempfile
import os
import zipfile

import pytest
import pydicom
from pydicom.dataset import Dataset, FileDataset
from pydicom.uid import ExplicitVRLittleEndian
import numpy as np


def create_dummy_dicom(filepath: str, patient_name: str = "Test^Patient", 
                       patient_id: str = "TEST001", study_date: str = "20231201",
                       modality: str = "CT") -> str:
    """
    Helper function to create a dummy DICOM file with customizable metadata.
    
    Args:
        filepath: Path where the DICOM file should be saved
        patient_name: Patient name to use
        patient_id: Patient ID to use
        study_date: Study date in YYYYMMDD format
        modality: DICOM modality (CT, MR, US, etc.)
        
    Returns:
        str: Path to the created DICOM file
    """
    # Create a minimal DICOM dataset
    file_meta = pydicom.Dataset()
    file_meta.MediaStorageSOPClassUID = pydicom.uid.CTImageStorage
    file_meta.MediaStorageSOPInstanceUID = pydicom.uid.generate_uid()
    file_meta.TransferSyntaxUID = ExplicitVRLittleEndian
    
    # Create the FileDataset
    ds = FileDataset(
        filepath,
        {},
        file_meta=file_meta,
        preamble=b"\0" * 128
    )
    
    # Add required DICOM attributes
    ds.PatientName = patient_name
    ds.PatientID = patient_id
    ds.StudyInstanceUID = pydicom.uid.generate_uid()
    ds.SeriesInstanceUID = pydicom.uid.generate_uid()
    ds.SOPInstanceUID = file_meta.MediaStorageSOPInstanceUID
    ds.SOPClassUID = file_meta.MediaStorageSOPClassUID
    ds.Modality = modality
    ds.StudyDate = study_date
    ds.SeriesDate = study_date
    ds.StudyDescription = "Test Study"
    ds.SeriesDescription = "Test Series"
    
    # Add image-related attributes
    ds.Rows = 64
    ds.Columns = 64
    ds.BitsAllocated = 16
    ds.BitsStored = 12
    ds.HighBit = 11
    ds.PixelRepresentation = 0
    ds.SamplesPerPixel = 1
    ds.PhotometricInterpretation = "MONOCHROME2"
    
    # Create dummy pixel data (64x64 grayscale image)
    pixel_array = np.zeros((64, 64), dtype=np.uint16)
    # Add some variation to make it more realistic
    pixel_array[16:48, 16:48] = 1000
    ds.PixelData = pixel_array.tobytes()
    
    # Save the DICOM file
    ds.save_as(filepath, write_like_original=False)
    
    return filepath


@pytest.fixture
def dummy_dicom_file():
    """
    Creates a temporary dummy DICOM file for testing purposes.
    
    Yields:
        str: Path to the temporary DICOM file.
        
    The file is automatically cleaned up after the test completes.
    """
    # Create a temporary directory for the DICOM file
    with tempfile.TemporaryDirectory() as tmpdir:
        filepath = os.path.join(tmpdir, "test_image.dcm")
        create_dummy_dicom(filepath)
        yield filepath


@pytest.fixture
def nested_zip_structure():
    """
    Creates a temporary ZIP file with nested folder structure for testing.
    
    Structure:
        archive.zip/
        ├── folder_a/
        │   └── image1.dcm
        ├── folder_b/
        │   └── subfolder/
        │       └── image2.dcm
        └── random_file.txt
    
    Yields:
        dict: Contains:
            - 'zip_path': Path to the ZIP file
            - 'temp_dir': Path to the temp directory (for extraction)
            - 'expected_dicoms': List of expected DICOM file paths within ZIP
            - 'expected_non_dicoms': List of non-DICOM files within ZIP
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create the nested folder structure
        folder_a = os.path.join(tmpdir, "folder_a")
        folder_b = os.path.join(tmpdir, "folder_b")
        subfolder = os.path.join(folder_b, "subfolder")
        
        os.makedirs(folder_a)
        os.makedirs(subfolder)
        
        # Create DICOM files
        dicom1_path = os.path.join(folder_a, "image1.dcm")
        dicom2_path = os.path.join(subfolder, "image2.dcm")
        
        create_dummy_dicom(dicom1_path, patient_name="Patient^One", patient_id="P001")
        create_dummy_dicom(dicom2_path, patient_name="Patient^Two", patient_id="P002")
        
        # Create non-DICOM file
        txt_path = os.path.join(tmpdir, "random_file.txt")
        with open(txt_path, 'w') as f:
            f.write("This is a random text file that should be ignored.\n")
        
        # Create the ZIP file
        zip_path = os.path.join(tmpdir, "archive.zip")
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
            # Add DICOM files with relative paths
            zf.write(dicom1_path, arcname="folder_a/image1.dcm")
            zf.write(dicom2_path, arcname="folder_b/subfolder/image2.dcm")
            # Add text file
            zf.write(txt_path, arcname="random_file.txt")
        
        yield {
            'zip_path': zip_path,
            'temp_dir': tmpdir,
            'expected_dicoms': ['folder_a/image1.dcm', 'folder_b/subfolder/image2.dcm'],
            'expected_non_dicoms': ['random_file.txt']
        }
