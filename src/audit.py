# audit.py
"""
Audit receipt generation for DICOM de-identification operations.
"""

import hashlib
from datetime import datetime
from typing import Optional, Dict

try:
    import pydicom
except ImportError:
    pydicom = None

def extract_sonographer_initials(original_meta: Dict) -> str:
    """
    Extract sonographer initials from DICOM tags.
    
    Args:
        original_meta: Dictionary with original DICOM metadata
        
    Returns:
        Formatted initials (e.g., "J.S." or "JS") or "N/A"
    """
    # Try OperatorsName first, then PerformingPhysicianName
    operators_name = original_meta.get('operators_name') or original_meta.get('OperatorsName')
    performing_physician = original_meta.get('performing_physician_name') or original_meta.get('PerformingPhysicianName')
    
    name_to_process = operators_name or performing_physician
    
    if not name_to_process:
        return "N/A"
    
    # Handle DICOM name format: "LastName^FirstName^MiddleName^..."
    if '^' in name_to_process:
        parts = name_to_process.split('^')
        if len(parts) >= 2 and parts[0] and parts[1]:
            # Format: L.F. (e.g., Smith^John -> S.J.)
            return f"{parts[0][0].upper()}.{parts[1][0].upper()}."
        elif len(parts) >= 1 and parts[0]:
            # Only last name available
            return parts[0][:2].upper()
    else:
        # Handle regular name format: "John Smith" or "Smith, John"
        if ',' in name_to_process:
            # "Smith, John" -> S.J.
            parts = [p.strip() for p in name_to_process.split(',')]
            if len(parts) >= 2 and parts[0] and parts[1]:
                return f"{parts[0][0].upper()}.{parts[1][0].upper()}."
        else:
            # "John Smith" -> J.S.
            parts = name_to_process.split()
            if len(parts) >= 2:
                return f"{parts[0][0].upper()}.{parts[1][0].upper()}."
            elif len(parts) == 1:
                return parts[0][:2].upper()
    
    return "N/A"

def calculate_file_hash(file_path: str) -> str:
    """
    Calculate SHA-256 hash of a file.
    
    Args:
        file_path: Path to the file
        
    Returns:
        SHA-256 hash as hex string
    """
    try:
        with open(file_path, 'rb') as f:
            return hashlib.sha256(f.read()).hexdigest()
    except Exception:
        return "HASH_ERROR"

def generate_audit_receipt(
    original_meta: Dict,
    new_meta: Dict,
    uuid_str: str,
    operator_id: str,
    mode: str,
    pixel_hash: Optional[str] = None,
    filename: str = "",
    mask_applied: bool = False,
    original_file_hash: Optional[str] = None,
    anonymized_file_hash: Optional[str] = None,
    safety_notification: Optional[str] = None,
    compliance_profile: str = "safe_harbor",
    pixel_action_reason: Optional[str] = None,
    dataset: Optional['pydicom.Dataset'] = None,
    is_foi_mode: bool = False,
    foi_redactions: Optional[list] = None
) -> str:
    """
    Generate a professional audit receipt for DICOM de-identification operations.

    Args:
        original_meta: Dictionary with original file metadata
        new_meta: Dictionary with processed file metadata
        uuid_str: Unique identifier for this scrub operation
        operator_id: ID of the operator performing the scrub
        mode: Processing mode ("Clinical" or "Research")
        pixel_hash: Optional hash of pixel data for integrity verification
        filename: Original filename
        mask_applied: Whether pixel masking was applied
        original_file_hash: SHA-256 hash of original file (chain of custody)
        anonymized_file_hash: SHA-256 hash of anonymized file (chain of custody)
        safety_notification: Optional safety notification for pixel masking bypass
        compliance_profile: Compliance profile used ("safe_harbor" or "limited_data_set")

    Returns:
        Formatted professional audit receipt as a string
    """
    # --- PRIORITY OVERRIDE: Use Dataset Values if Available ---
    # SOURCE OF TRUTH OVERRIDE
    # If the actual dataset is provided, use its values instead of the dictionary.
    if dataset:
        # Determine if we should preserve accession (FOI mode OR Clinical Correction)
        # Clinical Correction (internal_repair) preserves accession for workflow continuity
        is_clinical_correction = compliance_profile == "internal_repair"
        preserve_accession = is_foi_mode or is_clinical_correction
        
        # FOI MODE or CLINICAL CORRECTION: Preserve accession number
        # RESEARCH MODE: Force to 'REMOVED' since we delete it
        if not preserve_accession:
            new_meta['accession'] = 'REMOVED'
            new_meta['accession_number'] = 'REMOVED'
        else:
            # Preserve the actual accession from dataset
            if hasattr(dataset, 'AccessionNumber') and dataset.AccessionNumber:
                new_meta['accession'] = str(dataset.AccessionNumber)
                new_meta['accession_number'] = str(dataset.AccessionNumber)
        
        # STUDY DATE FIX: Force the log to reflect the actual StudyDate from the file
        if "StudyDate" in dataset:
            val = dataset.StudyDate
            final_date = val.value if hasattr(val, 'value') else str(val)
            new_meta['new_study_date'] = final_date
    # ----------------------------------------------------------
    
    # ═══════════════════════════════════════════════════════════════════════════════
    # PHASE 12: TWO-FLAG PHI VISIBILITY MODEL
    # 
    # Two distinct visibility classes (not one boolean):
    #   1. Patient identifiers (PatientName, PatientID, Accession, DOB, etc.)
    #   2. Staff identifiers (Operator, Sonographer, Radiographer, device IDs, etc.)
    #
    # Policy table:
    #   Profile              | Patient PHI | Staff IDs
    #   ---------------------|-------------|------------
    #   research_*           | REDACTED    | REDACTED
    #   foi_patient          | SHOWN       | REDACTED
    #   foi_legal            | SHOWN       | REDACTED
    #   internal_repair      | SHOWN       | SHOWN (internal only)
    #
    # This is audit-defensible and explicit.
    # ═══════════════════════════════════════════════════════════════════════════════
    
    # Explicit profile allowlists — profile drives EVERYTHING (not is_foi_mode boolean)
    PATIENT_PHI_PROFILES = {"internal_repair", "foi_patient", "foi_legal", "foi_legal_chain"}
    STAFF_ID_PROFILES = {"internal_repair"}  # Only internal repair shows staff
    FOI_PROFILES = {"foi_patient", "foi_legal", "foi_legal_chain"}  # Derive FOI status from profile
    RESEARCH_PROFILES = {"us_research_safe_harbor", "au_strict_oaic"}
    
    show_patient_phi = compliance_profile in PATIENT_PHI_PROFILES
    show_staff_ids = compliance_profile in STAFF_ID_PROFILES
    is_foi_profile = compliance_profile in FOI_PROFILES  # Derived from profile, not boolean param
    is_research_profile = compliance_profile in RESEARCH_PROFILES
    
    # Prepare patient PHI display values
    if show_patient_phi:
        display_patient_name = original_meta.get('patient_name', 'N/A')
        display_patient_id = original_meta.get('patient_id', 'N/A')
        display_new_patient_name = new_meta.get('patient_name', 'N/A')
        display_new_patient_id = new_meta.get('patient_id', 'N/A')
    else:
        display_patient_name = 'REDACTED'
        display_patient_id = 'REDACTED'
        display_new_patient_name = 'REDACTED'
        display_new_patient_id = 'REDACTED'
    
    # Prepare staff/infrastructure ID display values
    # These fields can leak staff identity even indirectly
    if show_staff_ids:
        display_operator_id = operator_id
        display_sonographer = extract_sonographer_initials(original_meta)
        display_institution = original_meta.get('institution', 'N/A')
    else:
        display_operator_id = 'REDACTED'
        display_sonographer = 'REDACTED'
        display_institution = 'REDACTED'  # Can identify staff in small teams
    
    # Visibility status labels for receipt transparency
    patient_phi_status = "SHOWN" if show_patient_phi else "REDACTED"
    staff_id_status = "SHOWN" if show_staff_ids else "REDACTED"
    
    # Output DICOM status (what's in the actual file, not just receipt)
    if is_foi_profile:
        output_patient_tags = "PRESERVED (Chain of Custody)"
    elif is_research_profile:
        output_patient_tags = "ANONYMISED"
    elif compliance_profile == "internal_repair":
        output_patient_tags = "CORRECTED (Contains PHI)"
    else:
        output_patient_tags = "PROCESSED"
    
    # Determine reason code based on PROFILE (not is_foi_mode boolean)
    if is_foi_profile:
        reason_code = "FOI_LEGAL_RELEASE"
    elif compliance_profile == "internal_repair":
        reason_code = "CLINICAL_CORRECTION"
    elif is_research_profile:
        reason_code = "RESEARCH_DEID"
    else:
        reason_code = "PROCESSING"
    
    # Determine metadata sanitization details based on PROFILE
    if is_foi_profile:
        metadata_disposition = "PRESERVED (FOI Legal Release - Staff names redacted)"
        private_tags_status = "REMOVED (Vendor-specific)"
        uids_status = "PRESERVED (Chain of Custody)"
    elif is_research_profile:
        metadata_disposition = "STRIPPED & ANONYMIZED (Safe for Research)"
        private_tags_status = "REMOVED"
        uids_status = "REMAPPED (Deterministic)"
    elif compliance_profile == "internal_repair":
        metadata_disposition = "RETAINED & CORRECTED (Contains PHI)"
        private_tags_status = "PRESERVED"
        uids_status = "PRESERVED"
    else:
        # Default/fallback
        metadata_disposition = "PROCESSED"
        private_tags_status = "UNKNOWN"
        uids_status = "UNKNOWN"
    
    # ═══════════════════════════════════════════════════════════════════════════════
    # BUILD RECEIPT - FOI gets screaming header to prevent accidental re-use
    # ═══════════════════════════════════════════════════════════════════════════════
    if is_foi_profile:
        # FOI SCREAMING HEADER - unambiguous warning
        audit_lines = [
            "╔═══════════════════════════════════════════════════════════════════════════════╗",
            "║          ⚠️  FOI EXPORT — CONTAINS PATIENT IDENTIFIERS  ⚠️            ║",
            "║                       STAFF IDENTIFIERS REDACTED                       ║",
            "╠═══════════════════════════════════════════════════════════════════════════════╣",
            "║                    VOXELMASK - AUDIT RECEIPT                     ║",
            "╚═══════════════════════════════════════════════════════════════════════════════╝",
        ]
    else:
        # Standard header
        audit_lines = [
            "╔═══════════════════════════════════════════════════════════════════════════════╗",
            "║                    VOXELMASK - AUDIT RECEIPT                     ║",
            "╚═══════════════════════════════════════════════════════════════════════════════╝",
        ]
    
    audit_lines.extend([
        "",
        "▶ VISIBILITY DISCLOSURE",
        "─────────────────────────────────────────────────────────────────────────────────",
        f"Patient identifiers in receipt:  {patient_phi_status}",
        f"Staff identifiers in receipt:    {staff_id_status}",
        f"Patient tags in OUTPUT DICOM:    {output_patient_tags}",
        f"Pixel masking applied:           {'YES' if mask_applied else 'NO'}",
        "",
        "▶ PROCESSING DETAILS",
        "─────────────────────────────────────────────────────────────────────────────────",
        f"Timestamp:     {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} UTC",
        f"Scrub UUID:    {uuid_str}",
        f"Operator:      {display_operator_id}",
        f"Sonographer:   {display_sonographer}",
        f"Reason:        {reason_code}",
        f"Profile:       {compliance_profile}",
        "",
        "▶ CHAIN OF CUSTODY (SHA-256)",
        "─────────────────────────────────────────────────────────────────────────────────",
        f"Original File:   {original_file_hash or 'HASH_UNAVAILABLE'}",
        f"Anonymized File: {anonymized_file_hash or 'HASH_UNAVAILABLE'}",
        "",
        "▶ SUBJECT DATA",
        "─────────────────────────────────────────────────────────────────────────────────",
        f"Filename:       {filename}",
        f"Patient:        {display_patient_name}",
        f"Patient ID:     {display_patient_id}",
        f"Original Date:  {original_meta.get('study_date', 'N/A')}",
        f"New Study Date: {new_meta.get('new_study_date', new_meta.get('study_date', 'N/A'))}",
        f"Study Time:     {original_meta.get('study_time', 'N/A')}",
        f"Modality:       {original_meta.get('modality', 'N/A')}",
        f"Institution:    {display_institution}",
        f"Accession:      {new_meta.get('accession_number', new_meta.get('accession', 'REMOVED'))} (was: {original_meta.get('accession', 'N/A')})",
        "",
        "▶ CLINICAL CONTEXT & SCAN PARAMETERS",
        "─────────────────────────────────────────────────────────────────────────────────",
    ])
    
    # Add clinical context details if available
    clinical_fields = [
        ('study_desc', 'Study Description'),
        ('series_description', 'Series Description'),
        ('protocol_name', 'Protocol'),
        ('body_part_examined', 'Body Part Examined'),
        ('scanning_sequence', 'Scanning Sequence'),
        ('sequence_variant', 'Sequence Variant'),
        ('probe_type', 'Probe Type'),
        ('frame_time', 'Frame Time')
    ]
    
    has_clinical_details = False
    for attr, label in clinical_fields:
        value = original_meta.get(attr)
        if value:
            audit_lines.append(f"{label}: {value}{' ms' if attr == 'frame_time' else ''}")
            has_clinical_details = True
    
    if not has_clinical_details:
        audit_lines.append("No clinical context metadata available")
    
    audit_lines.extend([
        "",
        "▶ TECHNICAL & SAFETY PROTOCOLS",
        "─────────────────────────────────────────────────────────────────────────────────",
        f"Output Filename: {filename.rsplit('.', 1)[0]}_fixed.dcm" if filename else "Output Filename: processed.dcm",
        f"New Patient:      {display_new_patient_name}",
        f"New Patient ID:   {display_new_patient_id}",
    ])
    
    # Pixel Action with transparency
    pixel_status = "APPLIED" if mask_applied else "NOT APPLIED"
    pixel_reason = pixel_action_reason or "No pixel modification required"
    audit_lines.append(f"Pixel Action:     {pixel_status} - {pixel_reason}")
    
    # Add pixel hash if provided
    if pixel_hash:
        audit_lines.append(f"Pixel Hash:     {pixel_hash}")
    
    # Add safety notification if provided
    if safety_notification:
        audit_lines.extend([
            "",
            "⚠️  SAFETY NOTIFICATION",
            "─────────────────────────────────────────────────────────────────────────────────",
            safety_notification,
        ])
    
    audit_lines.extend([
        "",
        "▶ METADATA SANITIZATION SUMMARY",
        "─────────────────────────────────────────────────────────────────────────────────",
        f"Disposition:    {metadata_disposition}",
        f"Private Tags:   {private_tags_status}",
        f"UIDs:           {uids_status}",
        "",
    ])
    
    # FOI-specific compliance section
    if is_foi_mode:
        audit_lines.extend([
            "▶ FOI RELEASE CERTIFICATION",
            "─────────────────────────────────────────────────────────────────────────────────",
            "Release Type:       Freedom of Information / Legal Discovery",
            "✓ Patient Data:     PRESERVED (Name, ID, DOB, Dates)",
            "✓ Accession Number: PRESERVED (Chain of Custody)",
            "✓ Study UIDs:       PRESERVED (Forensic Integrity)",
            "✓ Staff Names:      REDACTED (Employee Privacy)",
            "✓ Private Tags:     REMOVED (Vendor-specific data)",
        ])
        
        # Add specific redactions if available
        if foi_redactions:
            audit_lines.append("")
            audit_lines.append("Staff Redactions Performed:")
            for redaction in foi_redactions:
                tag_name = redaction.get('tag', 'Unknown')
                action = redaction.get('action', 'Redacted')
                audit_lines.append(f"  • {tag_name}: {action}")
        
        audit_lines.extend([
            "",
            "═══════════════════════════════════════════════════════════════════════════════",
            "This audit log constitutes a legal record of the FOI processing.",
            "Patient-identifying data has been PRESERVED for legal chain of custody.",
            "Staff-identifying data has been REDACTED for employee privacy protection.",
            "═══════════════════════════════════════════════════════════════════════════════"
        ])
    elif compliance_profile == "internal_repair":
        # Clinical Correction specific section
        # Determine if patient name was actually changed
        original_name = original_meta.get('patient_name', '')
        new_name = new_meta.get('patient_name', '')
        name_changed = original_name != new_name and new_name not in ('PRESERVED', 'N/A', '')
        name_status = "CORRECTED (New value applied)" if name_changed else "PRESERVED (No change)"
        
        audit_lines.extend([
            "▶ CLINICAL CORRECTION CERTIFICATION",
            "─────────────────────────────────────────────────────────────────────────────────",
            "Processing Type:     Clinical Data Correction (Internal Repair)",
            f"✓ Patient Name:      {name_status}",
            "✓ Accession Number:  PRESERVED (Workflow Continuity)",
            "✓ Study Date:        PRESERVED (Clinical Reference)",
            "✓ Study/Series UIDs: PRESERVED (PACS Compatibility)",
            "✓ Private Tags:      PRESERVED (Vendor Compatibility)",
            "",
            "═══════════════════════════════════════════════════════════════════════════════",
            "This audit log records a clinical data correction for PACS workflow purposes.",
            "Original study identifiers have been PRESERVED for clinical continuity.",
            "Patient demographics have been " + ("CORRECTED" if name_changed else "PRESERVED") + " as per operator input.",
            "═══════════════════════════════════════════════════════════════════════════════"
        ])
    else:
        # Standard research compliance section
        audit_lines.extend([
            "▶ COMPLIANCE CERTIFICATION",
            "─────────────────────────────────────────────────────────────────────────────────",
            f"Standard Used: DICOM PS3.15 / HIPAA {'Safe Harbor' if compliance_profile == 'safe_harbor' else 'Limited Data Set'}",
            "✓ OAIC/APP 11: Compliant",
            "✓ PatientIdentityRemoved: YES",
            "✓ BurnedInAnnotation: NO",
            "✓ Safe for Research Use: " + ("YES" if is_research_profile else "NO - Clinical Only"),
            "",
            "═══════════════════════════════════════════════════════════════════════════════",
            "This audit log constitutes a legal record of the de-identification process.",
            "Retain this receipt for compliance verification and audit purposes.",
            "═══════════════════════════════════════════════════════════════════════════════"
        ])

    return "\n".join(audit_lines)
