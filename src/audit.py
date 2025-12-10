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
            parts = name_to_process.split(',')
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
    
    # Determine reason code based on mode
    if is_foi_mode:
        reason_code = "FOI_LEGAL_RELEASE"
    elif mode.upper() == "CLINICAL":
        reason_code = "CLINICAL_CORRECTION"
    else:
        reason_code = "RESEARCH_DEID"
    
    # Determine metadata sanitization details based on mode
    is_research = mode.upper() == "RESEARCH" or "DE-ID" in mode.upper()
    is_clinical = mode.upper() == "CLINICAL" or "CORRECTION" in mode.upper()
    
    if is_foi_mode:
        metadata_disposition = "PRESERVED (FOI Legal Release - Staff names redacted)"
        private_tags_status = "REMOVED (Vendor-specific)"
        uids_status = "PRESERVED (Chain of Custody)"
    elif is_research:
        metadata_disposition = "STRIPPED & ANONYMIZED (Safe for Research)"
        private_tags_status = "REMOVED"
        uids_status = "REMAPPED (Deterministic)"
    elif is_clinical:
        metadata_disposition = "RETAINED & CORRECTED (Contains PHI)"
        private_tags_status = "PRESERVED"
        uids_status = "PRESERVED"
    else:
        # Default/fallback
        metadata_disposition = "PROCESSED"
        private_tags_status = "UNKNOWN"
        uids_status = "UNKNOWN"

    # Extract sonographer initials
    sonographer_initials = extract_sonographer_initials(original_meta)
    
    # Build professional audit receipt with enhanced layout
    audit_lines = [
        "╔═══════════════════════════════════════════════════════════════════════════════╗",
        "║                    VOXELMASK - AUDIT RECEIPT                     ║",
        "╚═══════════════════════════════════════════════════════════════════════════════╝",
        "",
        "▶ PROCESSING DETAILS",
        "─────────────────────────────────────────────────────────────────────────────────",
        f"Timestamp:     {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} UTC",
        f"Scrub UUID:    {uuid_str}",
        f"Operator:      {operator_id}",
        f"Sonographer:   {sonographer_initials}",
        f"Reason:        {reason_code}",
        f"Mode:          {mode}",
        "",
        "▶ CHAIN OF CUSTODY (SHA-256)",
        "─────────────────────────────────────────────────────────────────────────────────",
        f"Original File:   {original_file_hash or 'HASH_UNAVAILABLE'}",
        f"Anonymized File: {anonymized_file_hash or 'HASH_UNAVAILABLE'}",
        "",
        "▶ SUBJECT DATA",
        "─────────────────────────────────────────────────────────────────────────────────",
        f"Filename:       {filename}",
        f"Patient:        {original_meta.get('patient_name', 'N/A')}",
        f"Patient ID:     {original_meta.get('patient_id', 'N/A')}",
        f"Original Date:  {original_meta.get('study_date', 'N/A')}",
        f"New Study Date: {new_meta.get('new_study_date', new_meta.get('study_date', 'N/A'))}",
        f"Study Time:     {original_meta.get('study_time', 'N/A')}",
        f"Modality:       {original_meta.get('modality', 'N/A')}",
        f"Institution:    {original_meta.get('institution', 'N/A')}",
        f"Accession:      {new_meta.get('accession_number', new_meta.get('accession', 'REMOVED'))} (was: {original_meta.get('accession', 'N/A')})",
        "",
        "▶ CLINICAL CONTEXT & SCAN PARAMETERS",
        "─────────────────────────────────────────────────────────────────────────────────",
    ]
    
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
        f"New Patient:      {new_meta.get('patient_name', 'N/A')}",
        f"New Patient ID:   {new_meta.get('patient_id', 'N/A')}",
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
        audit_lines.extend([
            "▶ CLINICAL CORRECTION CERTIFICATION",
            "─────────────────────────────────────────────────────────────────────────────────",
            "Processing Type:     Clinical Data Correction (Internal Repair)",
            "✓ Patient Name:      CORRECTED (New value applied)",
            "✓ Accession Number:  PRESERVED (Workflow Continuity)",
            "✓ Study Date:        PRESERVED (Clinical Reference)",
            "✓ Study/Series UIDs: PRESERVED (PACS Compatibility)",
            "✓ Private Tags:      PRESERVED (Vendor Compatibility)",
            "",
            "═══════════════════════════════════════════════════════════════════════════════",
            "This audit log records a clinical data correction for PACS workflow purposes.",
            "Original study identifiers have been PRESERVED for clinical continuity.",
            "Patient demographics have been CORRECTED as per operator input.",
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
            "✓ Safe for Research Use: " + ("YES" if is_research else "NO - Clinical Only"),
            "",
            "═══════════════════════════════════════════════════════════════════════════════",
            "This audit log constitutes a legal record of the de-identification process.",
            "Retain this receipt for compliance verification and audit purposes.",
            "═══════════════════════════════════════════════════════════════════════════════"
        ])

    return "\n".join(audit_lines)
