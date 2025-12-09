"""
VoxelMask Compliance Engine
==========================
Modular compliance processing for DICOM de-identification.

Supports:
- Internal Repair: Minimal changes, fix corrupted headers
- US Research (Safe Harbor): HIPAA 18 identifiers removal
- AU Strict (OAIC): Australian Privacy Principles compliance

Author: VoxelMask Team
"""

import hashlib
import random
from datetime import datetime, timedelta
from typing import Dict, Optional, Tuple, List
import pydicom
from pydicom.dataset import Dataset
from pydicom.sequence import Sequence
from pydicom.uid import generate_uid


# HIPAA Safe Harbor 18 Identifiers (mapped to DICOM tags where applicable)
HIPAA_SAFE_HARBOR_TAGS = [
    'PatientName',              # 1. Names
    'PatientAddress',           # 2. Geographic (address)
    'PatientBirthDate',         # 3. Dates (DOB - special handling for age)
    'AdmissionDate',
    'DischargeDate',
    'DateOfSecondaryCapture',
    'PatientTelephoneNumbers',  # 4. Phone numbers
    'ReferringPhysicianTelephoneNumbers',
    'OtherPatientIDs',          # 5. Fax (other IDs as catch-all)
    'PatientID',                # 6. Medical record numbers
    'AccessionNumber',          # 7. Health plan beneficiary numbers
    'FillerOrderNumberImagingServiceRequest',
    'PlacerOrderNumberImagingServiceRequest',
    'MilitaryRank',             # 8-18: Various identifiers
    'EthnicGroup',
    'PatientMotherBirthName',
    'ResponsiblePerson',
    'OperatorsName',
    'PerformingPhysicianName',
    'NameOfPhysiciansReadingStudy',
    'InstitutionName',          # Geographic subdivision
    'StationName',
    'InstitutionalDepartmentName',
    'RequestingPhysician',
    'ScheduledPerformingPhysicianName',
]

# Australian OAIC APP11 - Additional tags for strict compliance
OAIC_STRICT_TAGS = [
    'InstitutionName',          # Must be deleted
    'InstitutionAddress',
    'ReferringPhysicianName',   # Must be deleted
    'ReferringPhysicianAddress',
    'ReferringPhysicianTelephoneNumbers',
    'InstitutionalDepartmentName',
    'PhysiciansOfRecord',
    'PerformingPhysicianName',
    'OperatorsName',
    'PatientInsurancePlanCodeSequence',
]


class UIDManager:
    """Manages UID regeneration with referential integrity."""
    
    def __init__(self, seed: str = None):
        """
        Initialize UID manager.
        
        Args:
            seed: Optional seed for deterministic UID generation (e.g., PatientID)
        """
        self._study_uid_map: Dict[str, str] = {}
        self._series_uid_map: Dict[str, str] = {}
        self._instance_uid_map: Dict[str, str] = {}
        self._seed = seed
    
    def get_new_study_uid(self, original_uid: str) -> str:
        """Get or create new StudyInstanceUID, maintaining mapping."""
        if original_uid not in self._study_uid_map:
            self._study_uid_map[original_uid] = generate_uid()
        return self._study_uid_map[original_uid]
    
    def get_new_series_uid(self, original_uid: str) -> str:
        """Get or create new SeriesInstanceUID, maintaining mapping."""
        if original_uid not in self._series_uid_map:
            self._series_uid_map[original_uid] = generate_uid()
        return self._series_uid_map[original_uid]
    
    def get_new_instance_uid(self, original_uid: str) -> str:
        """Get or create new SOPInstanceUID (always unique per instance)."""
        if original_uid not in self._instance_uid_map:
            self._instance_uid_map[original_uid] = generate_uid()
        return self._instance_uid_map[original_uid]
    
    def get_mapping_summary(self) -> Dict:
        """Return summary of UID mappings for audit."""
        return {
            'studies_remapped': len(self._study_uid_map),
            'series_remapped': len(self._series_uid_map),
            'instances_remapped': len(self._instance_uid_map)
        }


class DicomComplianceManager:
    """
    Global Compliance Engine for DICOM de-identification.
    
    Supports multiple compliance profiles:
    - internal_repair: Minimal changes, fix corrupted headers
    - us_research_safe_harbor: HIPAA Safe Harbor (18 identifiers removed)
    - au_strict_oaic: Australian Privacy Principles (APP11)
    """
    
    PROFILE_INTERNAL_REPAIR = 'internal_repair'
    PROFILE_US_RESEARCH = 'us_research_safe_harbor'
    PROFILE_AU_STRICT = 'au_strict_oaic'
    
    def __init__(self):
        """Initialize the compliance manager."""
        self._uid_manager: Optional[UIDManager] = None
        self._date_shift_days: Optional[int] = None
        self._processing_log: List[str] = []
    
    def _log(self, message: str):
        """Add message to processing log."""
        timestamp = datetime.now().strftime("%H:%M:%S")
        self._processing_log.append(f"[{timestamp}] {message}")
    
    def get_processing_log(self) -> List[str]:
        """Return the processing log."""
        return self._processing_log.copy()
    
    def _calculate_date_shift(self, patient_id: str) -> int:
        """
        Calculate deterministic date shift based on PatientID.
        
        Args:
            patient_id: Patient identifier for seeding
            
        Returns:
            Number of days to shift (negative, between -14 and -100)
        """
        # Create deterministic seed from patient ID
        hash_val = hashlib.sha256(patient_id.encode()).hexdigest()
        seed_val = int(hash_val[:8], 16)
        random.seed(seed_val)
        return -random.randint(14, 100)
    
    def _shift_date(self, date_str: str, days: int) -> str:
        """
        Shift a DICOM date string by specified days.
        
        Args:
            date_str: Date in YYYYMMDD format
            days: Number of days to shift (negative = past)
            
        Returns:
            Shifted date in YYYYMMDD format
        """
        if not date_str or len(date_str) < 8:
            return date_str
        
        try:
            # Handle YYYYMMDD format
            original_date = datetime.strptime(date_str[:8], "%Y%m%d")
            shifted_date = original_date + timedelta(days=days)
            return shifted_date.strftime("%Y%m%d")
        except ValueError:
            return date_str  # Return unchanged if parsing fails
    
    def _hash_patient_id(self, patient_id: str) -> str:
        """
        Create a deterministic hash of PatientID for AU Strict mode.
        
        Args:
            patient_id: Original patient ID
            
        Returns:
            Hashed patient ID (first 12 chars of SHA256)
        """
        hash_val = hashlib.sha256(patient_id.encode()).hexdigest()
        return f"ANON_{hash_val[:12].upper()}"
    
    def _fix_corrupted_headers(self, ds: pydicom.Dataset) -> pydicom.Dataset:
        """
        Fix common DICOM header corruption issues.
        
        Args:
            ds: Input dataset
            
        Returns:
            Dataset with fixed headers
        """
        # Ensure TransferSyntaxUID is set
        if not hasattr(ds, 'file_meta'):
            ds.file_meta = pydicom.dataset.FileMetaDataset()
        
        if not hasattr(ds.file_meta, 'TransferSyntaxUID') or not ds.file_meta.TransferSyntaxUID:
            ds.file_meta.TransferSyntaxUID = pydicom.uid.ImplicitVRLittleEndian
            self._log("Fixed: Missing TransferSyntaxUID")
        
        # Ensure MediaStorageSOPClassUID is set
        if not hasattr(ds.file_meta, 'MediaStorageSOPClassUID') or not ds.file_meta.MediaStorageSOPClassUID:
            if hasattr(ds, 'SOPClassUID'):
                ds.file_meta.MediaStorageSOPClassUID = ds.SOPClassUID
                self._log("Fixed: Missing MediaStorageSOPClassUID")
        
        # Ensure MediaStorageSOPInstanceUID is set
        if not hasattr(ds.file_meta, 'MediaStorageSOPInstanceUID') or not ds.file_meta.MediaStorageSOPInstanceUID:
            if hasattr(ds, 'SOPInstanceUID'):
                ds.file_meta.MediaStorageSOPInstanceUID = ds.SOPInstanceUID
                self._log("Fixed: Missing MediaStorageSOPInstanceUID")
        
        return ds
    
    def _apply_us_kill_switch(self, ds: pydicom.Dataset) -> pydicom.Dataset:
        """
        Apply Ultrasound Kill-Switch: Set BurnedInAnnotation to NO for US modality.
        
        Args:
            ds: Input dataset
            
        Returns:
            Dataset with BurnedInAnnotation set if US modality
        """
        modality = str(getattr(ds, 'Modality', '')).upper()
        
        if modality == 'US':
            ds.BurnedInAnnotation = 'NO'  # (0028,0301)
            self._log("US Kill-Switch: BurnedInAnnotation set to NO")
        
        return ds
    
    def _regenerate_uids(self, ds: pydicom.Dataset) -> pydicom.Dataset:
        """
        Regenerate Study/Series/SOP Instance UIDs with referential integrity.
        
        Args:
            ds: Input dataset
            
        Returns:
            Dataset with regenerated UIDs
        """
        if not self._uid_manager:
            patient_id = str(getattr(ds, 'PatientID', ''))
            self._uid_manager = UIDManager(seed=patient_id)
        
        # Regenerate UIDs
        if hasattr(ds, 'StudyInstanceUID') and ds.StudyInstanceUID:
            old_study = str(ds.StudyInstanceUID)
            ds.StudyInstanceUID = self._uid_manager.get_new_study_uid(old_study)
            self._log(f"UID: StudyInstanceUID regenerated")
        
        if hasattr(ds, 'SeriesInstanceUID') and ds.SeriesInstanceUID:
            old_series = str(ds.SeriesInstanceUID)
            ds.SeriesInstanceUID = self._uid_manager.get_new_series_uid(old_series)
            self._log(f"UID: SeriesInstanceUID regenerated")
        
        if hasattr(ds, 'SOPInstanceUID') and ds.SOPInstanceUID:
            old_sop = str(ds.SOPInstanceUID)
            new_sop = self._uid_manager.get_new_instance_uid(old_sop)
            ds.SOPInstanceUID = new_sop
            if hasattr(ds, 'file_meta'):
                ds.file_meta.MediaStorageSOPInstanceUID = new_sop
            self._log(f"UID: SOPInstanceUID regenerated")
        
        return ds
    
    def _apply_internal_repair(self, ds: pydicom.Dataset) -> pydicom.Dataset:
        """
        Internal Repair Mode: Minimal changes, fix corrupted headers.
        Keep dates, names, and most identifiers intact.
        
        Args:
            ds: Input dataset
            
        Returns:
            Repaired dataset
        """
        self._log("Profile: Internal Repair - Minimal changes")
        
        # Just fix headers, don't remove any data
        ds = self._fix_corrupted_headers(ds)
        
        # Still apply US kill switch for safety
        ds = self._apply_us_kill_switch(ds)
        
        return ds
    
    def _apply_us_research_safe_harbor(self, ds: pydicom.Dataset) -> pydicom.Dataset:
        """
        US Research (HIPAA Safe Harbor) Mode:
        Remove 18 HIPAA identifiers, shift dates, keep Patient Year of Birth.
        
        Args:
            ds: Input dataset
            
        Returns:
            De-identified dataset
        """
        self._log("Profile: US Research (HIPAA Safe Harbor)")
        
        ds = self._fix_corrupted_headers(ds)
        ds = self._apply_us_kill_switch(ds)
        
        # Remove private tags
        ds.remove_private_tags()
        self._log("Removed: Private tags")
        
        # Calculate date shift based on PatientID (deterministic per patient)
        patient_id = str(getattr(ds, 'PatientID', 'UNKNOWN'))
        self._date_shift_days = self._calculate_date_shift(patient_id)
        self._log(f"Date shift: {self._date_shift_days} days")
        
        # Initialize UID manager for consistent UID handling
        if not self._uid_manager:
            self._uid_manager = UIDManager(seed=patient_id)
        
        # Shift all date fields BEFORE removing identifiers
        date_tags = [
            'StudyDate', 'SeriesDate', 'AcquisitionDate', 'ContentDate',
            'InstanceCreationDate', 'PerformedProcedureStepStartDate',
            'AdmissionDate', 'DischargeDate', 'DateOfSecondaryCapture'
        ]
        
        for tag_name in date_tags:
            if hasattr(ds, tag_name) and getattr(ds, tag_name):
                original_date = str(getattr(ds, tag_name))
                shifted_date = self._shift_date(original_date, self._date_shift_days)
                setattr(ds, tag_name, shifted_date)
                self._log(f"Shifted: {tag_name}")
        
        # Regenerate UIDs for research de-identification
        if hasattr(ds, 'StudyInstanceUID') and ds.StudyInstanceUID:
            old_study = str(ds.StudyInstanceUID)
            ds.StudyInstanceUID = self._uid_manager.get_new_study_uid(old_study)
            self._log("UID: StudyInstanceUID regenerated")
        
        if hasattr(ds, 'SeriesInstanceUID') and ds.SeriesInstanceUID:
            old_series = str(ds.SeriesInstanceUID)
            ds.SeriesInstanceUID = self._uid_manager.get_new_series_uid(old_series)
            self._log("UID: SeriesInstanceUID regenerated")
        
        if hasattr(ds, 'SOPInstanceUID') and ds.SOPInstanceUID:
            old_sop = str(ds.SOPInstanceUID)
            new_sop = self._uid_manager.get_new_instance_uid(old_sop)
            ds.SOPInstanceUID = new_sop
            if hasattr(ds, 'file_meta'):
                ds.file_meta.MediaStorageSOPInstanceUID = new_sop
            self._log("UID: SOPInstanceUID regenerated")
        
        # Remove HIPAA Safe Harbor identifiers
        removed_count = 0
        for tag_name in HIPAA_SAFE_HARBOR_TAGS:
            if hasattr(ds, tag_name):
                # Special handling for PatientBirthDate - keep year only
                if tag_name == 'PatientBirthDate':
                    birth_date = str(getattr(ds, tag_name, ''))
                    if len(birth_date) >= 4:
                        # Keep year, zero out month/day
                        ds.PatientBirthDate = birth_date[:4] + '0101'
                        self._log(f"Modified: PatientBirthDate -> Year only")
                    continue
                
                # Delete all other identifiers
                delattr(ds, tag_name)
                removed_count += 1
        
        self._log(f"Removed: {removed_count} HIPAA identifiers")
        
        # Set compliance tags
        ds.PatientIdentityRemoved = 'YES'
        ds.DeidentificationMethod = 'HIPAA_SAFE_HARBOR | DATE_SHIFT | UID_REGEN | VOXELMASK'
        
        # Add De-identification Method Code Sequence
        deid_code = Dataset()
        deid_code.CodeValue = "113100"
        deid_code.CodingSchemeDesignator = "DCM"
        deid_code.CodeMeaning = "De-identification"
        ds.DeidentificationMethodCodeSequence = Sequence([deid_code])
        
        return ds

    
    def _apply_au_strict_oaic(self, ds: pydicom.Dataset) -> pydicom.Dataset:
        """
        AU Strict (OAIC APP11) Mode:
        Australian Privacy Principles compliance.
        - Delete InstitutionName, ReferringPhysicianName
        - Shift all dates (-14 to -100 days, seeded by PatientID)
        - Hash PatientID
        
        Args:
            ds: Input dataset
            
        Returns:
            De-identified dataset
        """
        self._log("Profile: AU Strict (OAIC APP11)")
        
        ds = self._fix_corrupted_headers(ds)
        ds = self._apply_us_kill_switch(ds)
        
        # Remove private tags
        ds.remove_private_tags()
        self._log("Removed: Private tags")
        
        # Calculate date shift based on PatientID
        patient_id = str(getattr(ds, 'PatientID', 'UNKNOWN'))
        self._date_shift_days = self._calculate_date_shift(patient_id)
        self._log(f"Date shift: {self._date_shift_days} days")
        
        # Hash PatientID
        if hasattr(ds, 'PatientID') and ds.PatientID:
            ds.PatientID = self._hash_patient_id(patient_id)
            self._log("Hashed: PatientID")
        
        # Remove OAIC-specific tags
        removed_count = 0
        for tag_name in OAIC_STRICT_TAGS:
            if hasattr(ds, tag_name):
                delattr(ds, tag_name)
                removed_count += 1
        
        self._log(f"Removed: {removed_count} OAIC identifiers")
        
        # Also remove HIPAA identifiers
        for tag_name in HIPAA_SAFE_HARBOR_TAGS:
            if hasattr(ds, tag_name) and tag_name not in ['PatientID']:  # Already hashed
                if tag_name == 'PatientBirthDate':
                    # Keep year only for age calculation
                    birth_date = str(getattr(ds, tag_name, ''))
                    if len(birth_date) >= 4:
                        ds.PatientBirthDate = birth_date[:4] + '0101'
                    continue
                delattr(ds, tag_name)
        
        # Shift all date fields
        date_tags = [
            'StudyDate', 'SeriesDate', 'AcquisitionDate', 'ContentDate',
            'InstanceCreationDate', 'PerformedProcedureStepStartDate',
            'AdmissionDate', 'DischargeDate'
        ]
        
        for tag_name in date_tags:
            if hasattr(ds, tag_name) and getattr(ds, tag_name):
                original_date = str(getattr(ds, tag_name))
                shifted_date = self._shift_date(original_date, self._date_shift_days)
                setattr(ds, tag_name, shifted_date)
                self._log(f"Shifted: {tag_name}")
        
        # Set compliance tags
        ds.PatientIdentityRemoved = 'YES'
        ds.DeidentificationMethod = 'OAIC_APP11 | ADELAIDE_PACS_SCRUBBER | VOXELMASK'
        
        # Add De-identification Method Code Sequence
        deid_code = Dataset()
        deid_code.CodeValue = "113100"
        deid_code.CodingSchemeDesignator = "DCM"
        deid_code.CodeMeaning = "De-identification"
        ds.DeidentificationMethodCodeSequence = Sequence([deid_code])
        
        return ds
    
    def process_dataset(
        self,
        dataset: pydicom.Dataset,
        profile_mode: str,
        fix_uids: bool = False
    ) -> Tuple[pydicom.Dataset, Dict]:
        """
        Process a DICOM dataset according to the specified compliance profile.
        
        Args:
            dataset: Input pydicom Dataset
            profile_mode: One of 'internal_repair', 'us_research_safe_harbor', 'au_strict_oaic'
            fix_uids: If True, regenerate Study/Series/SOP Instance UIDs
            
        Returns:
            Tuple of (processed_dataset, processing_info)
        """
        self._processing_log = []  # Reset log for this dataset
        
        self._log(f"Processing started: {profile_mode}")
        
        # Apply profile-specific processing
        if profile_mode == self.PROFILE_INTERNAL_REPAIR:
            dataset = self._apply_internal_repair(dataset)
        elif profile_mode == self.PROFILE_US_RESEARCH:
            dataset = self._apply_us_research_safe_harbor(dataset)
        elif profile_mode == self.PROFILE_AU_STRICT:
            dataset = self._apply_au_strict_oaic(dataset)
        else:
            self._log(f"Unknown profile: {profile_mode}, using internal_repair")
            dataset = self._apply_internal_repair(dataset)
        
        # UID regeneration (optional, for fixing SOP/duplicate blocks)
        if fix_uids:
            dataset = self._regenerate_uids(dataset)
        
        self._log("Processing complete")
        
        # Build processing info
        processing_info = {
            'profile': profile_mode,
            'fix_uids': fix_uids,
            'date_shift_days': self._date_shift_days,
            'uid_mapping': self._uid_manager.get_mapping_summary() if self._uid_manager else None,
            'log': self.get_processing_log()
        }
        
        return dataset, processing_info


# Convenience function for quick processing
def apply_compliance(
    dataset: pydicom.Dataset,
    profile: str = 'internal_repair',
    fix_uids: bool = False
) -> Tuple[pydicom.Dataset, Dict]:
    """
    Convenience function to apply compliance processing.
    
    Args:
        dataset: Input pydicom Dataset
        profile: Compliance profile name
        fix_uids: Whether to regenerate UIDs
        
    Returns:
        Tuple of (processed_dataset, processing_info)
    """
    manager = DicomComplianceManager()
    return manager.process_dataset(dataset, profile, fix_uids)
