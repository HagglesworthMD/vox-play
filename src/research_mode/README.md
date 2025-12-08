# Research Mode DICOM Anonymization Module

A Python-based DICOM anonymization module that strips 100% of Protected Health Information (PHI) to prepare medical imaging data for commercial research or machine learning sales.

## Compliance Standards

- **HIPAA Safe Harbor** (45 CFR 164.514(b)(2))
- **DICOM PS3.15** Basic Application Level Confidentiality Profile

## Key Features

### 1. Whitelist Architecture
- **Strict "Keep List"** approach: Only explicitly approved tags are retained
- All private tags (odd group numbers) are removed by default
- Non-whitelisted tags are automatically removed

### 2. Smart Anonymization

#### UID Remapping
- Uses **HMAC-SHA256** with a secret salt for stable UID generation
- Same patient processed twice gets the same anonymous ID
- Preserves longitudinal research data validity

#### Date Shifting
- All dates shifted by a consistent random offset per study
- Preserves temporal intervals (delta time) between events
- Hides actual event dates

#### Text Cleaning
- Scrubs PHI patterns from text fields:
  - SSN patterns (XXX-XX-XXXX)
  - Phone numbers
  - Email addresses
  - MRN patterns
  - Name patterns (Dr., Mr., Mrs., etc.)

### 3. Audit & Verification
- Generates `compliance_report.json` for every batch
- Lists all files changed and tags modified
- SHA-256 hash verification of pixel data integrity

## Installation

```bash
pip install -r requirements.txt
```

## Usage

### Python API

```python
from research_mode import DicomAnonymizer, AnonymizationConfig, ComplianceReportGenerator

# Configure anonymizer
config = AnonymizationConfig(
    secret_salt=b"your_secret_salt_here",  # Keep this secure!
    date_shift_range=(-365, -30),
    keep_patient_sex=True,
)

# Create anonymizer
anonymizer = DicomAnonymizer(config)

# Anonymize a single file
result = anonymizer.anonymize_file("input.dcm", "output.dcm")

# Check result
if result.success:
    print(f"Tags removed: {len(result.tags_removed)}")
    print(f"UIDs remapped: {len(result.uids_remapped)}")
    print(f"Pixel data preserved: {result.pixel_data_preserved}")

# Generate compliance report
generator = ComplianceReportGenerator()
generator.add_result(result)
generator.save_report("compliance_report.json")
```

### Command Line

```bash
# Anonymize a single file
python -m research_mode.cli input.dcm -o output.dcm

# Anonymize a directory
python -m research_mode.cli input_dir/ -o output_dir/

# Generate compliance report
python -m research_mode.cli input_dir/ -o output_dir/ --report compliance_report.json

# Use custom salt for reproducible UIDs
python -m research_mode.cli input.dcm -o output.dcm --salt-file my_salt.key

# Generate a new salt file
python -m research_mode.cli --generate-salt my_salt.key input.dcm -o output.dcm
```

## Compliance Report Structure

```json
{
  "report_metadata": {
    "report_id": "abc123...",
    "generation_timestamp": "2024-01-15T10:30:00Z",
    "generator_version": "1.0.0"
  },
  "compliance_standards": [
    "HIPAA Safe Harbor (45 CFR 164.514(b)(2))",
    "DICOM PS3.15 Basic Application Level Confidentiality Profile"
  ],
  "processing_summary": {
    "total_files_processed": 10,
    "successful_files": 10,
    "failed_files": 0
  },
  "aggregate_statistics": {
    "total_tags_removed": 150,
    "total_tags_anonymized": 20,
    "total_uids_remapped": 30,
    "total_dates_shifted": 40,
    "total_texts_scrubbed": 5,
    "total_private_tags_removed": 25
  },
  "integrity_verification": {
    "all_pixel_data_preserved": true
  },
  "file_entries": [
    {
      "file_identification": {
        "original_filename": "study001.dcm",
        "anonymized_filename": "study001.dcm",
        "processing_timestamp": "2024-01-15T10:30:00Z"
      },
      "integrity_verification": {
        "original_pixel_hash": "sha256:abc123...",
        "anonymized_pixel_hash": "sha256:abc123...",
        "pixel_data_preserved": true
      }
    }
  ]
}
```

## Safe Tags Whitelist

The following categories of tags are preserved:

- **SOP Common Module**: SOPClassUID, SOPInstanceUID (remapped)
- **Study/Series UIDs**: Remapped with HMAC-SHA256
- **Modality Information**: Modality, BodyPartExamined, Laterality
- **Image Parameters**: Rows, Columns, BitsAllocated, PixelSpacing, etc.
- **Acquisition Parameters**: KVP, ExposureTime, RepetitionTime, EchoTime, etc.
- **Pixel Data**: Preserved with integrity verification
- **VOI LUT**: WindowCenter, WindowWidth, RescaleSlope, etc.

## Tags Removed

- All patient identification (Name, ID, BirthDate, Address, Phone)
- All institution information (Name, Address)
- All physician names
- All private tags (odd group numbers)
- All accession numbers and study IDs

## Testing

```bash
cd src
python -m pytest research_mode/tests/ -v
```

## Security Considerations

1. **Secret Salt**: Store the HMAC salt securely. If compromised, UIDs could be reversed.
2. **Audit Logs**: Keep compliance reports for regulatory purposes.
3. **Pixel Data**: While metadata is anonymized, burned-in PHI in images requires separate handling.

## License

Internal use only. Contact compliance team for distribution.
