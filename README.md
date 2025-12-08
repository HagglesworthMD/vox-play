# VoxelMask - Intelligent DICOM De-Identification Engine

<p align="center">
  <img src="src/voxelmask_loading.png" alt="VoxelMask Logo" width="200"/>
</p>

<p align="center">
  <strong>Version 2.0 BETA</strong> | Modality-Aware Safety Protocol v2.1 | Multi-Compliance Engine
</p>

<p align="center">
  <em>A comprehensive web-based DICOM de-identification workstation for medical imaging workflows</em>
</p>

<p align="center">
  ⚠️ <strong>BETA RELEASE</strong> ⚠️
</p>

> **⚠️ Beta Notice:** This software is currently in beta testing. While functional and tested, it may contain bugs or incomplete features. Not recommended for production clinical use without thorough validation. Please report any issues via GitHub Issues.

---

## 🛡️ Overview

VoxelMask is a professional-grade DICOM processing platform designed for healthcare organizations, research institutions, AI/ML companies, and legal departments. It provides intelligent, modality-aware de-identification with full audit trail capabilities and multi-jurisdictional compliance support.

### Core Operating Modes

| Mode | Purpose | Patient Data | Staff Data | UIDs |
|------|---------|--------------|------------|------|
| **Clinical Correction** | Fix patient demographics | ✅ Preserved/Updated | ✅ Preserved | 🔄 Optional Regen |
| **Research De-ID** | HIPAA Safe Harbor for AI/ML | ❌ Removed | ❌ Removed | 🔄 HMAC-remapped |
| **FOI Legal** | Crown Solicitor/litigation | ✅ Preserved | ❌ Redacted | ✅ Preserved |
| **FOI Patient** | Patient record requests | ✅ Preserved | ❌ Redacted | ✅ Preserved |

---

## 📋 Table of Contents

1. [Quick Upload](#-quick-upload---no-pre-processing-required)
2. [Use Cases](#-use-cases)
3. [Key Features](#-key-features)
4. [Operating Modes](#-operating-modes)
5. [DICOM Compliance Engine](#-dicom-compliance-engine)
6. [DICOM Viewer](#-dicom-viewer)
7. [Output Formats](#-output-formats)
8. [System Requirements & Compatibility](#-system-requirements--compatibility)
9. [Installation](#-installation)
10. [Architecture](#-architecture)
11. [API Reference](#-api-reference)
12. [Security & Audit](#-security--audit)

---

## 📥 Quick Upload - No Pre-Processing Required

**VoxelMask accepts DICOM files directly from your PACS viewer or workstation.**

Simply export/download a ZIP from your viewing software (Horos, OsiriX, RadiAnt, Sante, InteleViewer, ESMI VueMotion, etc.) and upload it directly to VoxelMask. No need to:
- ❌ Extract or unzip files first
- ❌ Convert to a specific format
- ❌ Remove existing viewers or metadata
- ❌ Organize folder structure

**Supported Input Formats**:
| Format | Support |
|--------|---------|
| Single DICOM file | ✅ |
| Multiple DICOM files | ✅ |
| ZIP archive (from any viewer) | ✅ |
| Nested folder structures | ✅ |
| Mixed modalities in one upload | ✅ |

> 💡 **Tip**: Most PACS viewers have an "Export to ZIP" or "Download Study" option. Use that directly - VoxelMask will automatically detect and process all DICOM files inside, ignoring any bundled viewers or non-DICOM files.

---

## 🎯 Use Cases

### 1. AI/ML Research & Commercial Data Sales

**Scenario**: Prepare medical imaging datasets for machine learning model training, commercial sale, or multi-site research collaborations.

**Requirements**:
- Complete removal of all 18 HIPAA identifiers
- Preservation of diagnostic image quality
- Consistent subject IDs for longitudinal studies
- NIfTI export for ML pipelines (PyTorch, TensorFlow, MONAI)
- Audit trail for regulatory compliance

**VoxelMask Solution**:
- **Research De-ID Mode** with HIPAA Safe Harbor profile
- HMAC-SHA256 UID remapping for consistent anonymization
- Date shifting preserves temporal relationships
- NIfTI export with quality audit (zero-loss conversion)
- Modality-aware pixel masking (US/SC/OT only)
- Professional Safe Harbor Certificate (PDF)

**Example Workflow**:
```
1. Upload CT/MRI/US study (DICOM)
2. Select "US Research (HIPAA Safe Harbor)" profile
3. Enter Trial ID, Site ID, Subject ID
4. Enable "Output as NIfTI" for ML pipeline
5. Download anonymized dataset with compliance certificate
```

**Output**:
- De-identified DICOM or NIfTI files
- `VoxelMask_SafeHarborCertificate.pdf`
- Quality audit with slice retention verification

---

### 2. Patient FOI Requests (Freedom of Information)

**Scenario**: Patient requests copies of their medical imaging records under FOI legislation, MyHealth Record access, or personal data access rights (GDPR Article 15).

**Requirements**:
- Preserve all patient data (name, DOB, dates)
- Redact staff names for employee privacy
- Include viewer for patient access
- Professional cover letter

**VoxelMask Solution**:
- **FOI Patient Mode** preserves chain of custody
- Staff name redaction (Operators, Physicians)
- Bundled DICOM Viewer for patient viewing
- Medical Image Release Letter (PDF)

**Example Workflow**:
```
1. Upload patient's imaging study
2. Select "FOI/Patient" profile
3. Enter case reference and recipient details
4. Optionally exclude scanned documents (SC/OT)
5. Download release package with cover letter
```

**Output**:
- Original DICOM files with staff names redacted
- `VoxelMask_PatientRelease.pdf` (cover letter)
- `DICOM_Viewer.html` for patient viewing
- SHA-256 hash verification

---

### 3. Crown Solicitor / Legal Discovery Requests

**Scenario**: Crown Solicitor's Office, insurance companies, or legal firms request medical imaging for litigation, coronial inquests, or workers' compensation claims.

**Requirements**:
- Forensic integrity (chain of custody)
- Original UIDs preserved (no modification)
- Staff names redacted (employee privacy protection)
- Hash verification for court admissibility
- Exclude worksheets/scanned documents (optional)

**VoxelMask Solution**:
- **FOI Legal Mode** maintains forensic integrity
- UIDs preserved (no regeneration)
- Staff name redaction with audit trail
- Forensic Integrity Certificate (PDF)
- SHA-256 hashing of original and processed files

**Example Workflow**:
```
1. Upload imaging study for legal matter
2. Select "FOI/Legal" profile
3. Enter case reference (e.g., "CROWN-2024-001")
4. Enable "Exclude Scanned Documents" if needed
5. ⚠️ Do NOT regenerate UIDs (breaks chain of custody)
6. Download forensic package
```

**Output**:
- DICOM files with staff names redacted
- `VoxelMask_ForensicCertificate.pdf`
- Hash verification for court admissibility
- Audit log with redaction details

**Legal Considerations**:
- Original UIDs preserved for chain of custody
- Pixel data unchanged (SHA-256 verified)
- Staff redaction protects employee privacy under Privacy Act
- Scanned document exclusion removes non-diagnostic content

---

### 4. Clinical Data Correction

**Scenario**: Patient name misspelled at scan time, wrong patient ID entered, or demographic data needs correction before PACS upload.

**Requirements**:
- Correct patient demographics
- Preserve diagnostic data
- Audit trail for corrections
- Optional UID regeneration for duplicate fixes

**VoxelMask Solution**:
- **Clinical Correction Mode** with full audit trail
- Toshiba/Aplio-style header overlay
- Correction notes with timestamp
- Optional UID regeneration

**Example Workflow**:
```
1. Upload incorrect DICOM study
2. Select "Clinical Correction" profile
3. Enter correct patient name, DOB, etc.
4. Add correction reason and operator name
5. Download corrected files for PACS upload
```

---

### 5. Multi-Site Research Collaboration

**Scenario**: Multi-center clinical trial requiring standardized de-identification across sites with consistent subject IDs.

**Requirements**:
- Consistent anonymization across sites
- Reproducible UID mapping
- Australian OAIC compliance (if AU sites)
- Date shifting with preserved intervals

**VoxelMask Solution**:
- **AU Strict (OAIC)** profile for Australian sites
- **US Research (Safe Harbor)** for US sites
- Secret salt for reproducible UID mapping
- Deterministic date shifting per patient

---

## ✨ Key Features

### Core Capabilities

- 🖥️ **Web-Based Interface** - Modern Streamlit UI with dark theme
- 🛡️ **Multi-Compliance Engine** - HIPAA, OAIC (Australia), and custom profiles
- 🔍 **Smart Pixel Masking** - Modality-aware burned-in PHI detection
- 📋 **Professional Audit Trail** - PDF reports with SHA-256 verification
- 📦 **Batch Processing** - Single files, multi-file uploads, and ZIP archives
- 🎯 **Interactive Redaction** - Click-and-drag canvas for manual PHI masking
- 🔐 **Forensic Integrity** - Chain of custody tracking for legal use
- 📊 **NIfTI Export** - AI/ML-ready output format with quality audit

### Modality-Aware Safety Protocol v2.1

| Modality | Masking Behavior | Reason |
|----------|------------------|--------|
| **US** (Ultrasound) | ✅ Applied | High burned-in PHI risk |
| **SC** (Secondary Capture) | ✅ Applied | Screenshots, annotations |
| **OT** (Other) | ✅ Applied | Text-heavy documents |
| **CT** (Computed Tomography) | ⚠️ Skipped | Protects diagnostic anatomy |
| **MRI** (Magnetic Resonance) | ⚠️ Skipped | Protects diagnostic anatomy |
| **XA** (X-Ray Angiography) | ⚠️ Skipped | Protects diagnostic anatomy |
| **DX** (Digital Radiography) | ⚠️ Skipped | Protects diagnostic anatomy |
| **NM** (Nuclear Medicine) | ⚠️ Skipped | Protects diagnostic anatomy |

---

## 🔧 Operating Modes

### 1. Clinical Correction Mode

**Purpose**: Correct patient demographics and metadata while preserving diagnostic integrity.

#### Available Fields
- **Patient Demographics**: Name, ID, Sex, Date of Birth
- **Study Information**: Accession Number, Study Date, Time, Type, Location
- **Personnel**: Sonographer, Referring Physician
- **Audit Trail**: Correction Notes, Reason for Correction, Operator Name

#### Output
- Corrected DICOM files
- `VoxelMask_DataRepairLog.pdf`
- Bundled DICOM Viewer

---

### 2. Research De-ID Mode

**Purpose**: Complete HIPAA Safe Harbor anonymization for AI/ML research, commercial data sales, or multi-site collaborations.

#### Compliance Standards
- **HIPAA Safe Harbor** (45 CFR 164.514(b)(2))
- **DICOM PS3.15** Basic Application Level Confidentiality Profile

#### Key Features
- **UID Remapping**: HMAC-SHA256 with secret salt
- **Date Shifting**: -30 to -365 days (configurable)
- **Text Cleaning**: SSN, phone, email, MRN patterns
- **Pixel Masking**: Automatic for US/SC/OT modalities

#### Research Context Fields
- Trial ID, Site ID, Subject ID, Time Point

#### Output
- De-identified DICOM or NIfTI files
- `VoxelMask_SafeHarborCertificate.pdf`
- Quality audit (for NIfTI)

---

### 3. FOI Mode (Freedom of Information)

**Purpose**: Process DICOM files for legal discovery, Crown Solicitor requests, and patient record access.

#### Key Differences from Research De-ID

| Aspect | Research De-ID | FOI Mode |
|--------|----------------|----------|
| Patient Name | ❌ Removed | ✅ **Preserved** |
| Patient ID | ❌ Removed | ✅ **Preserved** |
| Study Dates | 🔄 Shifted | ✅ **Preserved** |
| UIDs | 🔄 Remapped | ✅ **Preserved** |
| Staff Names | ❌ Removed | ❌ **Redacted** |

#### FOI Legal Mode (Crown Solicitor/Litigation)
- Forensic integrity with SHA-256 hashing
- Chain of custody documentation
- `VoxelMask_ForensicCertificate.pdf`

#### FOI Patient Mode (Patient Requests)
- Patient-friendly release format
- `VoxelMask_PatientRelease.pdf`
- Bundled DICOM Viewer

#### Staff Tags Redacted
| Tag | Name | Description |
|-----|------|-------------|
| (0008,1070) | OperatorsName | Sonographer/Technologist |
| (0008,1050) | PerformingPhysicianName | Performing doctor |
| (0008,0090) | ReferringPhysicianName | Referring doctor (optional) |
| (0008,1048) | PhysiciansOfRecord | Attending physicians |
| (0008,1060) | NameOfPhysiciansReadingStudy | Radiologists |
| (0040,A075) | VerifyingObserverName | Report verifiers |
| (0032,1032) | RequestingPhysician | Ordering physician |
| (0008,009C) | ConsultingPhysicianName | Consulting doctors |

---

## 🔒 DICOM Compliance Engine

### Complete Tag Processing Reference

#### HIPAA Safe Harbor Tags (Removed in Research Mode)

These 18+ identifier categories are removed or anonymized:

| # | HIPAA Category | DICOM Tags Affected |
|---|----------------|---------------------|
| 1 | **Names** | PatientName, PatientMotherBirthName, OtherPatientNames |
| 2 | **Geographic** | PatientAddress, InstitutionName, InstitutionAddress |
| 3 | **Dates** | PatientBirthDate (year kept), AdmissionDate, DischargeDate |
| 4 | **Phone Numbers** | PatientTelephoneNumbers, ReferringPhysicianTelephoneNumbers |
| 5 | **Fax Numbers** | (Included in phone fields) |
| 6 | **Email** | Pattern matching in text fields |
| 7 | **SSN** | Pattern matching (XXX-XX-XXXX) |
| 8 | **MRN** | PatientID, OtherPatientIDs, AccessionNumber |
| 9 | **Health Plan** | PatientInsurancePlanCodeSequence |
| 10 | **Account Numbers** | AdmissionID |
| 11 | **Certificate/License** | Pattern matching |
| 12 | **Vehicle IDs** | Pattern matching |
| 13 | **Device IDs** | DeviceSerialNumber, StationName |
| 14 | **URLs** | Pattern matching in text fields |
| 15 | **IP Addresses** | Pattern matching |
| 16 | **Biometric** | N/A for DICOM |
| 17 | **Full-face Photos** | Pixel masking |
| 18 | **Unique IDs** | All UIDs remapped via HMAC-SHA256 |

#### PHI Tags (Complete List)

```
Patient Identification:
  (0010,0010) PatientName
  (0010,0020) PatientID
  (0010,0030) PatientBirthDate
  (0010,0032) PatientBirthTime
  (0010,0040) PatientSex (kept if configured)
  (0010,1000) OtherPatientIDs
  (0010,1001) OtherPatientNames
  (0010,1010) PatientAge
  (0010,1020) PatientSize
  (0010,1030) PatientWeight
  (0010,1040) PatientAddress
  (0010,1060) PatientMotherBirthName
  (0010,2154) PatientTelephoneNumbers
  (0010,2160) EthnicGroup
  (0010,21B0) AdditionalPatientHistory
  (0010,4000) PatientComments

Institution/Physician:
  (0008,0080) InstitutionName
  (0008,0081) InstitutionAddress
  (0008,0082) InstitutionCodeSequence
  (0008,0090) ReferringPhysicianName
  (0008,0092) ReferringPhysicianAddress
  (0008,0094) ReferringPhysicianTelephoneNumbers
  (0008,1048) PhysiciansOfRecord
  (0008,1049) PhysiciansOfRecordIdentificationSequence
  (0008,1050) PerformingPhysicianName
  (0008,1052) PerformingPhysicianIdentificationSequence
  (0008,1060) NameOfPhysiciansReadingStudy
  (0008,1062) PhysiciansReadingStudyIdentificationSequence
  (0008,1070) OperatorsName
  (0008,1072) OperatorIdentificationSequence

Study/Accession:
  (0008,0050) AccessionNumber
  (0020,0010) StudyID

Device/Station:
  (0008,1010) StationName
  (0008,1040) InstitutionalDepartmentName

Request Attributes:
  (0040,0275) RequestAttributesSequence
  (0032,1032) RequestingPhysician
  (0032,1033) RequestingService

Other Identifiers:
  (0038,0010) AdmissionID
  (0038,0500) PatientState
  (0040,1001) RequestedProcedureID
  (0040,0009) ScheduledProcedureStepID
  (0040,2016) PlacerOrderNumberImagingServiceRequest
  (0040,2017) FillerOrderNumberImagingServiceRequest
```

#### Safe Tags Whitelist (Preserved for Research)

These tags are explicitly preserved as they contain no PHI and are critical for ML/research:

```
SOP Common Module:
  (0008,0016) SOPClassUID
  (0008,0018) SOPInstanceUID (remapped)
  (0008,0005) SpecificCharacterSet

Study/Series UIDs:
  (0020,000D) StudyInstanceUID (remapped)
  (0020,000E) SeriesInstanceUID (remapped)
  (0020,0052) FrameOfReferenceUID (remapped)

Modality Information:
  (0008,0060) Modality
  (0018,0015) BodyPartExamined
  (0020,0060) Laterality
  (0020,0062) ImageLaterality

Image Parameters (Critical for ML):
  (0028,0010) Rows
  (0028,0011) Columns
  (0028,0030) PixelSpacing
  (0028,0100) BitsAllocated
  (0028,0101) BitsStored
  (0028,0102) HighBit
  (0028,0103) PixelRepresentation
  (0028,0002) SamplesPerPixel
  (0028,0004) PhotometricInterpretation
  (7FE0,0010) PixelData

VOI LUT (Critical for CT Display):
  (0028,1050) WindowCenter
  (0028,1051) WindowWidth
  (0028,1052) RescaleIntercept
  (0028,1053) RescaleSlope
  (0028,1054) RescaleType

CT Acquisition Parameters:
  (0018,0060) KVP
  (0018,0088) SpacingBetweenSlices
  (0018,0050) SliceThickness
  (0018,1150) ExposureTime
  (0018,1151) XRayTubeCurrent
  (0018,1210) ConvolutionKernel
  (0018,5100) PatientPosition

MR Acquisition Parameters:
  (0018,0080) RepetitionTime
  (0018,0081) EchoTime
  (0018,0082) InversionTime
  (0018,0087) MagneticFieldStrength
  (0018,1314) FlipAngle
  (0018,0020) ScanningSequence
  (0018,0023) MRAcquisitionType

3D Reconstruction:
  (0020,0032) ImagePositionPatient
  (0020,0037) ImageOrientationPatient
  (0020,1041) SliceLocation

Transfer Syntax:
  (0002,0010) TransferSyntaxUID
  (0002,0002) MediaStorageSOPClassUID
  (0002,0003) MediaStorageSOPInstanceUID (remapped)
```

#### UID Remapping Tags

These UIDs are remapped using HMAC-SHA256 for consistent anonymization:

| Tag | Name | Remapping |
|-----|------|-----------|
| (0008,0018) | SOPInstanceUID | HMAC-SHA256 |
| (0020,000D) | StudyInstanceUID | HMAC-SHA256 |
| (0020,000E) | SeriesInstanceUID | HMAC-SHA256 |
| (0020,0052) | FrameOfReferenceUID | HMAC-SHA256 |
| (0002,0003) | MediaStorageSOPInstanceUID | HMAC-SHA256 |

#### Date Shifting Tags

| Tag | Name | Shift Range |
|-----|------|-------------|
| (0008,0020) | StudyDate | -30 to -365 days |
| (0008,0021) | SeriesDate | Same offset |
| (0008,0022) | AcquisitionDate | Same offset |
| (0008,0023) | ContentDate | Same offset |
| (0010,0030) | PatientBirthDate | Year only kept |

#### Text Scrubbing Tags

These text fields are scanned for PHI patterns:

| Tag | Name | Patterns Removed |
|-----|------|------------------|
| (0008,1030) | StudyDescription | Names, SSN, MRN |
| (0008,103E) | SeriesDescription | Names, SSN, MRN |
| (0018,1030) | ProtocolName | Names, SSN, MRN |
| (0010,4000) | PatientComments | All PHI patterns |
| (0032,4000) | StudyComments | All PHI patterns |
| (0020,4000) | ImageComments | All PHI patterns |

---

### Compliance Profile Comparison

| Feature | Internal Repair | US Research | AU Strict (OAIC) | FOI Legal | FOI Patient |
|---------|-----------------|-------------|------------------|-----------|-------------|
| **Patient Name** | Preserved | Anonymized | Hashed | Preserved | Preserved |
| **Patient ID** | Preserved | Anonymized | Hashed | Preserved | Preserved |
| **Patient DOB** | Preserved | Year only | Year only | Preserved | Preserved |
| **Study Dates** | Preserved | Shifted (-30 to -365d) | Shifted (-14 to -100d) | Preserved | Preserved |
| **Accession** | Preserved | Removed | Removed | Preserved | Preserved |
| **Staff Names** | Preserved | Removed | Removed | **Redacted** | **Redacted** |
| **Institution** | Preserved | Removed | Removed | Preserved | Preserved |
| **UIDs** | Optional Regen | HMAC-remapped | Regenerated | **Preserved** | **Preserved** |
| **Private Tags** | Preserved | Removed | Removed | Removed | Removed |
| **Pixel Masking** | Manual only | Auto (US/SC/OT) | Auto (US/SC/OT) | Manual only | Manual only |
| **Date Shift Seed** | N/A | Secret salt | PatientID hash | N/A | N/A |
| **PDF Report** | Data Repair Log | Safe Harbor Cert | OAIC Privacy Audit | Forensic Cert | Release Letter |

---

### De-identification Method Codes (DICOM PS3.15)

VoxelMask sets these compliance tags:

```
(0012,0062) PatientIdentityRemoved = "YES"
(0012,0063) DeidentificationMethod = "HIPAA_SAFE_HARBOR | VOXELMASK"

DeidentificationMethodCodeSequence:
  CodeValue = "113100"
  CodingSchemeDesignator = "DCM"
  CodeMeaning = "De-identification"
```

---

## 🖥️ DICOM Viewer

VoxelMask includes a **bundled HTML5 DICOM Viewer** in every output ZIP.

### Features
- **Zero Installation**: Single HTML file, runs in any modern browser
- **Cornerstone.js Engine**: Industry-standard medical imaging library
- **Window/Level Controls**: Adjust contrast and brightness
- **Zoom & Pan**: Navigate large images
- **Debug Console**: Built-in logging

### Browser Compatibility

| Browser | Status |
|---------|--------|
| Chrome 90+ | ✅ Fully Supported |
| Firefox 88+ | ✅ Fully Supported |
| Safari 14+ | ✅ Fully Supported |
| Edge 90+ | ✅ Fully Supported |
| Internet Explorer | ❌ Not Supported |

---

## 📁 Output Formats

### DICOM Output (Default)

```
{PatientName_or_SubjectID}/
├── StudyDescription_Modality/
│   └── S###_SeriesDescription/
│       └── IMG_####_filename.dcm
├── DICOM_Viewer.html
├── VoxelMask_Report.pdf
├── VoxelMask_AuditLog.txt
└── README.txt
```

### NIfTI Output (AI/ML Research)

- **Zero-Loss Conversion**: Relaxed validation for clinical data
- **Multi-frame Support**: Cine/4D data → 4D NIfTI
- **Quality Audit**: Input/output slice count verification

```
{SubjectID_TrialID}/
├── series_001.nii.gz
├── series_002.nii.gz
├── README_NIfTI.txt
└── VoxelMask_AuditLog.txt
```

*Note: DICOM Viewer NOT included with NIfTI output.*

---

## 💻 System Requirements & Compatibility

### Operating System

| OS | Status |
|----|--------|
| Linux (Ubuntu 20.04+) | ✅ Fully Supported |
| Linux (Arch/Steam Deck) | ✅ Fully Supported |
| macOS (11.0+) | ✅ Fully Supported |
| Windows (10/11) | ✅ Fully Supported |
| Docker | ✅ Recommended |

### DICOM Transfer Syntax Compatibility

| Transfer Syntax | Status |
|-----------------|--------|
| Implicit VR Little Endian | ✅ |
| Explicit VR Little Endian | ✅ |
| Explicit VR Big Endian | ✅ |
| JPEG Baseline | ✅ |
| JPEG Lossless | ✅ |
| JPEG 2000 | ✅ |
| JPEG-LS | ✅ |
| RLE Lossless | ✅ |
| Deflated Explicit VR | ✅ |

### Modality Compatibility

| Modality | Processing | Pixel Masking | NIfTI Export |
|----------|------------|---------------|--------------|
| CT | ✅ | ⚠️ Skipped | ✅ 3D |
| MRI | ✅ | ⚠️ Skipped | ✅ 3D |
| US | ✅ | ✅ Applied | ✅ 2D/4D |
| XA | ✅ | ⚠️ Skipped | ✅ 2D |
| DX/CR | ✅ | ⚠️ Skipped | ✅ 2D |
| NM/PT | ✅ | ⚠️ Skipped | ✅ 3D |
| SC | ✅ | ✅ Applied | ⚠️ Limited |
| OT | ✅ | ✅ Applied | ⚠️ Limited |
| SR | ⚠️ FOI Exclude | N/A | ❌ |

---

## 🚀 Installation

### Docker (Recommended)

```bash
git clone https://github.com/HagglesworthMD/VOXELMASK.git
cd VOXELMASK
docker-compose up --build
# Open http://localhost:8501
```

### Local Development

```bash
git clone https://github.com/HagglesworthMD/VOXELMASK.git
cd VOXELMASK
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
streamlit run src/app.py
```

### Dependencies

```
streamlit==1.28.0
pydicom
numpy>=1.24.0
opencv-python-headless
paddlepaddle
paddleocr
streamlit-drawable-canvas==0.9.3
Pillow
dicom2nifti>=2.4.9
nibabel>=5.1.0
scipy>=1.10.0
fpdf2>=2.7.0
```

---

## 🏗️ Architecture

```
VoxelMask/
├── src/
│   ├── app.py                    # Main Streamlit application
│   ├── foi_engine.py             # FOI processing (Legal/Patient)
│   ├── compliance_engine.py      # Multi-profile compliance manager
│   ├── clinical_corrector.py     # OCR-based PHI detection
│   ├── run_on_dicom.py           # Core DICOM processing pipeline
│   ├── nifti_handler.py          # NIfTI conversion
│   ├── pdf_reporter.py           # PDF report generator
│   ├── research_mode/
│   │   ├── anonymizer.py         # HIPAA Safe Harbor engine
│   │   ├── whitelist.py          # DICOM tag whitelist
│   │   └── cli.py                # Command-line interface
│   └── assets/
│       └── dicom_viewer.html     # Bundled viewer
├── docker-compose.yml
├── Dockerfile
└── requirements.txt
```

---

## 📖 API Reference

### Python API

```python
# Research Mode (AI/ML)
from research_mode import DicomAnonymizer, AnonymizationConfig

config = AnonymizationConfig(
    secret_salt=b"your-secret-salt",
    date_shift_range=(-365, -30),
    keep_patient_sex=True,
    pixel_mask_modalities={"US", "SC", "OT"}
)
anonymizer = DicomAnonymizer(config)
result = anonymizer.anonymize_file("input.dcm", "output.dcm")

# FOI Processing (Legal/Patient)
from foi_engine import FOIEngine

engine = FOIEngine(redact_referring_physician=False)
dataset, result = engine.process_dataset(
    dataset=pydicom.dcmread("input.dcm"),
    mode="legal",  # or "patient"
    exclude_scanned=True
)

# Compliance Engine
from compliance_engine import DicomComplianceManager

manager = DicomComplianceManager()
dataset, info = manager.process_dataset(
    dataset=ds,
    profile_mode="us_research_safe_harbor",
    fix_uids=True
)
```

### CLI

```bash
python -m research_mode.cli input.dcm -o output.dcm
python -m research_mode.cli input_dir/ -o output_dir/ --report report.json
```

---

## 🔒 Security & Audit

### Report Types

| Profile | Report | Filename |
|---------|--------|----------|
| Internal Repair | Data Repair Log | `VoxelMask_DataRepairLog.pdf` |
| US Research | Safe Harbor Certificate | `VoxelMask_SafeHarborCertificate.pdf` |
| AU Strict | OAIC Privacy Audit | `VoxelMask_OAIC_PrivacyAudit.pdf` |
| FOI Legal | Forensic Integrity Certificate | `VoxelMask_ForensicCertificate.pdf` |
| FOI Patient | Medical Image Release Letter | `VoxelMask_PatientRelease.pdf` |

### Security Features
- SHA-256 hash verification (input/output)
- Audit database logging (SQLite)
- Operator tracking
- Secret salt management for reproducible anonymization

---

## 📈 Version History

### v2.0.0 (2025-12)
- **FOI Mode**: Freedom of Information processing for legal/patient requests
- **Multi-Compliance Engine**: HIPAA, OAIC, and custom profiles
- **NIfTI Export**: AI/ML-ready output with quality audit
- **PDF Reports**: Professional compliance documentation
- **Bundled DICOM Viewer**: HTML5 viewer in every output

### v1.0.0 (2025-12-04)
- **Rebrand**: Adelaide Scrubber → VoxelMask
- **Modality-Aware Safety Protocol v2.1**
- **Zero-Loss Pipeline**: CT/MRI/NM/XA/DX pixel preservation
- **HIPAA Safe Harbor compliance**
- **Docker deployment with dark theme**

---

## 📄 License

Internal use only. Contact compliance team for distribution and licensing inquiries.

---

<p align="center">
  <strong>⚠️ Important</strong>: This system processes Protected Health Information (PHI). Ensure compliance with all applicable healthcare regulations including HIPAA, GDPR, Australian Privacy Act, and local data protection laws before use in production environments.
</p>

<p align="center">
  <strong>🔐 Security</strong>: Always use secure authentication, HTTPS, and proper access controls when deploying in production environments.
</p>
