"""
VoxelMask FOI Engine - Freedom of Information Request Handler
==============================================================
Processes DICOM files for legal discovery and patient record requests.

Key Differences from Research De-ID:
- PRESERVES: PatientID, Patient Name, Dates (chain of custody)
- PRESERVES: UIDs (forensic integrity)
- REDACTS: Staff names (Operators, Technicians, Physicians)
- REMOVES: Private tags (vendor-specific data)

Author: VoxelMask Team
"""

import os
import hashlib
from datetime import datetime
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field

import pydicom
from pydicom.dataset import Dataset


@dataclass
class FOIProcessingResult:
    """Result of FOI processing operation."""
    success: bool = False
    mode: str = "unknown"  # 'legal' or 'patient'
    files_processed: int = 0
    redactions: List[Dict] = field(default_factory=list)
    excluded_files: List[str] = field(default_factory=list)
    hashes: List[Dict] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    error: Optional[str] = None
    # ═══════════════════════════════════════════════════════════════
    # DICOM Metadata - Extracted from ORIGINAL dataset for PDF reports
    # ═══════════════════════════════════════════════════════════════
    study_date: str = "Unknown"      # (0008,0020) StudyDate
    accession: str = "Unknown"       # (0008,0050) AccessionNumber  
    modality: str = "Unknown"        # (0008,0060) Modality
    patient_name: str = "Unknown"    # (0010,0010) PatientName (preserved in FOI)



class FOIEngine:
    """
    Freedom of Information Engine for legal and patient record requests.
    
    Features:
    - Staff name redaction (protects employee privacy)
    - UID preservation (chain of custody)
    - Patient data preservation (legal discovery)
    - Scanned document exclusion (optional)
    - Hash verification for forensic integrity
    """
    
    # Staff-related DICOM tags to redact
    STAFF_TAGS = [
        (0x0008, 0x1070),  # Operators' Name
        (0x0008, 0x1050),  # Performing Physician's Name
        (0x0008, 0x0090),  # Referring Physician's Name (optional - may keep for legal)
        (0x0008, 0x1048),  # Physician(s) of Record
        (0x0008, 0x1060),  # Name of Physician(s) Reading Study
        (0x0040, 0xA075),  # Verifying Observer Name
        (0x0040, 0xA073),  # Verifying Observer Sequence (contains names)
        (0x0032, 0x1032),  # Requesting Physician
        (0x0008, 0x009C),  # Consulting Physician's Name
    ]
    
    # Tags to always preserve for legal chain of custody
    PRESERVE_TAGS = [
        (0x0010, 0x0010),  # Patient Name
        (0x0010, 0x0020),  # Patient ID
        (0x0010, 0x0030),  # Patient Birth Date
        (0x0008, 0x0020),  # Study Date
        (0x0008, 0x0030),  # Study Time
        (0x0008, 0x0050),  # Accession Number
        (0x0020, 0x000D),  # Study Instance UID
        (0x0020, 0x000E),  # Series Instance UID
        (0x0008, 0x0018),  # SOP Instance UID
    ]
    
    def __init__(self, redact_referring_physician: bool = False):
        """
        Initialize FOI Engine.
        
        Args:
            redact_referring_physician: If True, also redacts ReferringPhysicianName
        """
        self.redact_referring = redact_referring_physician
    
    def process_dataset(
        self,
        dataset: Dataset,
        mode: str = "legal",
        exclude_scanned: bool = False
    ) -> Tuple[Dataset, FOIProcessingResult]:
        """
        Process a DICOM dataset for FOI release.
        
        Args:
            dataset: pydicom Dataset to process
            mode: 'legal' (forensic integrity) or 'patient' (friendly release)
            exclude_scanned: If True, raises exception for SC/OT modality
            
        Returns:
            Tuple of (processed_dataset, result)
        """
        result = FOIProcessingResult(mode=mode)
        
        try:
            # ═══════════════════════════════════════════════════════════════
            # EXTRACT ORIGINAL METADATA FIRST (Before any processing!)
            # These values go into the PDF report for legal chain of custody
            # ═══════════════════════════════════════════════════════════════
            
            # StudyDate (0008,0020) - Format as YYYY-MM-DD if possible
            if hasattr(dataset, 'StudyDate') and dataset.StudyDate:
                try:
                    sd_str = str(dataset.StudyDate).strip()
                    if len(sd_str) == 8 and sd_str.isdigit():
                        result.study_date = f"{sd_str[0:4]}-{sd_str[4:6]}-{sd_str[6:8]}"
                    elif sd_str:
                        result.study_date = sd_str
                except Exception:
                    result.study_date = str(dataset.StudyDate)
            
            # AccessionNumber (0008,0050)
            if hasattr(dataset, 'AccessionNumber') and dataset.AccessionNumber:
                acc_str = str(dataset.AccessionNumber).strip()
                if acc_str:
                    result.accession = acc_str
            
            # Modality (0008,0060)
            if hasattr(dataset, 'Modality') and dataset.Modality:
                result.modality = str(dataset.Modality).upper()
            
            # PatientName (0010,0010) - Preserved in FOI mode
            if hasattr(dataset, 'PatientName') and dataset.PatientName:
                result.patient_name = str(dataset.PatientName)
            
            # Check if scanned document and should exclude
            if exclude_scanned:
                should_exclude, reason = self.is_scanned_document(dataset)
                if should_exclude:
                    result.success = False
                    result.excluded_files.append(reason)
                    result.error = f"Excluded: {reason}"
                    return dataset, result
            
            # Calculate original hash
            if hasattr(dataset, 'PixelData') and dataset.PixelData:
                original_hash = hashlib.sha256(dataset.PixelData).hexdigest()
            else:
                original_hash = "NO_PIXEL_DATA"
            
            # Process based on mode
            if mode == "legal":
                dataset, redactions = self._process_legal(dataset)
            else:
                dataset, redactions = self._process_patient(dataset)
            
            result.redactions = redactions
            
            # Remove private tags
            private_removed = self._remove_private_tags(dataset)
            if private_removed > 0:
                result.redactions.append({
                    'tag': 'Private Tags',
                    'action': f'Removed {private_removed} private tag groups'
                })
            
            # Calculate processed hash
            if hasattr(dataset, 'PixelData') and dataset.PixelData:
                processed_hash = hashlib.sha256(dataset.PixelData).hexdigest()
            else:
                processed_hash = "NO_PIXEL_DATA"
            
            result.hashes.append({
                'original': original_hash,
                'processed': processed_hash,
                'unchanged': original_hash == processed_hash
            })
            
            result.success = True
            result.files_processed = 1
            
        except Exception as e:
            result.success = False
            result.error = str(e)
        
        return dataset, result
    
    def _process_legal(self, dataset: Dataset) -> Tuple[Dataset, List[Dict]]:
        """
        Process for legal/forensic release.
        
        - Redacts staff names for employee privacy
        - Preserves all patient data and UIDs
        """
        redactions = []
        
        for tag_tuple in self.STAFF_TAGS:
            tag = pydicom.tag.Tag(*tag_tuple)
            
            # Skip referring physician if not configured to redact
            if tag_tuple == (0x0008, 0x0090) and not self.redact_referring:
                continue
            
            if tag in dataset:
                original_value = str(dataset[tag].value)
                tag_name = dataset[tag].keyword if hasattr(dataset[tag], 'keyword') else f"({tag_tuple[0]:04X},{tag_tuple[1]:04X})"
                
                # Redact to "REDACTED" for legal clarity
                dataset[tag].value = "REDACTED"
                
                redactions.append({
                    'tag': tag_name,
                    'original': original_value[:20] + '...' if len(original_value) > 20 else original_value,
                    'action': 'Redacted (Staff Privacy)'
                })
        
        return dataset, redactions
    
    def _process_patient(self, dataset: Dataset) -> Tuple[Dataset, List[Dict]]:
        """
        Process for patient record release.
        
        - Same as legal but with friendlier messaging
        - Redacts staff names
        """
        # Same processing as legal for now
        return self._process_legal(dataset)
    
    def _remove_private_tags(self, dataset: Dataset) -> int:
        """
        Remove all private (vendor-specific) tags.
        
        Returns:
            Count of private tag groups removed
        """
        removed = 0
        
        # Find all private tags (odd group numbers)
        private_tags = [tag for tag in dataset.keys() if tag.is_private]
        
        for tag in private_tags:
            try:
                del dataset[tag]
                removed += 1
            except:
                pass
        
        # Also check sequences
        for elem in dataset:
            if elem.VR == 'SQ' and elem.value:
                for item in elem.value:
                    if isinstance(item, Dataset):
                        removed += self._remove_private_tags(item)
        
        return removed
    
    def is_scanned_document(self, dataset: Dataset) -> Tuple[bool, str]:
        """
        Check if dataset is a scanned document (SC/OT modality).
        
        Args:
            dataset: pydicom Dataset to check
            
        Returns:
            Tuple of (is_scanned, reason_string)
        """
        modality = getattr(dataset, 'Modality', '').upper()
        
        if modality == 'SC':
            return True, f"Secondary Capture (SC) - Likely scanned document"
        
        if modality == 'OT':
            return True, f"Other (OT) - Non-imaging document"
        
        # Check for document-like characteristics
        sop_class = getattr(dataset, 'SOPClassUID', '')
        if '1.2.840.10008.5.1.4.1.1.88' in str(sop_class):  # SR
            return True, f"Structured Report (SR) - Text document"
        
        # Check image type for DERIVED/SECONDARY
        # Note: ImageType may be list, tuple, or pydicom.MultiValue - all are iterable
        image_type = getattr(dataset, 'ImageType', [])
        try:
            # Normalize to uppercase strings (handles MultiValue, list, tuple)
            image_type_values = [str(x).upper() for x in image_type]
        except TypeError:
            image_type_values = []
        
        if 'DERIVED' in image_type_values and 'SECONDARY' in image_type_values:
            # Might be a worksheet/report
            series_desc = str(getattr(dataset, 'SeriesDescription', '')).lower()
            if any(w in series_desc for w in ['report', 'worksheet', 'summary', 'document']):
                return True, f"Derived Secondary - Worksheet/Report"
        
        return False, ""


def exclude_scanned_documents(dataset: Dataset) -> bool:
    """
    Convenience function to check if a dataset should be excluded.
    
    Args:
        dataset: pydicom Dataset to check
        
    Returns:
        True if the dataset is a scanned document and should be excluded
    """
    engine = FOIEngine()
    should_exclude, _ = engine.is_scanned_document(dataset)
    return should_exclude


def process_foi_request(
    dataset: Dataset,
    mode: str = "legal",
    exclude_scanned: bool = False,
    redact_referring: bool = False
) -> Tuple[Dataset, FOIProcessingResult]:
    """
    Convenience function to process a single dataset for FOI.
    
    Args:
        dataset: pydicom Dataset to process
        mode: 'legal' or 'patient'
        exclude_scanned: Exclude SC/OT modalities
        redact_referring: Also redact referring physician
        
    Returns:
        Tuple of (processed_dataset, result)
    """
    engine = FOIEngine(redact_referring_physician=redact_referring)
    return engine.process_dataset(dataset, mode, exclude_scanned)


# ═══════════════════════════════════════════════════════════════════════════════
# FOI BATCH PROCESSOR
# ═══════════════════════════════════════════════════════════════════════════════

class FOIBatchProcessor:
    """
    Process multiple DICOM files for FOI release.
    """
    
    def __init__(
        self,
        mode: str = "legal",
        exclude_scanned: bool = False,
        redact_referring: bool = False
    ):
        self.engine = FOIEngine(redact_referring_physician=redact_referring)
        self.mode = mode
        self.exclude_scanned = exclude_scanned
    
    def process_files(
        self,
        input_paths: List[str],
        output_dir: str
    ) -> FOIProcessingResult:
        """
        Process multiple DICOM files.
        
        Args:
            input_paths: List of input DICOM file paths
            output_dir: Directory to save processed files
            
        Returns:
            Combined FOIProcessingResult
        """
        os.makedirs(output_dir, exist_ok=True)
        
        combined_result = FOIProcessingResult(mode=self.mode)
        combined_result.success = True
        
        for input_path in input_paths:
            try:
                # Read DICOM
                ds = pydicom.dcmread(input_path, force=True)
                
                # Process
                ds, result = self.engine.process_dataset(
                    ds, self.mode, self.exclude_scanned
                )
                
                if result.success:
                    # Save processed file
                    filename = os.path.basename(input_path)
                    output_path = os.path.join(output_dir, filename)
                    ds.save_as(output_path)
                    
                    combined_result.files_processed += 1
                    combined_result.redactions.extend(result.redactions)
                    combined_result.hashes.extend([{
                        'name': filename,
                        **h
                    } for h in result.hashes])
                else:
                    combined_result.excluded_files.append(f"{input_path}: {result.error}")
                    
            except Exception as e:
                combined_result.warnings.append(f"Error processing {input_path}: {e}")
        
        return combined_result
