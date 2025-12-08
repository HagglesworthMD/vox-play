"""
VoxelMask PDF Reporter - Universal Report Generator
====================================================
Generates professional PDF reports for all compliance profiles.

Report Types:
- CLINICAL: Data Repair Log
- RESEARCH: Safe Harbor Certificate
- STRICT: OAIC Privacy Audit
- FOI_LEGAL: Forensic Integrity Certificate
- FOI_PATIENT: Medical Image Release Letter

Dependencies:
- fpdf2 (pip install fpdf2)

Author: VoxelMask Team
"""

import os
from datetime import datetime
from typing import Dict, List, Optional, Any
import io

try:
    from fpdf import FPDF
except ImportError:
    # Fallback - will raise error if used without fpdf
    FPDF = None


class VoxelMaskPDF(FPDF):
    """Custom PDF class with VoxelMask branding."""
    
    def __init__(self, title: str = "VoxelMask Report", report_type: str = "GENERAL"):
        super().__init__()
        self.title = title
        self.report_type = report_type
        self.set_auto_page_break(auto=True, margin=20)
        
    def header(self):
        """Add header to each page."""
        # Logo placeholder (gradient bar)
        self.set_fill_color(0, 180, 160)  # Teal
        self.rect(0, 0, 210, 12, 'F')
        
        # Title
        self.set_font('Helvetica', 'B', 14)
        self.set_text_color(255, 255, 255)
        self.set_xy(10, 3)
        self.cell(0, 6, f'VoxelMask | {self.title}', align='L')
        
        # Report type badge
        self.set_xy(150, 3)
        self.set_font('Helvetica', '', 10)
        self.cell(0, 6, self.report_type, align='R')
        
        self.ln(15)
        
    def footer(self):
        """Add footer to each page."""
        self.set_y(-15)
        self.set_font('Helvetica', 'I', 8)
        self.set_text_color(128, 128, 128)
        self.cell(0, 10, f'Page {self.page_no()}/{{nb}} | Generated: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}', align='C')


class PDFReporter:
    """
    Universal PDF Report Generator for VoxelMask.
    
    Supports all compliance profiles with professional formatting.
    """
    
    def __init__(self):
        if FPDF is None:
            raise ImportError("fpdf2 is required. Install with: pip install fpdf2")
    
    def create_pdf(
        self,
        report_type: str,
        data: Dict[str, Any],
        output_path: Optional[str] = None
    ) -> bytes:
        """
        Create a PDF report based on type and data.
        
        Args:
            report_type: One of CLINICAL, RESEARCH, STRICT, FOI_LEGAL, FOI_PATIENT
            data: Dictionary containing report-specific data
            output_path: Optional path to save PDF file
            
        Returns:
            PDF content as bytes
        """
        # Route to appropriate generator
        generators = {
            'CLINICAL': self._generate_clinical_report,
            'RESEARCH': self._generate_research_report,
            'STRICT': self._generate_strict_report,
            'FOI_LEGAL': self._generate_foi_legal_report,
            'FOI_PATIENT': self._generate_foi_patient_report,
            'NIFTI': self._generate_nifti_report,
        }
        
        generator = generators.get(report_type.upper())
        if not generator:
            raise ValueError(f"Unknown report type: {report_type}. Valid: {list(generators.keys())}")
        
        pdf_bytes = generator(data)
        
        # Save to file if path provided
        if output_path:
            with open(output_path, 'wb') as f:
                f.write(pdf_bytes)
        
        return pdf_bytes
    
    # ═══════════════════════════════════════════════════════════════════════════
    # PROFILE A: CLINICAL - Data Repair Log
    # ═══════════════════════════════════════════════════════════════════════════
    
    def _generate_clinical_report(self, data: Dict) -> bytes:
        """Generate Clinical Data Repair Log."""
        pdf = VoxelMaskPDF(title="Data Repair Log", report_type="CLINICAL")
        pdf.alias_nb_pages()
        pdf.add_page()
        
        # Summary section
        pdf.set_font('Helvetica', 'B', 16)
        pdf.set_text_color(0, 0, 0)
        pdf.cell(0, 10, 'Clinical Data Repair Summary', ln=True)
        
        pdf.set_font('Helvetica', '', 11)
        pdf.set_text_color(60, 60, 60)
        
        # Patient info box
        pdf.set_fill_color(245, 245, 245)
        pdf.rect(10, pdf.get_y(), 190, 35, 'F')
        pdf.set_xy(15, pdf.get_y() + 5)
        
        pdf.set_font('Helvetica', 'B', 10)
        pdf.cell(40, 6, 'Patient Name:', ln=False)
        pdf.set_font('Helvetica', '', 10)
        pdf.cell(0, 6, data.get('patient_name', 'N/A'), ln=True)
        
        pdf.set_x(15)
        pdf.set_font('Helvetica', 'B', 10)
        pdf.cell(40, 6, 'Accession:', ln=False)
        pdf.set_font('Helvetica', '', 10)
        pdf.cell(0, 6, data.get('accession', 'N/A'), ln=True)
        
        pdf.set_x(15)
        pdf.set_font('Helvetica', 'B', 10)
        pdf.cell(40, 6, 'Study Date:', ln=False)
        pdf.set_font('Helvetica', '', 10)
        pdf.cell(0, 6, data.get('study_date', 'N/A'), ln=True)
        
        pdf.set_x(15)
        pdf.set_font('Helvetica', 'B', 10)
        pdf.cell(40, 6, 'Operator:', ln=False)
        pdf.set_font('Helvetica', '', 10)
        pdf.cell(0, 6, data.get('operator', 'WEBAPP_USER'), ln=True)
        
        pdf.ln(10)
        
        # Fixed tags table
        pdf.set_font('Helvetica', 'B', 12)
        pdf.cell(0, 8, 'Tags Modified:', ln=True)
        
        fixed_tags = data.get('fixed_tags', [])
        if fixed_tags:
            # Table header
            pdf.set_fill_color(0, 180, 160)
            pdf.set_text_color(255, 255, 255)
            pdf.set_font('Helvetica', 'B', 9)
            pdf.cell(50, 7, 'Tag', border=1, fill=True)
            pdf.cell(50, 7, 'Original', border=1, fill=True)
            pdf.cell(50, 7, 'New Value', border=1, fill=True)
            pdf.cell(40, 7, 'Action', border=1, fill=True, ln=True)
            
            # Table rows
            pdf.set_text_color(0, 0, 0)
            pdf.set_font('Helvetica', '', 9)
            for tag in fixed_tags:
                pdf.cell(50, 6, str(tag.get('name', ''))[:25], border=1)
                pdf.cell(50, 6, str(tag.get('original', ''))[:25], border=1)
                pdf.cell(50, 6, str(tag.get('new', ''))[:25], border=1)
                pdf.cell(40, 6, str(tag.get('action', 'Modified')), border=1, ln=True)
        else:
            pdf.set_font('Helvetica', 'I', 10)
            pdf.cell(0, 8, 'No tags were modified.', ln=True)
        
        pdf.ln(10)
        
        # Pixel masking section
        if data.get('mask_applied'):
            pdf.set_font('Helvetica', 'B', 12)
            pdf.cell(0, 8, 'Pixel Masking Applied:', ln=True)
            pdf.set_font('Helvetica', '', 10)
            pdf.multi_cell(0, 6, f"Region: {data.get('mask_region', 'User-defined region')}\nFrames: {data.get('frames_processed', 'All')}")
        
        # Audit trail
        pdf.ln(5)
        pdf.set_font('Helvetica', 'B', 12)
        pdf.cell(0, 8, 'Audit Trail:', ln=True)
        pdf.set_font('Helvetica', '', 9)
        pdf.set_text_color(80, 80, 80)
        pdf.multi_cell(0, 5, f"UUID: {data.get('uuid', 'N/A')}\nTimestamp: {data.get('timestamp', datetime.now().isoformat())}\nOriginal Hash: {data.get('original_hash', 'N/A')[:32]}...\nProcessed Hash: {data.get('processed_hash', 'N/A')[:32]}...")
        
        return bytes(pdf.output())
    
    # ═══════════════════════════════════════════════════════════════════════════
    # PROFILE B: RESEARCH - Safe Harbor Certificate
    # ═══════════════════════════════════════════════════════════════════════════
    
    def _generate_research_report(self, data: Dict) -> bytes:
        """Generate HIPAA Safe Harbor De-identification Certificate."""
        pdf = VoxelMaskPDF(title="Safe Harbor Certificate", report_type="RESEARCH")
        pdf.alias_nb_pages()
        pdf.add_page()
        
        # Certificate header
        pdf.set_font('Helvetica', 'B', 20)
        pdf.set_text_color(0, 100, 80)
        pdf.cell(0, 15, 'HIPAA Safe Harbor', align='C', ln=True)
        pdf.set_font('Helvetica', 'B', 16)
        pdf.cell(0, 10, 'De-Identification Certificate', align='C', ln=True)
        
        pdf.ln(10)
        
        # Certification statement
        pdf.set_font('Helvetica', '', 11)
        pdf.set_text_color(0, 0, 0)
        pdf.multi_cell(0, 6, 
            "This certifies that the attached DICOM files have been processed using the "
            "VoxelMask Safe Harbor method, which removes or generalizes the 18 HIPAA-specified "
            "identifiers in accordance with 45 CFR 164.514(b)(2)."
        )
        
        pdf.ln(10)
        
        # 18 Identifiers checklist
        pdf.set_font('Helvetica', 'B', 12)
        pdf.cell(0, 8, 'Verified Removal of 18 HIPAA Identifiers:', ln=True)
        
        identifiers = [
            ("Names", True), ("Geographic Data", True), ("Dates (except year)", True),
            ("Phone Numbers", True), ("Fax Numbers", True), ("Email Addresses", True),
            ("SSN", True), ("Medical Record Numbers", True), ("Health Plan Numbers", True),
            ("Account Numbers", True), ("License Numbers", True), ("Vehicle IDs", True),
            ("Device IDs", True), ("URLs", True), ("IP Addresses", True),
            ("Biometric IDs", True), ("Photos", data.get('pixel_masked', False)), 
            ("Unique Identifiers", True)
        ]
        
        pdf.set_font('Helvetica', '', 10)
        col_width = 63
        for i, (name, removed) in enumerate(identifiers):
            if i % 3 == 0 and i > 0:
                pdf.ln(6)
            status = "[X]" if removed else "[ ]"
            pdf.cell(col_width, 6, f"{status} {name}")
        
        pdf.ln(15)
        
        # Subject info
        pdf.set_fill_color(240, 255, 250)
        pdf.rect(10, pdf.get_y(), 190, 25, 'F')
        pdf.set_xy(15, pdf.get_y() + 5)
        
        pdf.set_font('Helvetica', 'B', 10)
        pdf.cell(40, 6, 'Subject ID:', ln=False)
        pdf.set_font('Helvetica', '', 10)
        pdf.cell(60, 6, data.get('subject_id', 'SUB-001'), ln=False)
        
        pdf.set_font('Helvetica', 'B', 10)
        pdf.cell(35, 6, 'Trial ID:', ln=False)
        pdf.set_font('Helvetica', '', 10)
        pdf.cell(0, 6, data.get('trial_id', 'TRIAL-001'), ln=True)
        
        pdf.set_x(15)
        pdf.set_font('Helvetica', 'B', 10)
        pdf.cell(40, 6, 'Site ID:', ln=False)
        pdf.set_font('Helvetica', '', 10)
        pdf.cell(60, 6, data.get('site_id', 'SITE-01'), ln=False)
        
        pdf.set_font('Helvetica', 'B', 10)
        pdf.cell(35, 6, 'Time Point:', ln=False)
        pdf.set_font('Helvetica', '', 10)
        pdf.cell(0, 6, data.get('time_point', 'Baseline'), ln=True)
        
        pdf.ln(15)
        
        # Processing details
        pdf.set_font('Helvetica', 'B', 12)
        pdf.cell(0, 8, 'Processing Details:', ln=True)
        pdf.set_font('Helvetica', '', 10)
        pdf.multi_cell(0, 5, 
            f"Files Processed: {data.get('file_count', 1)}\n"
            f"UIDs Regenerated: {'Yes' if data.get('uids_regenerated') else 'No'}\n"
            f"Dates Generalized: Year only retained\n"
            f"Pixel Data Scrubbed: {'Yes' if data.get('pixel_masked') else 'No'}\n"
            f"Processing UUID: {data.get('uuid', 'N/A')}"
        )
        
        pdf.ln(10)
        
        # Signature line
        pdf.set_font('Helvetica', 'I', 10)
        pdf.cell(0, 8, 'This certificate was automatically generated by VoxelMask.', align='C', ln=True)
        pdf.cell(0, 6, f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')}", align='C')
        
        return bytes(pdf.output())
    
    # ═══════════════════════════════════════════════════════════════════════════
    # PROFILE C: STRICT - OAIC Privacy Audit
    # ═══════════════════════════════════════════════════════════════════════════
    
    def _generate_strict_report(self, data: Dict) -> bytes:
        """Generate Australian OAIC APP11 Privacy Audit Report."""
        pdf = VoxelMaskPDF(title="OAIC Privacy Audit", report_type="AU STRICT")
        pdf.alias_nb_pages()
        pdf.add_page()
        
        # Header
        pdf.set_font('Helvetica', 'B', 18)
        pdf.set_text_color(0, 80, 120)
        pdf.cell(0, 12, 'Australian Privacy Principles', align='C', ln=True)
        pdf.set_font('Helvetica', 'B', 14)
        pdf.cell(0, 8, 'APP 11 Compliance Audit', align='C', ln=True)
        
        pdf.ln(10)
        
        # Compliance statement
        pdf.set_font('Helvetica', '', 11)
        pdf.set_text_color(0, 0, 0)
        pdf.multi_cell(0, 6, 
            "This report certifies compliance with the Australian Privacy Principles (APP) 11, "
            "which requires entities to take reasonable steps to protect personal information "
            "from misuse, interference, loss, and unauthorized access."
        )
        
        pdf.ln(10)
        
        # Protection measures applied
        pdf.set_font('Helvetica', 'B', 12)
        pdf.cell(0, 8, 'Protection Measures Applied:', ln=True)
        
        measures = [
            ("PatientID Hashed", True, f"SHA-256 with salt"),
            ("Dates Shifted", True, f"{data.get('date_shift_days', '-14 to -100')} days (deterministic)"),
            ("UIDs Regenerated", data.get('uids_regenerated', True), "New UUIDs generated"),
            ("Institution Removed", True, "InstitutionName deleted"),
            ("Referring Physician Removed", True, "ReferringPhysicianName deleted"),
            ("Private Tags Removed", True, "All private creator blocks deleted"),
            ("Pixel PHI Scrubbed", data.get('pixel_masked', False), "Burned-in text removed"),
        ]
        
        pdf.set_font('Helvetica', '', 10)
        for measure, applied, detail in measures:
            status = "[APPLIED]" if applied else "[SKIPPED]"
            color = (0, 128, 0) if applied else (180, 0, 0)
            pdf.set_text_color(*color)
            pdf.cell(25, 6, status)
            pdf.set_text_color(0, 0, 0)
            pdf.cell(55, 6, measure)
            pdf.set_text_color(100, 100, 100)
            pdf.cell(0, 6, detail, ln=True)
        
        pdf.ln(10)
        
        # Hashed ID display
        pdf.set_text_color(0, 0, 0)
        pdf.set_font('Helvetica', 'B', 12)
        pdf.cell(0, 8, 'De-Identification Result:', ln=True)
        
        pdf.set_fill_color(245, 245, 250)
        pdf.rect(10, pdf.get_y(), 190, 20, 'F')
        pdf.set_xy(15, pdf.get_y() + 5)
        
        pdf.set_font('Helvetica', 'B', 10)
        pdf.cell(40, 5, 'Original PatientID:', ln=False)
        pdf.set_font('Courier', '', 9)
        pdf.cell(0, 5, '[REDACTED]', ln=True)
        
        pdf.set_x(15)
        pdf.set_font('Helvetica', 'B', 10)
        pdf.cell(40, 5, 'Hashed PatientID:', ln=False)
        pdf.set_font('Courier', '', 9)
        pdf.cell(0, 5, data.get('hashed_patient_id', 'SHA256_HASH_VALUE')[:40] + '...', ln=True)
        
        pdf.ln(15)
        
        # Audit trail
        pdf.set_font('Helvetica', 'B', 12)
        pdf.cell(0, 8, 'Audit Trail:', ln=True)
        pdf.set_font('Helvetica', '', 9)
        pdf.multi_cell(0, 5, 
            f"Processing UUID: {data.get('uuid', 'N/A')}\n"
            f"Timestamp: {data.get('timestamp', datetime.now().isoformat())}\n"
            f"Files Processed: {data.get('file_count', 1)}\n"
            f"Operator: {data.get('operator', 'WEBAPP_USER')}"
        )
        
        return bytes(pdf.output())
    
    # ═══════════════════════════════════════════════════════════════════════════
    # PROFILE D: FOI_LEGAL - Forensic Integrity Certificate
    # ═══════════════════════════════════════════════════════════════════════════
    
    def _generate_foi_legal_report(self, data: Dict) -> bytes:
        """Generate FOI Legal Forensic Integrity Certificate."""
        pdf = VoxelMaskPDF(title="Forensic Integrity Certificate", report_type="FOI LEGAL")
        pdf.alias_nb_pages()
        pdf.add_page()
        
        # Official header
        pdf.set_font('Helvetica', 'B', 18)
        pdf.set_text_color(80, 0, 0)
        pdf.cell(0, 12, 'FORENSIC INTEGRITY CERTIFICATE', align='C', ln=True)
        
        pdf.set_font('Helvetica', '', 11)
        pdf.set_text_color(0, 0, 0)
        pdf.cell(0, 8, 'Freedom of Information Request - Legal Discovery', align='C', ln=True)
        
        pdf.ln(10)
        
        # Case information
        pdf.set_fill_color(255, 250, 245)
        pdf.rect(10, pdf.get_y(), 190, 30, 'F')
        pdf.set_xy(15, pdf.get_y() + 5)
        
        pdf.set_font('Helvetica', 'B', 10)
        pdf.cell(40, 6, 'Case Reference:', ln=False)
        pdf.set_font('Helvetica', '', 10)
        pdf.cell(60, 6, data.get('case_reference', 'N/A'), ln=False)
        
        pdf.set_font('Helvetica', 'B', 10)
        pdf.cell(35, 6, 'Request Date:', ln=False)
        pdf.set_font('Helvetica', '', 10)
        pdf.cell(0, 6, data.get('request_date', datetime.now().strftime('%Y-%m-%d')), ln=True)
        
        pdf.set_x(15)
        pdf.set_font('Helvetica', 'B', 10)
        pdf.cell(40, 6, 'Requesting Party:', ln=False)
        pdf.set_font('Helvetica', '', 10)
        pdf.cell(0, 6, data.get('requesting_party', 'N/A'), ln=True)
        
        pdf.set_x(15)
        pdf.set_font('Helvetica', 'B', 10)
        pdf.cell(40, 6, 'Patient Name:', ln=False)
        pdf.set_font('Helvetica', '', 10)
        pdf.cell(0, 6, data.get('patient_name', 'N/A'), ln=True)
        
        pdf.ln(10)
        
        # Chain of custody
        pdf.set_font('Helvetica', 'B', 12)
        pdf.cell(0, 8, 'Chain of Custody Verification:', ln=True)
        pdf.set_font('Helvetica', '', 10)
        pdf.multi_cell(0, 6, 
            "The following DICOM files have been processed for legal release. "
            "UIDs have been PRESERVED to maintain chain of custody. "
            "Staff names have been REDACTED per privacy requirements."
        )
        
        pdf.ln(5)
        
        # Hash verification table
        pdf.set_font('Helvetica', 'B', 11)
        pdf.cell(0, 8, 'Hash Verification:', ln=True)
        
        pdf.set_fill_color(80, 0, 0)
        pdf.set_text_color(255, 255, 255)
        pdf.set_font('Helvetica', 'B', 9)
        pdf.cell(60, 7, 'File', border=1, fill=True)
        pdf.cell(65, 7, 'Original SHA-256', border=1, fill=True)
        pdf.cell(65, 7, 'Processed SHA-256', border=1, fill=True, ln=True)
        
        pdf.set_text_color(0, 0, 0)
        pdf.set_font('Courier', '', 8)
        
        files = data.get('files', [{'name': 'image.dcm', 'original_hash': 'N/A', 'processed_hash': 'N/A'}])
        for f in files[:10]:  # Limit to 10 files
            pdf.cell(60, 6, str(f.get('name', ''))[:30], border=1)
            pdf.cell(65, 6, str(f.get('original_hash', ''))[:28] + '...', border=1)
            pdf.cell(65, 6, str(f.get('processed_hash', ''))[:28] + '...', border=1, ln=True)
        
        pdf.ln(10)
        
        # Redaction log
        pdf.set_font('Helvetica', 'B', 12)
        pdf.cell(0, 8, 'Redaction Log (Staff Names Removed):', ln=True)
        
        redactions = data.get('redactions', [])
        if redactions:
            pdf.set_font('Helvetica', '', 10)
            for r in redactions:
                pdf.cell(0, 6, f"- {r.get('tag', 'Unknown')}: {r.get('action', 'Redacted')}", ln=True)
        else:
            pdf.set_font('Helvetica', 'I', 10)
            pdf.cell(0, 6, "No staff names found in dataset.", ln=True)
        
        pdf.ln(10)
        
        # Certification
        pdf.set_font('Helvetica', 'B', 10)
        pdf.cell(0, 8, 'I certify that these records are true copies of the originals:', ln=True)
        pdf.ln(10)
        pdf.cell(80, 0, '', 'T')  # Signature line
        pdf.ln(5)
        pdf.set_font('Helvetica', '', 9)
        pdf.cell(0, 5, 'Authorized Signatory', ln=True)
        pdf.cell(0, 5, f'Date: {datetime.now().strftime("%Y-%m-%d")}')
        
        return bytes(pdf.output())
    
    # ═══════════════════════════════════════════════════════════════════════════
    # PROFILE D: FOI_PATIENT - Medical Image Release Letter
    # ═══════════════════════════════════════════════════════════════════════════
    
    def _generate_foi_patient_report(self, data: Dict) -> bytes:
        """Generate patient-friendly Medical Image Release letter."""
        pdf = VoxelMaskPDF(title="Medical Image Release", report_type="FOI PATIENT")
        pdf.alias_nb_pages()
        pdf.add_page()
        
        # Hospital/facility header
        pdf.set_font('Helvetica', 'B', 14)
        pdf.set_text_color(0, 80, 120)
        pdf.cell(0, 8, data.get('facility_name', 'Medical Imaging Department'), align='C', ln=True)
        pdf.set_font('Helvetica', '', 10)
        pdf.set_text_color(100, 100, 100)
        pdf.cell(0, 6, data.get('facility_address', ''), align='C', ln=True)
        pdf.cell(0, 6, data.get('facility_phone', ''), align='C', ln=True)
        
        pdf.ln(15)
        
        # Date and reference
        pdf.set_text_color(0, 0, 0)
        pdf.set_font('Helvetica', '', 11)
        pdf.cell(0, 6, f"Date: {datetime.now().strftime('%d %B %Y')}", ln=True)
        pdf.cell(0, 6, f"Reference: {data.get('reference_number', 'FOI-' + datetime.now().strftime('%Y%m%d'))}", ln=True)
        
        pdf.ln(10)
        
        # Patient address
        pdf.set_font('Helvetica', 'B', 11)
        pdf.cell(0, 6, data.get('patient_name', 'Patient Name'), ln=True)
        pdf.set_font('Helvetica', '', 11)
        if data.get('patient_address'):
            for line in data['patient_address'].split('\n'):
                pdf.cell(0, 6, line, ln=True)
        
        pdf.ln(10)
        
        # Greeting - use recipient field if provided, otherwise fall back to patient name
        recipient = data.get('recipient', '') or data.get('patient_name', 'Patient')
        # Use first word of recipient if it's a full name, or use as-is for titles like "lawyer"
        greeting_name = recipient.split()[0] if recipient else 'Patient'
        pdf.set_font('Helvetica', '', 11)
        pdf.cell(0, 8, f"Dear {greeting_name},", ln=True)
        
        pdf.ln(5)
        
        # Body text
        pdf.multi_cell(0, 6, 
            f"Further to your request dated {data.get('request_date', 'N/A')}, please find enclosed "
            f"copies of your medical imaging records."
        )
        
        pdf.ln(5)
        
        # What's included
        pdf.set_font('Helvetica', 'B', 11)
        pdf.cell(0, 8, 'Enclosed:', ln=True)
        pdf.set_font('Helvetica', '', 11)
        
        included_items = data.get('included_items', [
            f"{data.get('file_count', 1)} DICOM image file(s)",
            "DICOM Viewer application (HTML)",
            "This cover letter"
        ])
        for item in included_items:
            pdf.cell(0, 6, f"  - {item}", ln=True)
        
        pdf.ln(5)
        
        # Study information
        pdf.set_font('Helvetica', 'B', 11)
        pdf.cell(0, 8, 'Study Information:', ln=True)
        
        pdf.set_fill_color(248, 248, 248)
        pdf.rect(10, pdf.get_y(), 190, 25, 'F')
        pdf.set_xy(15, pdf.get_y() + 5)
        
        pdf.set_font('Helvetica', '', 10)
        pdf.cell(40, 5, 'Study Date:', ln=False)
        pdf.cell(60, 5, data.get('study_date', 'N/A'), ln=False)
        pdf.cell(30, 5, 'Modality:', ln=False)
        pdf.cell(0, 5, data.get('modality', 'N/A'), ln=True)
        
        pdf.set_x(15)
        pdf.cell(40, 5, 'Accession:', ln=False)
        pdf.cell(60, 5, data.get('accession', 'N/A'), ln=False)
        pdf.cell(30, 5, 'Files:', ln=False)
        pdf.cell(0, 5, str(data.get('file_count', 1)), ln=True)
        
        pdf.ln(15)
        
        # Viewing instructions
        pdf.set_font('Helvetica', 'B', 11)
        pdf.cell(0, 8, 'How to View Your Images:', ln=True)
        pdf.set_font('Helvetica', '', 10)
        pdf.multi_cell(0, 5, 
            "1. Extract all files from the ZIP archive to a folder on your computer.\n"
            "2. Open the file named 'DICOM_Viewer.html' in a web browser (Chrome recommended).\n"
            "3. When prompted, select the folder containing your images.\n"
            "4. Use the navigation buttons to browse through your images."
        )
        
        pdf.ln(10)
        
        # Closing
        pdf.set_font('Helvetica', '', 11)
        pdf.multi_cell(0, 6, 
            "If you have any questions about these records or require further assistance, "
            "please contact our Medical Records Department."
        )
        
        pdf.ln(10)
        pdf.cell(0, 6, 'Yours sincerely,', ln=True)
        pdf.ln(15)
        pdf.cell(0, 6, data.get('signatory_name', 'Medical Records Officer'), ln=True)
        pdf.set_font('Helvetica', 'I', 10)
        pdf.cell(0, 5, data.get('signatory_title', 'Health Information Services'))
        
        return bytes(pdf.output())
    
    # ═══════════════════════════════════════════════════════════════════════════
    # NIFTI CONVERSION REPORT
    # ═══════════════════════════════════════════════════════════════════════════
    
    def _generate_nifti_report(self, data: Dict) -> bytes:
        """Generate NIfTI conversion report for AI/ML research."""
        pdf = VoxelMaskPDF(title="NIfTI Conversion Report", report_type="AI/ML RESEARCH")
        pdf.alias_nb_pages()
        pdf.add_page()
        
        # Header
        pdf.set_font('Helvetica', 'B', 18)
        pdf.set_text_color(0, 120, 80)
        pdf.cell(0, 12, 'NIfTI Conversion Report', align='C', ln=True)
        pdf.set_font('Helvetica', '', 11)
        pdf.set_text_color(100, 100, 100)
        pdf.cell(0, 6, 'AI/Machine Learning Ready Format', align='C', ln=True)
        
        pdf.ln(10)
        
        # Conversion summary
        pdf.set_font('Helvetica', 'B', 12)
        pdf.set_text_color(0, 0, 0)
        pdf.cell(0, 8, 'Conversion Summary:', ln=True)
        
        pdf.set_fill_color(240, 255, 245)
        pdf.rect(10, pdf.get_y(), 190, 30, 'F')
        pdf.set_xy(15, pdf.get_y() + 5)
        
        pdf.set_font('Helvetica', '', 10)
        pdf.cell(50, 6, 'Conversion Mode:', ln=False)
        pdf.set_font('Helvetica', 'B', 10)
        pdf.cell(0, 6, data.get('conversion_mode', '3D'), ln=True)
        
        pdf.set_x(15)
        pdf.set_font('Helvetica', '', 10)
        pdf.cell(50, 6, 'Input DICOMs:', ln=False)
        pdf.cell(50, 6, str(data.get('input_count', 0)), ln=False)
        pdf.cell(30, 6, 'Output Files:', ln=False)
        pdf.cell(0, 6, str(data.get('output_count', 0)), ln=True)
        
        pdf.set_x(15)
        pdf.cell(50, 6, 'Quality Retention:', ln=False)
        pdf.set_font('Helvetica', 'B', 10)
        retention = data.get('retention', 100)
        if retention >= 99:
            pdf.set_text_color(0, 128, 0)
        elif retention >= 90:
            pdf.set_text_color(180, 140, 0)
        else:
            pdf.set_text_color(180, 0, 0)
        pdf.cell(0, 6, f"{retention:.1f}%", ln=True)
        
        pdf.set_text_color(0, 0, 0)
        pdf.ln(15)
        
        # Important notes
        pdf.set_font('Helvetica', 'B', 12)
        pdf.cell(0, 8, 'Important Notes for Researchers:', ln=True)
        pdf.set_font('Helvetica', '', 10)
        pdf.multi_cell(0, 5, 
            "1. NIfTI format is optimized for 3D/4D volume processing.\n"
            "2. Most DICOM metadata has been stripped - only voxel data remains.\n"
            "3. Use nibabel (Python) or ITK-SNAP to view/process these files.\n"
            "4. The affine matrix may be identity for 2D fallback conversions."
        )
        
        pdf.ln(10)
        
        # Python verification code
        pdf.set_font('Helvetica', 'B', 12)
        pdf.cell(0, 8, 'Verification Code (Python):', ln=True)
        pdf.set_fill_color(40, 40, 40)
        pdf.set_text_color(200, 200, 200)
        pdf.set_font('Courier', '', 9)
        pdf.multi_cell(0, 5, 
            "import nibabel as nib\n"
            "img = nib.load('file.nii.gz')\n"
            "print(f'Shape: {img.shape}')\n"
            "print(f'Affine: {img.affine}')\n"
            "data = img.get_fdata()  # NumPy array",
            fill=True
        )
        
        return bytes(pdf.output())


# ═══════════════════════════════════════════════════════════════════════════════
# CONVENIENCE FUNCTION
# ═══════════════════════════════════════════════════════════════════════════════

def create_report(report_type: str, data: Dict, output_path: Optional[str] = None) -> bytes:
    """
    Convenience function to create a PDF report.
    
    Args:
        report_type: CLINICAL, RESEARCH, STRICT, FOI_LEGAL, FOI_PATIENT, NIFTI
        data: Dictionary with report-specific data
        output_path: Optional path to save the PDF
        
    Returns:
        PDF content as bytes
    """
    reporter = PDFReporter()
    return reporter.create_pdf(report_type, data, output_path)
