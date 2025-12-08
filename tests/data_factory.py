#!/usr/bin/env python3
"""
VoxelMask Scrubber - Synthetic DICOM Data Factory

Generates synthetic DICOM files for all major modalities to test
the anonymization pipeline without requiring real patient data.
"""

import os
import numpy as np
from pathlib import Path
from datetime import datetime

import pydicom
from pydicom.dataset import Dataset, FileDataset, FileMetaDataset
from pydicom.uid import (
    generate_uid,
    ExplicitVRLittleEndian,
    ImplicitVRLittleEndian,
    RLELossless,
)


def generate_dummy_dicom(
    filename: str,
    modality: str,
    is_color: bool = False,
    add_burned_in_annotation: bool = False,
    image_size: tuple = (512, 512),
) -> str:
    """
    Generate a synthetic DICOM file with valid headers and pixel data.
    
    Args:
        filename: Output filename (will be created in test_input/)
        modality: DICOM modality code (CT, MR, US, NM, XA, DX, SC)
        is_color: If True, generate RGB pixel data (3 samples per pixel)
        add_burned_in_annotation: If True, add white square in top-left to simulate PHI
        image_size: Tuple of (rows, cols) for image dimensions
        
    Returns:
        Full path to generated file
    """
    # Ensure output directory exists
    output_dir = Path(__file__).parent / "test_input"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / filename
    
    # Create file meta information
    file_meta = FileMetaDataset()
    file_meta.MediaStorageSOPClassUID = get_sop_class_uid(modality)
    file_meta.MediaStorageSOPInstanceUID = generate_uid()
    file_meta.TransferSyntaxUID = ExplicitVRLittleEndian
    file_meta.ImplementationClassUID = generate_uid()
    file_meta.ImplementationVersionName = "VOXELMASK_1.0"
    
    # Create the FileDataset
    ds = FileDataset(
        str(output_path),
        {},
        file_meta=file_meta,
        preamble=b"\x00" * 128
    )
    
    # ═══════════════════════════════════════════════════════════════════════════
    # PATIENT MODULE (PHI - Should be anonymized)
    # ═══════════════════════════════════════════════════════════════════════════
    ds.PatientName = "TEST^SUBJECT^MIDDLE"
    ds.PatientID = "12345"
    ds.PatientBirthDate = "19800115"
    ds.PatientSex = "M"
    ds.PatientAge = "045Y"
    ds.PatientAddress = "123 Test Street, VoxelMask SA 5000"
    ds.PatientTelephoneNumbers = "0412345678"
    
    # ═══════════════════════════════════════════════════════════════════════════
    # STUDY MODULE
    # ═══════════════════════════════════════════════════════════════════════════
    ds.StudyDate = "20250101"
    ds.StudyTime = "120000"
    ds.StudyDescription = f"Test {modality} Study"
    ds.StudyInstanceUID = generate_uid()
    ds.StudyID = "STUDY001"
    ds.AccessionNumber = "ACC123456"
    ds.ReferringPhysicianName = "DR^REFERRING^PHYSICIAN"
    
    # ═══════════════════════════════════════════════════════════════════════════
    # SERIES MODULE
    # ═══════════════════════════════════════════════════════════════════════════
    ds.SeriesDate = "20250101"
    ds.SeriesTime = "120100"
    ds.SeriesDescription = f"Test {modality} Series"
    ds.SeriesInstanceUID = generate_uid()
    ds.SeriesNumber = 1
    ds.Modality = modality
    
    # ═══════════════════════════════════════════════════════════════════════════
    # GENERAL EQUIPMENT MODULE
    # ═══════════════════════════════════════════════════════════════════════════
    ds.Manufacturer = "VoxelMask Test Systems"
    ds.InstitutionName = "Royal VoxelMask Hospital"
    ds.InstitutionAddress = "Port Road, VoxelMask SA 5000"
    ds.StationName = "TEST_STATION_01"
    ds.InstitutionalDepartmentName = "Radiology"
    ds.ManufacturerModelName = f"TestScanner_{modality}"
    ds.DeviceSerialNumber = "SN123456789"
    ds.SoftwareVersions = "1.0.0"
    
    # ═══════════════════════════════════════════════════════════════════════════
    # INSTANCE MODULE
    # ═══════════════════════════════════════════════════════════════════════════
    ds.SOPClassUID = file_meta.MediaStorageSOPClassUID
    ds.SOPInstanceUID = file_meta.MediaStorageSOPInstanceUID
    ds.InstanceNumber = 1
    ds.ContentDate = "20250101"
    ds.ContentTime = "120200"
    
    # ═══════════════════════════════════════════════════════════════════════════
    # IMAGE PIXEL MODULE
    # ═══════════════════════════════════════════════════════════════════════════
    rows, cols = image_size
    
    if is_color:
        # RGB color image (e.g., Ultrasound with color Doppler)
        ds.SamplesPerPixel = 3
        ds.PhotometricInterpretation = "RGB"
        ds.PlanarConfiguration = 0  # Color-by-pixel (R1G1B1R2G2B2...)
        ds.BitsAllocated = 8
        ds.BitsStored = 8
        ds.HighBit = 7
        ds.PixelRepresentation = 0  # Unsigned
        
        # Generate random RGB noise
        np.random.seed(42)  # Reproducible for testing
        pixel_array = np.random.randint(0, 256, (rows, cols, 3), dtype=np.uint8)
        
        # Add burned-in annotation simulation (white square in top-left)
        if add_burned_in_annotation:
            # Simulate a "name tag" burned into the image
            pixel_array[10:60, 10:150, :] = 255  # White rectangle
            
    else:
        # Grayscale image (CT, MR, NM, XA, DX)
        ds.SamplesPerPixel = 1
        ds.PhotometricInterpretation = "MONOCHROME2"
        ds.BitsAllocated = 16
        ds.BitsStored = 12
        ds.HighBit = 11
        ds.PixelRepresentation = 0  # Unsigned for most, signed for CT
        
        # CT uses signed representation with Rescale
        if modality == "CT":
            ds.PixelRepresentation = 1  # Signed
            ds.RescaleIntercept = -1024.0
            ds.RescaleSlope = 1.0
            ds.WindowCenter = 40.0
            ds.WindowWidth = 400.0
            # Generate CT-like values (Hounsfield units stored as unsigned + offset)
            np.random.seed(42)
            pixel_array = np.random.randint(0, 2048, (rows, cols), dtype=np.int16)
        else:
            # Standard grayscale
            np.random.seed(42)
            pixel_array = np.random.randint(0, 4096, (rows, cols), dtype=np.uint16)
        
        # Add burned-in annotation simulation for grayscale
        if add_burned_in_annotation:
            max_val = 4095 if modality != "CT" else 2047
            pixel_array[10:60, 10:150] = max_val  # Bright rectangle
    
    ds.Rows = rows
    ds.Columns = cols
    ds.PixelData = pixel_array.tobytes()
    
    # ═══════════════════════════════════════════════════════════════════════════
    # MODALITY-SPECIFIC ATTRIBUTES
    # ═══════════════════════════════════════════════════════════════════════════
    add_modality_specific_tags(ds, modality)
    
    # ═══════════════════════════════════════════════════════════════════════════
    # BURNED-IN ANNOTATION FLAG
    # ═══════════════════════════════════════════════════════════════════════════
    if add_burned_in_annotation or modality in ["US", "SC"]:
        ds.BurnedInAnnotation = "YES"
    else:
        ds.BurnedInAnnotation = "NO"
    
    # Save the file
    ds.save_as(str(output_path), write_like_original=False)
    
    print(f"✓ Generated: {filename} ({modality}, {'Color' if is_color else 'Grayscale'}, "
          f"{'with burned-in PHI' if add_burned_in_annotation else 'clean'})")
    
    return str(output_path)


def get_sop_class_uid(modality: str) -> str:
    """Get appropriate SOP Class UID for modality."""
    sop_classes = {
        "CT": "1.2.840.10008.5.1.4.1.1.2",      # CT Image Storage
        "MR": "1.2.840.10008.5.1.4.1.1.4",      # MR Image Storage
        "US": "1.2.840.10008.5.1.4.1.1.6.1",    # Ultrasound Image Storage
        "NM": "1.2.840.10008.5.1.4.1.1.20",     # Nuclear Medicine Image Storage
        "XA": "1.2.840.10008.5.1.4.1.1.12.1",   # X-Ray Angiographic Image Storage
        "DX": "1.2.840.10008.5.1.4.1.1.1.1",    # Digital X-Ray Image Storage
        "SC": "1.2.840.10008.5.1.4.1.1.7",      # Secondary Capture Image Storage
        "PT": "1.2.840.10008.5.1.4.1.1.128",    # PET Image Storage
    }
    return sop_classes.get(modality, "1.2.840.10008.5.1.4.1.1.7")  # Default to SC


def add_modality_specific_tags(ds: Dataset, modality: str) -> None:
    """Add modality-specific DICOM tags."""
    
    if modality == "CT":
        ds.ImageType = ["ORIGINAL", "PRIMARY", "AXIAL"]
        ds.SliceThickness = 2.5
        ds.KVP = 120.0
        ds.DataCollectionDiameter = 500.0
        ds.ReconstructionDiameter = 350.0
        ds.DistanceSourceToDetector = 1040.0
        ds.DistanceSourceToPatient = 570.0
        ds.GantryDetectorTilt = 0.0
        ds.TableHeight = 150.0
        ds.RotationDirection = "CW"
        ds.ExposureTime = 500
        ds.XRayTubeCurrent = 200
        ds.Exposure = 100
        ds.FilterType = "BODY"
        ds.ConvolutionKernel = "STANDARD"
        ds.BodyPartExamined = "CHEST"
        ds.ImagePositionPatient = [-175.0, -175.0, 0.0]
        ds.ImageOrientationPatient = [1.0, 0.0, 0.0, 0.0, 1.0, 0.0]
        ds.SliceLocation = 0.0
        ds.PixelSpacing = [0.68, 0.68]
        
    elif modality == "MR":
        ds.ImageType = ["ORIGINAL", "PRIMARY", "M", "ND"]
        ds.ScanningSequence = "SE"
        ds.SequenceVariant = "SK"
        ds.ScanOptions = "SAT1"
        ds.MRAcquisitionType = "2D"
        ds.SliceThickness = 5.0
        ds.RepetitionTime = 500.0
        ds.EchoTime = 15.0
        ds.NumberOfAverages = 2
        ds.ImagingFrequency = 63.87
        ds.ImagedNucleus = "1H"
        ds.EchoNumbers = 1
        ds.MagneticFieldStrength = 1.5
        ds.SpacingBetweenSlices = 5.5
        ds.NumberOfPhaseEncodingSteps = 256
        ds.EchoTrainLength = 1
        ds.PercentSampling = 100.0
        ds.PercentPhaseFieldOfView = 100.0
        ds.PixelBandwidth = 200.0
        ds.BodyPartExamined = "BRAIN"
        ds.ImagePositionPatient = [-100.0, -100.0, 0.0]
        ds.ImageOrientationPatient = [1.0, 0.0, 0.0, 0.0, 1.0, 0.0]
        ds.SliceLocation = 0.0
        ds.PixelSpacing = [0.9, 0.9]
        
    elif modality == "US":
        ds.ImageType = ["ORIGINAL", "PRIMARY"]
        ds.BodyPartExamined = "ABDOMEN"
        ds.TransducerType = "CURVED LINEAR"
        ds.FrameTime = 33.3  # ~30 fps
        ds.NumberOfFrames = 1
        ds.UltrasoundColorDataPresent = 1
        ds.PixelSpacing = [0.3, 0.3]
        # US typically has burned-in annotations
        ds.BurnedInAnnotation = "YES"
        
    elif modality == "NM":
        ds.ImageType = ["ORIGINAL", "PRIMARY", "STATIC"]
        ds.BodyPartExamined = "WHOLEBODY"
        ds.CountsAccumulated = 1000000
        ds.ActualFrameDuration = 600000  # 10 minutes in ms
        ds.NumberOfFrames = 1
        ds.EnergyWindowInformationSequence = []
        ds.RadiopharmaceuticalInformationSequence = []
        ds.DetectorInformationSequence = []
        ds.ImagePositionPatient = [-250.0, -250.0, 0.0]
        ds.ImageOrientationPatient = [1.0, 0.0, 0.0, 0.0, 1.0, 0.0]
        ds.PixelSpacing = [4.0, 4.0]
        
    elif modality == "XA":
        ds.ImageType = ["ORIGINAL", "PRIMARY"]
        ds.BodyPartExamined = "HEART"
        ds.KVP = 80.0
        ds.ExposureTime = 5
        ds.XRayTubeCurrent = 500
        ds.DistanceSourceToPatient = 1000.0
        ds.DistanceSourceToDetector = 1200.0
        ds.PositionerType = "CARM"
        ds.PositionerPrimaryAngle = 30.0
        ds.PositionerSecondaryAngle = 0.0
        ds.ImagePositionPatient = [-150.0, -150.0, 0.0]
        ds.ImageOrientationPatient = [1.0, 0.0, 0.0, 0.0, 1.0, 0.0]
        ds.PixelSpacing = [0.3, 0.3]
        
    elif modality == "DX":
        ds.ImageType = ["ORIGINAL", "PRIMARY"]
        ds.BodyPartExamined = "CHEST"
        ds.ViewPosition = "PA"
        ds.KVP = 120.0
        ds.ExposureTime = 10
        ds.XRayTubeCurrent = 200
        ds.Exposure = 2
        ds.ExposureInuAs = 2000
        ds.DistanceSourceToPatient = 1800.0
        ds.DistanceSourceToDetector = 1800.0
        ds.Grid = "IN"
        ds.ImagePositionPatient = [-200.0, -200.0, 0.0]
        ds.ImageOrientationPatient = [1.0, 0.0, 0.0, 0.0, 1.0, 0.0]
        ds.PixelSpacing = [0.14, 0.14]
        ds.ImagerPixelSpacing = [0.14, 0.14]


def generate_test_suite() -> list:
    """
    Generate the complete test suite of synthetic DICOM files.
    
    Returns:
        List of generated file paths
    """
    print("\n" + "═" * 70)
    print("  VOXELMASK - SYNTHETIC DICOM DATA FACTORY")
    print("═" * 70 + "\n")
    
    generated_files = []
    
    # Define test cases: (filename, modality, is_color, add_burned_in)
    test_cases = [
        # Ultrasound - Color with burned-in PHI (SHOULD BE MASKED)
        ("test_US.dcm", "US", True, True),
        
        # CT - Grayscale, anatomical (SHOULD BYPASS MASKING - Safety Protocol)
        ("test_CT.dcm", "CT", False, False),
        
        # MRI - Grayscale, anatomical (SHOULD BYPASS MASKING - Safety Protocol)
        ("test_MR.dcm", "MR", False, False),
        
        # Nuclear Medicine - Grayscale (SHOULD BYPASS MASKING - Safety Protocol)
        ("test_NM.dcm", "NM", False, False),
        
        # X-Ray Angiography - Grayscale (SHOULD BYPASS MASKING - Safety Protocol)
        ("test_XA.dcm", "XA", False, False),
        
        # Digital X-Ray - Grayscale (SHOULD BYPASS MASKING - Safety Protocol)
        ("test_DX.dcm", "DX", False, False),
    ]
    
    for filename, modality, is_color, add_burned_in in test_cases:
        path = generate_dummy_dicom(
            filename=filename,
            modality=modality,
            is_color=is_color,
            add_burned_in_annotation=add_burned_in
        )
        generated_files.append(path)
    
    print(f"\n✅ Generated {len(generated_files)} test files in tests/test_input/")
    print("═" * 70 + "\n")
    
    return generated_files


if __name__ == "__main__":
    generate_test_suite()
