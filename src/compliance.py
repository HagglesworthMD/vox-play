# compliance.py
import pydicom
from pydicom.dataset import Dataset
from pydicom.sequence import Sequence
from typing import Optional, Dict
from datetime import datetime

# Application constants
APP_VERSION = "0.3.0"
MANUFACTURER = "SAMI_Support_Dev"

def enforce_dicom_compliance(ds: pydicom.Dataset, 
                           mode: str, 
                           new_details: Optional[Dict] = None,
                           operator_id: str = "WEBAPP_USER",
                           reason_code: str = "CLINICAL_CORRECTION",
                           scrub_uuid: str = None) -> pydicom.Dataset:
    """
    Enforces DICOM compliance standards on a dataset according to specified mode.
    
    Args:
        ds: Input pydicom Dataset to modify
        mode: Either "Clinical" (name correction) or "Research" (full de-id)
        new_details: Dictionary containing new patient details for Clinical mode
            Expected keys for Clinical mode:
            - patient_name: New patient name
            - patient_id: New patient ID
            - patient_dob: New date of birth (YYYY-MM-DD format)
            - institution: New institution name
        operator_id: ID of the operator performing the scrub (for audit tags)
        reason_code: Reason for the scrub operation (for audit tags)
        scrub_uuid: Unique identifier for this scrub event (for audit tags)
            
    Returns:
        Modified pydicom Dataset with compliance tags
    """
    # Standard DICOM de-identification steps
    ds.remove_private_tags()
    
    # PS3.15 Compliance Tags
    ds.PatientIdentityRemoved = 'YES'  # (0012,0062)
    
    # Build comprehensive de-identification method string
    audit_parts = ["OAIC_APP11", "ADELAIDE_PACS_SCRUBBER"]
    if operator_id:
        audit_parts.append(f"OP:{operator_id}")
    if scrub_uuid:
        audit_parts.append(f"UUID:{scrub_uuid}")
    ds.DeidentificationMethod = " | ".join(audit_parts)  # (0012,0063)
    
    # BurnedInAnnotation (0028,0301) - assert pixel scrub is complete
    ds.BurnedInAnnotation = "NO"
    
    # Add ContributingEquipmentSequence for audit trail
    contributing_equipment = Dataset()
    contributing_equipment.Manufacturer = MANUFACTURER
    contributing_equipment.InstitutionName = "VoxelMask PACS Scrubber"
    contributing_equipment.StationName = "PACS_SCRUBBER"
    contributing_equipment.SoftwareVersions = APP_VERSION
    contributing_equipment.ContributionDateTime = datetime.now().strftime("%Y%m%d%H%M%S")
    contributing_equipment.ContributionDescription = f"De-identification: {reason_code}"
    
    # Purpose of Reference Code Sequence - DICOM Code 113100 (De-identification)
    purpose_code = Dataset()
    purpose_code.CodeValue = "113100"
    purpose_code.CodingSchemeDesignator = "DCM"
    purpose_code.CodeMeaning = "De-identification"
    contributing_equipment.PurposeOfReferenceCodeSequence = Sequence([purpose_code])
    
    # Append to existing sequence or create new one
    if hasattr(ds, 'ContributingEquipmentSequence') and ds.ContributingEquipmentSequence:
        ds.ContributingEquipmentSequence.append(contributing_equipment)
    else:
        ds.ContributingEquipmentSequence = Sequence([contributing_equipment])
    
    # Add De-identification Method Code Sequence
    deid_code = Dataset()
    deid_code.CodeValue = "113100"
    deid_code.CodingSchemeDesignator = "DCM"
    deid_code.CodeMeaning = "De-identification"
    
    if hasattr(ds, 'DeidentificationMethodCodeSequence') and ds.DeidentificationMethodCodeSequence:
        ds.DeidentificationMethodCodeSequence.append(deid_code)
    else:
        ds.DeidentificationMethodCodeSequence = Sequence([deid_code])
    
    # Mode-specific processing
    if mode.upper() == "RESEARCH":
        # Full de-identification for research
        phi_fields = [
            'PatientName', 'PatientID', 'PatientBirthDate',
            'InstitutionName', 'ReferringPhysicianName',
            'OperatorsName', 'OtherPatientIDs', 'PatientAddress',
            'PatientTelephoneNumbers', 'MilitaryRank', 'EthnicGroup',
            'PatientMotherBirthName', 'ResponsiblePerson'
        ]
        
        for field in phi_fields:
            if hasattr(ds, field):
                setattr(ds, field, "")
        
        # Note: AccessionNumber is now handled by apply_deterministic_sanitization
                
    elif mode.upper() == "CLINICAL" and new_details:
        # Targeted correction for clinical use
        if new_details.get('patient_name'):
            ds.PatientName = new_details['patient_name']
        if new_details.get('patient_id'): 
            ds.PatientID = new_details['patient_id']
        if new_details.get('patient_dob'):
            ds.PatientBirthDate = new_details['patient_dob']
        if new_details.get('institution'):
            ds.InstitutionName = new_details['institution']
        # Note: AccessionNumber is now handled by apply_deterministic_sanitization
    
    return ds
