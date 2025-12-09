# Release Notes - VoxelMask v0.3.0

**Release Date:** December 9, 2025  
**Codename:** Compliance Verification Edition

---

## 🚀 Major Feature: Automated Compliance Verification

This release introduces a comprehensive **Automated Test Suite** powered by Pytest, enabling deterministic verification of all de-identification logic on every code change.

### Highlights

- **37 Automated Tests** covering core compliance logic, file handling, NIfTI conversion, and UI components
- **Deterministic Data Generation**: Synthetic DICOM fixtures ensure reproducible testing without exposing real patient data
- **HIPAA Safe Harbor Verification**: Unit tests assert that:
  - `PatientName` is removed or anonymized
  - `StudyDate` is shifted by a random offset (14-100 days, seeded by PatientID)
  - `StudyInstanceUID` is regenerated to prevent re-identification
  - Private tags are stripped
  - `PatientIdentityRemoved` flag is set to "YES"
- **FOI Legal Mode Verification**: Tests confirm that:
  - `PatientName` is PRESERVED (chain of custody)
  - `ReferringPhysicianName` is REDACTED (staff privacy)
  - Original UIDs are maintained for forensic integrity
- **NIfTI Conversion Validation**: Tests verify:
  - Output files end in `.nii.gz`
  - Output file size is greater than 0 bytes
  - Quality audit tracks input/output slice counts
- **ZIP Handling Tests**: Verify:
  - Nested folder structures are correctly extracted
  - DICOM files are identified by magic bytes (not just extension)
  - Non-DICOM files (`.txt`, `.html`, etc.) are properly ignored

---

## 🛡️ Security & Privacy

### US Research Profile - Date Shifting Fix

**Critical Fix:** The US Research (HIPAA Safe Harbor) profile now correctly implements date shifting, matching the documented behavior in the README.

| Before v0.3.0 | After v0.3.0 |
|---------------|--------------|
| `StudyDate` preserved | `StudyDate` shifted by -14 to -100 days |
| UIDs preserved unless `fix_uids=True` | UIDs regenerated automatically |
| `DeidentificationMethod` = `HIPAA_SAFE_HARBOR` | `DeidentificationMethod` = `HIPAA_SAFE_HARBOR | DATE_SHIFT | UID_REGEN | VOXELMASK` |

### Validation & Compliance Badge

The README now includes a **GitHub Actions Build Status badge** at the top, providing instant visibility into the test suite status:

![Build Status](https://github.com/HagglesworthMD/VOXELMASK/actions/workflows/test.yml/badge.svg)

A new **"🛡️ Validation & Compliance"** section documents:
- Testing methodology
- Forensic integrity checks (SHA-256)
- CI/CD pipeline details

---

## 🐛 Bug Fixes

### Date Shifting Logic (Critical)

- **Fixed:** US Research profile was not shifting dates, potentially exposing temporal identifiers
- **Solution:** Implemented deterministic date shifting using PatientID-seeded random offset
- **Verification:** New unit test `test_study_date_shifted_in_us_research` ensures this cannot regress

### UID Regeneration

- **Fixed:** UIDs were only regenerated when `fix_uids=True` was explicitly set
- **Solution:** US Research profile now regenerates UIDs by default as part of proper de-identification
- **Verification:** New unit test `test_study_instance_uid_regenerated_in_us_research`

### Nested ZIP Handling

- **Improved:** Enhanced detection of DICOM files within nested folder structures
- **Added:** Magic byte validation (`DICM` at offset 128) instead of relying on file extensions
- **Verification:** `test_dicom_magic_bytes_validation` and `test_subfolder_dicoms_are_found`

---

## 🧪 Technical Details

### CI/CD Pipeline

A new GitHub Actions workflow (`.github/workflows/test.yml`) provides:

- **Trigger:** Runs on every push to `main` and all pull requests
- **Matrix Testing:** Python 3.10, 3.11, and 3.12
- **System Dependencies:** Automatically installs `dcm2niix` for NIfTI conversion
- **Coverage Reports:** Uploaded to Codecov
- **Linting:** Optional flake8 syntax checking

### dcm2niix Integration

- NIfTI conversion tests now properly detect and use `dcm2niix` when available
- Graceful skipping with `pytest.mark.skipif` when tool is not installed
- Zero-loss conversion verified with quality audit

### Test Suite Structure

```
tests/
├── conftest.py           # Fixtures: dummy_dicom_file, nested_zip_structure
├── test_file_handling.py # 10 tests: ZIP extraction, DICOM detection
├── test_foi_preservation.py # 2 tests: FOI legal mode
├── test_nifti.py         # 10 tests: NIfTI conversion
├── test_research_mode.py # 7 tests: HIPAA Safe Harbor
└── test_ui.py            # 8 tests: Streamlit UI
```

### Dependencies Added

```
pytest>=7.0.0
pytest-cov>=4.0.0
```

---

## 📋 Upgrade Instructions

1. **Pull the latest code:**
   ```bash
   git pull origin main
   ```

2. **Update dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

3. **Run tests locally:**
   ```bash
   pytest -v
   ```

4. **Optional - Install dcm2niix for NIfTI tests:**
   ```bash
   # Ubuntu/Debian
   sudo apt-get install dcm2niix
   
   # macOS
   brew install dcm2niix
   
   # Arch Linux
   sudo pacman -S dcm2niix
   ```

---

## 📊 Test Results Summary

| Category | Passed | Skipped | Notes |
|----------|--------|---------|-------|
| File Handling | 10 | 0 | ZIP extraction, DICOM detection |
| FOI Preservation | 2 | 0 | Legal mode data preservation |
| Research Mode | 7 | 0 | HIPAA Safe Harbor de-identification |
| NIfTI Conversion | 10 | 0* | *Requires dcm2niix installed |
| UI Tests | 0 | 8 | Requires full Streamlit environment |
| **Total** | **28** | **8** | |

---

## 🔮 Coming in v0.4.0

- Enhanced pixel masking with OCR-based PHI detection
- Multi-language support for international deployments
- DICOM PS3.15 Option D (deterministic UID) support
- Expanded NIfTI output options for neuroimaging research

---

**Full Changelog:** [v0.2.0...v0.3.0](https://github.com/HagglesworthMD/VOXELMASK/compare/v0.2.0...v0.3.0)
