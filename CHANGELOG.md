# Changelog

All notable changes to this project are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html) where applicable.

---

## [Unreleased]

### Added
- Comprehensive deterministic unit test suite for core anonymization pipeline
- New testing strategy documentation clarifying unit vs integration boundaries

---

## [0.3.0] – 2025-12-14

### Added

#### Test Suite Improvements
- 21 deterministic unit tests for `audit_manager.py`
  - AuditLogger CRUD operations
  - Statistics date filtering
  - CSV export via pandas stub
  - Atomic scrub success and failure paths
- Full branch coverage for `anonymize_metadata()` in `run_on_dicom.py`
  - Research vs clinical context handling
  - UID regeneration and missing-tag robustness
  - Context precedence (research overrides clinical)
- OCR/text detection unit tests for `detect_text_box_from_array()`
  - Frame sampling logic
  - Static box consistency rules
  - OCR exception handling
- Deterministic tests for `process_dataset()` metadata paths
- Failure-path tests for unreadable DICOM handling

#### Documentation
- Comprehensive Testing Strategy section in README
- CHANGELOG.md following Keep a Changelog format

### Changed
- Improved audit pipeline testability without modifying production behavior
- Clarified testing boundaries for integration-heavy code paths
- Marked demo and CLI blocks with `# pragma: no cover` for honest coverage reporting
- Marked `process_dicom()` pixel pipeline with `# pragma: no cover` (integration-tested separately)

### Fixed
- Uncovered error-handling branches in audit and scrub logic
- Silent failure paths in atomic scrub operations
- Missing PatientID attribute edge cases in anonymize_metadata

### Coverage Improvements

| Module | Before | After |
|--------|--------|-------|
| `audit_manager.py` | ~48% | **97%** (production code) |
| `clinical_corrector.py` | ~52% | **99%** |
| `compliance_engine.py` | ~58% | **99%** |
| `run_on_dicom.py` | ~25% | **97%** (core logic) |

---

## [0.2.0] – 2025-12-08

### Added
- **FOI Mode**: Freedom of Information processing for legal/patient requests
- **Multi-Compliance Engine V1.0**: HIPAA, OAIC, and custom profiles
- **NIfTI Export**: AI/ML-ready output with quality audit
- **PDF Reports**: Professional compliance documentation
- **Bundled DICOM Viewer**: HTML5 viewer in every output
- **Modality-Aware Safety Protocol V1.0**
- **Zero-Loss Pipeline**: CT/MRI/NM/XA/DX pixel preservation
- HIPAA Safe Harbor compliance
- Docker deployment with dark theme

---

## Notes

- Integration-heavy pixel pipelines are intentionally excluded from unit tests
- OCR, OpenCV, and filesystem pipelines are validated separately via integration tests
- All test helpers use deterministic data generation to avoid flaky tests
