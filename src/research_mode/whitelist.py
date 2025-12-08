"""
DICOM Tag Whitelist for Research Mode Anonymization

Based on DICOM PS3.15 Basic Application Level Confidentiality Profile
and HIPAA Safe Harbor requirements.

Architecture: STRICT WHITELIST - If a tag is NOT on this list, it MUST be removed.
"""

from typing import Set, Tuple

# ═══════════════════════════════════════════════════════════════════════════════
# SAFE TAGS WHITELIST
# These tags are considered safe for research and do not contain PHI.
# Organized by DICOM module for clarity.
# ═══════════════════════════════════════════════════════════════════════════════

SAFE_TAGS: Set[Tuple[int, int]] = {
    # ─────────────────────────────────────────────────────────────────────────────
    # SOP Common Module (Required for valid DICOM)
    # ─────────────────────────────────────────────────────────────────────────────
    (0x0008, 0x0016),  # SOPClassUID - Required
    (0x0008, 0x0018),  # SOPInstanceUID - Will be remapped
    (0x0008, 0x0005),  # SpecificCharacterSet
    
    # ─────────────────────────────────────────────────────────────────────────────
    # General Study Module (Safe subset)
    # ─────────────────────────────────────────────────────────────────────────────
    (0x0020, 0x000D),  # StudyInstanceUID - Will be remapped
    (0x0008, 0x0020),  # StudyDate - Will be shifted
    (0x0008, 0x0030),  # StudyTime - Kept for temporal analysis
    (0x0008, 0x0050),  # AccessionNumber - Will be anonymized
    (0x0008, 0x1030),  # StudyDescription - Will be scrubbed for PHI
    
    # ─────────────────────────────────────────────────────────────────────────────
    # General Series Module (Safe subset)
    # ─────────────────────────────────────────────────────────────────────────────
    (0x0020, 0x000E),  # SeriesInstanceUID - Will be remapped
    (0x0008, 0x0060),  # Modality - Critical for ML
    (0x0008, 0x0021),  # SeriesDate - Will be shifted
    (0x0008, 0x0031),  # SeriesTime
    (0x0020, 0x0011),  # SeriesNumber
    (0x0008, 0x0068),  # PresentationIntentType
    (0x0008, 0x103E),  # SeriesDescription - Will be scrubbed for PHI
    (0x0018, 0x1030),  # ProtocolName - Will be scrubbed for PHI
    
    # ─────────────────────────────────────────────────────────────────────────────
    # Frame of Reference Module
    # ─────────────────────────────────────────────────────────────────────────────
    (0x0020, 0x0052),  # FrameOfReferenceUID - Will be remapped
    (0x0020, 0x1040),  # PositionReferenceIndicator
    
    # ─────────────────────────────────────────────────────────────────────────────
    # General Equipment Module (Safe subset - no institution info)
    # ─────────────────────────────────────────────────────────────────────────────
    (0x0008, 0x0070),  # Manufacturer
    (0x0008, 0x1090),  # ManufacturerModelName
    (0x0018, 0x1020),  # SoftwareVersions
    (0x0018, 0x1000),  # DeviceSerialNumber - Consider removing in strict mode
    
    # ─────────────────────────────────────────────────────────────────────────────
    # General Image Module
    # ─────────────────────────────────────────────────────────────────────────────
    (0x0020, 0x0013),  # InstanceNumber
    (0x0020, 0x0020),  # PatientOrientation
    (0x0008, 0x0023),  # ContentDate - Will be shifted
    (0x0008, 0x0033),  # ContentTime
    (0x0020, 0x0012),  # AcquisitionNumber
    (0x0008, 0x0022),  # AcquisitionDate - Will be shifted
    (0x0008, 0x0032),  # AcquisitionTime
    
    # ─────────────────────────────────────────────────────────────────────────────
    # Image Pixel Module - CRITICAL FOR ML
    # ─────────────────────────────────────────────────────────────────────────────
    (0x0028, 0x0006),  # PlanarConfiguration
    (0x0028, 0x0008),  # NumberOfFrames
    (0x7FE0, 0x0010),  # PixelData - THE ACTUAL IMAGE
    (0x0028, 0x0034),  # PixelAspectRatio
    (0x0028, 0x0120),  # PixelPaddingValue
    # Note: Critical Image Pixel Structure tags moved to "PREVENTS WHITE SCREEN" section above
    
    # ─────────────────────────────────────────────────────────────────────────────
    # Multi-frame Module
    # ─────────────────────────────────────────────────────────────────────────────
    (0x0028, 0x0009),  # FrameIncrementPointer
    (0x0018, 0x1063),  # FrameTime
    (0x0018, 0x1065),  # FrameTimeVector
    
    # ─────────────────────────────────────────────────────────────────────────────
    # Image Plane Module (Critical for 3D reconstruction)
    # ─────────────────────────────────────────────────────────────────────────────
    (0x0020, 0x0032),  # ImagePositionPatient
    (0x0020, 0x0037),  # ImageOrientationPatient
    (0x0018, 0x0050),  # SliceThickness
    (0x0020, 0x1041),  # SliceLocation
    
    # ─────────────────────────────────────────────────────────────────────────────
    # VOI LUT Module (Window/Level) - CRITICAL FOR CT DISPLAY
    # ─────────────────────────────────────────────────────────────────────────────
    (0x0028, 0x1050),  # WindowCenter
    (0x0028, 0x1051),  # WindowWidth
    
    # Image Pixel Structure (Critical for Display) - PREVENTS WHITE SCREEN
    (0x0028, 0x0002),  # SamplesPerPixel
    (0x0028, 0x0004),  # PhotometricInterpretation
    (0x0028, 0x0010),  # Rows
    (0x0028, 0x0011),  # Columns
    (0x0028, 0x0030),  # PixelSpacing
    (0x0028, 0x0100),  # BitsAllocated
    (0x0028, 0x0101),  # BitsStored
    (0x0028, 0x0102),  # HighBit
    (0x0028, 0x0103),  # PixelRepresentation (CRITICAL: Prevents White Screen)
    
    (0x0028, 0x1052),  # RescaleIntercept - ESSENTIAL for Hounsfield Units
    (0x0028, 0x1053),  # RescaleSlope - ESSENTIAL for Hounsfield Units
    (0x0028, 0x1054),  # RescaleType
    (0x0028, 0x1055),  # WindowCenterWidthExplanation
    (0x0028, 0x1056),  # VOILUTFunction
    (0x0028, 0x1057),  # VOILUTSequence
    (0x0028, 0x1058),  # VOILUTDescriptor
    (0x0028, 0x1059),  # VOILUTData
    (0x0028, 0x105A),  # VOILUTExplanation
    (0x0028, 0x3010),  # VOILUTSequence - Alternative location
    (0x0028, 0x3002),  # LUTDescriptor
    (0x0028, 0x3003),  # LUTData
    (0x0028, 0x3006),  # ModalityLUTSequence
    (0x0028, 0x3008),  # ModalityLUTType
    (0x0028, 0x3004),  # LUTExplanation
    
    # ─────────────────────────────────────────────────────────────────────────────
    # Modality-Specific Acquisition Parameters (Safe for research)
    # ─────────────────────────────────────────────────────────────────────────────
    # CT
    (0x0018, 0x0060),  # KVP
    (0x0018, 0x0088),  # SpacingBetweenSlices
    (0x0018, 0x0090),  # DataCollectionDiameter
    (0x0018, 0x1100),  # ReconstructionDiameter
    (0x0018, 0x1110),  # DistanceSourceToDetector
    (0x0018, 0x1111),  # DistanceSourceToPatient
    (0x0018, 0x1120),  # GantryDetectorTilt
    (0x0018, 0x1130),  # TableHeight
    (0x0018, 0x1140),  # RotationDirection
    (0x0018, 0x1150),  # ExposureTime
    (0x0018, 0x1151),  # XRayTubeCurrent
    (0x0018, 0x1152),  # Exposure
    (0x0018, 0x1160),  # FilterType
    (0x0018, 0x1170),  # GeneratorPower
    (0x0018, 0x1190),  # FocalSpots
    (0x0018, 0x1210),  # ConvolutionKernel - CRITICAL for CT reconstruction algorithm
    (0x0018, 0x5100),  # PatientPosition
    
    # MR
    (0x0018, 0x0020),  # ScanningSequence
    (0x0018, 0x0021),  # SequenceVariant
    (0x0018, 0x0022),  # ScanOptions
    (0x0018, 0x0023),  # MRAcquisitionType
    (0x0018, 0x0024),  # SequenceName
    (0x0018, 0x0025),  # AngioFlag
    (0x0018, 0x0080),  # RepetitionTime
    (0x0018, 0x0081),  # EchoTime
    (0x0018, 0x0082),  # InversionTime
    (0x0018, 0x0083),  # NumberOfAverages
    (0x0018, 0x0084),  # ImagingFrequency
    (0x0018, 0x0085),  # ImagedNucleus
    (0x0018, 0x0086),  # EchoNumbers
    (0x0018, 0x0087),  # MagneticFieldStrength
    (0x0018, 0x0089),  # NumberOfPhaseEncodingSteps
    (0x0018, 0x0091),  # EchoTrainLength
    (0x0018, 0x0093),  # PercentSampling
    (0x0018, 0x0094),  # PercentPhaseFieldOfView
    (0x0018, 0x0095),  # PixelBandwidth
    (0x0018, 0x1310),  # AcquisitionMatrix
    (0x0018, 0x1312),  # InPlanePhaseEncodingDirection
    (0x0018, 0x1314),  # FlipAngle
    (0x0018, 0x1316),  # SAR
    (0x0018, 0x1318),  # dB/dt
    
    # Ultrasound
    (0x0018, 0x6011),  # SequenceOfUltrasoundRegions
    (0x0018, 0x6012),  # RegionSpatialFormat
    (0x0018, 0x6014),  # RegionDataType
    (0x0018, 0x6016),  # RegionFlags
    (0x0018, 0x6018),  # RegionLocationMinX0
    (0x0018, 0x601A),  # RegionLocationMinY0
    (0x0018, 0x601C),  # RegionLocationMaxX1
    (0x0018, 0x601E),  # RegionLocationMaxY1
    (0x0018, 0x6020),  # ReferencePixelX0
    (0x0018, 0x6022),  # ReferencePixelY0
    (0x0018, 0x6024),  # PhysicalUnitsXDirection
    (0x0018, 0x6026),  # PhysicalUnitsYDirection
    (0x0018, 0x6028),  # ReferencePixelPhysicalValueX
    (0x0018, 0x602A),  # ReferencePixelPhysicalValueY
    (0x0018, 0x602C),  # PhysicalDeltaX
    (0x0018, 0x602E),  # PhysicalDeltaY
    
    # ─────────────────────────────────────────────────────────────────────────────
    # Anatomical Information (Critical for ML classification)
    # ─────────────────────────────────────────────────────────────────────────────
    (0x0018, 0x0015),  # BodyPartExamined
    (0x0018, 0x5101),  # ViewPosition
    (0x0020, 0x0060),  # Laterality
    (0x0020, 0x0062),  # ImageLaterality
    (0x0008, 0x2218),  # AnatomicRegionSequence
    
    # ─────────────────────────────────────────────────────────────────────────────
    # Color/Palette
    # ─────────────────────────────────────────────────────────────────────────────
    (0x0028, 0x1101),  # RedPaletteColorLookupTableDescriptor
    (0x0028, 0x1102),  # GreenPaletteColorLookupTableDescriptor
    (0x0028, 0x1103),  # BluePaletteColorLookupTableDescriptor
    (0x0028, 0x1201),  # RedPaletteColorLookupTableData
    (0x0028, 0x1202),  # GreenPaletteColorLookupTableData
    (0x0028, 0x1203),  # BluePaletteColorLookupTableData
    
    # ─────────────────────────────────────────────────────────────────────────────
    # Transfer Syntax
    # ─────────────────────────────────────────────────────────────────────────────
    (0x0002, 0x0000),  # FileMetaInformationGroupLength
    (0x0002, 0x0001),  # FileMetaInformationVersion
    (0x0002, 0x0002),  # MediaStorageSOPClassUID
    (0x0002, 0x0003),  # MediaStorageSOPInstanceUID - Will be remapped
    (0x0002, 0x0010),  # TransferSyntaxUID
    (0x0002, 0x0012),  # ImplementationClassUID
    (0x0002, 0x0013),  # ImplementationVersionName
}

# ═══════════════════════════════════════════════════════════════════════════════
# TAGS THAT REQUIRE SPECIAL PROCESSING (not just keep/remove)
# ═══════════════════════════════════════════════════════════════════════════════

# UIDs that need to be remapped (hashed) for consistency
UID_TAGS: Set[Tuple[int, int]] = {
    (0x0008, 0x0018),  # SOPInstanceUID
    (0x0020, 0x000D),  # StudyInstanceUID
    (0x0020, 0x000E),  # SeriesInstanceUID
    (0x0020, 0x0052),  # FrameOfReferenceUID
    (0x0002, 0x0003),  # MediaStorageSOPInstanceUID
}

# Date tags that need to be shifted
DATE_TAGS: Set[Tuple[int, int]] = {
    (0x0008, 0x0020),  # StudyDate
    (0x0008, 0x0021),  # SeriesDate
    (0x0008, 0x0022),  # AcquisitionDate
    (0x0008, 0x0023),  # ContentDate
    (0x0010, 0x0030),  # PatientBirthDate - MUST be shifted or removed
}

# Text tags that need PHI scrubbing (patterns like names, SSN, MRN)
TEXT_SCRUB_TAGS: Set[Tuple[int, int]] = {
    (0x0008, 0x1030),  # StudyDescription
    (0x0008, 0x103E),  # SeriesDescription
    (0x0008, 0x1032),  # ProcedureCodeSequence
    (0x0018, 0x1030),  # ProtocolName
    (0x0010, 0x4000),  # PatientComments
    (0x0032, 0x4000),  # StudyComments
    (0x0020, 0x4000),  # ImageComments
}

# ═══════════════════════════════════════════════════════════════════════════════
# PHI TAGS - MUST BE REMOVED OR ANONYMIZED (HIPAA Safe Harbor)
# ═══════════════════════════════════════════════════════════════════════════════

PHI_TAGS: Set[Tuple[int, int]] = {
    # Patient Identification
    (0x0010, 0x0010),  # PatientName
    (0x0010, 0x0020),  # PatientID
    (0x0010, 0x0030),  # PatientBirthDate
    (0x0010, 0x0032),  # PatientBirthTime
    (0x0010, 0x0040),  # PatientSex - Can be kept for research if needed
    (0x0010, 0x1000),  # OtherPatientIDs
    (0x0010, 0x1001),  # OtherPatientNames
    (0x0010, 0x1010),  # PatientAge
    (0x0010, 0x1020),  # PatientSize
    (0x0010, 0x1030),  # PatientWeight
    (0x0010, 0x1040),  # PatientAddress
    (0x0010, 0x1060),  # PatientMotherBirthName
    (0x0010, 0x2154),  # PatientTelephoneNumbers
    (0x0010, 0x2160),  # EthnicGroup
    (0x0010, 0x21B0),  # AdditionalPatientHistory
    (0x0010, 0x4000),  # PatientComments
    
    # Institution/Physician
    (0x0008, 0x0080),  # InstitutionName
    (0x0008, 0x0081),  # InstitutionAddress
    (0x0008, 0x0082),  # InstitutionCodeSequence
    (0x0008, 0x0090),  # ReferringPhysicianName
    (0x0008, 0x0092),  # ReferringPhysicianAddress
    (0x0008, 0x0094),  # ReferringPhysicianTelephoneNumbers
    (0x0008, 0x1048),  # PhysiciansOfRecord
    (0x0008, 0x1049),  # PhysiciansOfRecordIdentificationSequence
    (0x0008, 0x1050),  # PerformingPhysicianName
    (0x0008, 0x1052),  # PerformingPhysicianIdentificationSequence
    (0x0008, 0x1060),  # NameOfPhysiciansReadingStudy
    (0x0008, 0x1062),  # PhysiciansReadingStudyIdentificationSequence
    (0x0008, 0x1070),  # OperatorsName
    (0x0008, 0x1072),  # OperatorIdentificationSequence
    
    # Study/Accession
    (0x0008, 0x0050),  # AccessionNumber - Should be anonymized
    (0x0020, 0x0010),  # StudyID
    
    # Device/Station
    (0x0008, 0x1010),  # StationName
    (0x0008, 0x1040),  # InstitutionalDepartmentName
    
    # Request Attributes
    (0x0040, 0x0275),  # RequestAttributesSequence
    (0x0032, 0x1032),  # RequestingPhysician
    (0x0032, 0x1033),  # RequestingService
    
    # Other identifiers
    (0x0038, 0x0010),  # AdmissionID
    (0x0038, 0x0500),  # PatientState
    (0x0040, 0x1001),  # RequestedProcedureID
    (0x0040, 0x0009),  # ScheduledProcedureStepID
    (0x0040, 0x2016),  # PlacerOrderNumberImagingServiceRequest
    (0x0040, 0x2017),  # FillerOrderNumberImagingServiceRequest
}


def is_tag_safe(tag: Tuple[int, int]) -> bool:
    """
    Check if a DICOM tag is on the safe whitelist.
    
    Args:
        tag: Tuple of (group, element) representing the DICOM tag
        
    Returns:
        True if tag is safe to keep, False if it should be removed
    """
    return tag in SAFE_TAGS


def is_private_tag(tag: Tuple[int, int]) -> bool:
    """
    Check if a DICOM tag is a private tag (odd group number).
    Private tags MUST be removed unless specifically whitelisted.
    
    Args:
        tag: Tuple of (group, element) representing the DICOM tag
        
    Returns:
        True if tag is private (odd group number)
    """
    return tag[0] % 2 == 1


def is_uid_tag(tag: Tuple[int, int]) -> bool:
    """Check if tag is a UID that needs remapping."""
    return tag in UID_TAGS


def is_date_tag(tag: Tuple[int, int]) -> bool:
    """Check if tag is a date that needs shifting."""
    return tag in DATE_TAGS


def is_text_scrub_tag(tag: Tuple[int, int]) -> bool:
    """Check if tag is a text field that needs PHI pattern scrubbing."""
    return tag in TEXT_SCRUB_TAGS


def is_phi_tag(tag: Tuple[int, int]) -> bool:
    """Check if tag contains PHI that must be removed."""
    return tag in PHI_TAGS
