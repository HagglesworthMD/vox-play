# VoxelMask - User Guide

**Intelligent De-Identification for Research & Clinical Correction**

---

## 🛡 The Modality-Aware Protocol

VoxelMask automatically detects the risk level of your images and applies the appropriate de-identification strategy.

### 1. The "Zero-Loss" Pipeline (CT, MRI, NM, XA, DX)

* **Target:** High-fidelity volumetric and diagnostic data
* **Behavior:** Metadata cleaned, Pixels locked (Crypto-verified)
* **Use Case:** Radiomics research, AI training datasets, quantitative analysis
* **Guarantee:** Hounsfield Units and voxel values are 100% preserved

### 2. The "Masking" Pipeline (Ultrasound, Secondary Capture)

* **Target:** High-risk burned-in PHI
* **Behavior:** Black mask applied to top 10% of pixels
* **Use Case:** Ultrasound studies with patient name overlays
* **Guarantee:** PHI regions obscured while preserving diagnostic content

---

## 🚀 Quick Start

### Single File Processing

1. Upload a DICOM file using the file uploader
2. Select processing mode:
   - **Clinical Correction**: Correct patient demographics (retains PHI)
   - **Research De-ID**: Full HIPAA Safe Harbor anonymization
3. Click "Process DICOM"
4. Download the processed file and audit receipt

### Batch Processing

1. Upload multiple DICOM files or a ZIP archive
2. Configure batch settings (patient ID prefix, etc.)
3. Process all files in one operation
4. Download ZIP containing all processed files with individual audit receipts

### Interactive Redaction

1. Upload a file with burned-in PHI
2. Use the canvas to draw rectangles over sensitive areas
3. The mask will be applied during processing
4. Verify the redaction in the preview

---

## 📋 Processing Modes

### Clinical Correction Mode

- **Purpose:** Fix incorrect patient demographics
- **PHI Status:** RETAINED (not for research sharing)
- **Pixel Handling:** Optional manual masking
- **Output:** Corrected DICOM with audit trail

### Research De-ID Mode

- **Purpose:** Prepare data for research/commercial use
- **PHI Status:** REMOVED (HIPAA Safe Harbor compliant)
- **Pixel Handling:** Automatic modality-aware masking
- **Output:** Anonymized DICOM with compliance certificate

---

## 🔐 Security Features

### Chain of Custody

Every processed file includes:
- SHA-256 hash of original file
- SHA-256 hash of anonymized file
- Unique scrub UUID for audit tracking
- Timestamp and operator ID

### Audit Receipt

Professional audit receipts include:
- Original and new metadata summary
- Pixel action taken (PRESERVED/MASKED)
- Compliance certification
- Safety notifications (if applicable)

---

## ⚙️ Configuration

### Environment Variables

```bash
# Audit database path
AUDIT_DB_PATH=/app/scrub_history.db

# Anonymization salt (for deterministic UID remapping)
ANONYMIZATION_SALT=your-secret-salt
```

### Streamlit Theme

VoxelMask uses a dark theme with cyan accents:
- Primary Color: `#00d4ff`
- Background: `#0e1117`
- Secondary Background: `#262730`

---

## 📊 Supported Modalities

| Modality | Code | Pixel Action | Notes |
|----------|------|--------------|-------|
| CT Scan | CT | PRESERVED | Hounsfield units protected |
| MRI | MR | PRESERVED | Signal intensity protected |
| Nuclear Medicine | NM | PRESERVED | Count data protected |
| X-Ray Angiography | XA | PRESERVED | Diagnostic quality maintained |
| Digital X-Ray | DX | PRESERVED | Full resolution maintained |
| Ultrasound | US | MASKED | Top 10% masked for PHI |
| Secondary Capture | SC | MASKED | Screenshots/reports masked |

---

## 🆘 Troubleshooting

### White/Inverted Images
- Check that RescaleIntercept/RescaleSlope tags are preserved
- Verify PhotometricInterpretation is correct

### Missing Metadata
- Some tags are intentionally removed for HIPAA compliance
- Check the audit receipt for detailed modification list

### Batch Processing Errors
- Ensure all files are valid DICOM format
- Check available disk space for output files

---

*VoxelMask v1.0 - Intelligent DICOM De-Identification*
