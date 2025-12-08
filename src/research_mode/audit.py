"""
Compliance Audit and Report Generation for Research Mode

Generates detailed compliance reports for HIPAA Safe Harbor and 
DICOM PS3.15 verification.
"""

import hashlib
import json
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from .anonymizer import AnonymizationResult


@dataclass
class AuditEntry:
    """Single file audit entry."""
    
    # File identification
    original_filename: str
    anonymized_filename: str
    processing_timestamp: str
    
    # Status
    success: bool
    error_message: Optional[str] = None
    
    # Modifications summary
    tags_removed_count: int = 0
    tags_anonymized_count: int = 0
    uids_remapped_count: int = 0
    dates_shifted_count: int = 0
    texts_scrubbed_count: int = 0
    private_tags_removed_count: int = 0
    
    # Detailed modifications (for full audit)
    tags_removed: List[str] = field(default_factory=list)
    tags_anonymized: List[str] = field(default_factory=list)
    uids_remapped: Dict[str, str] = field(default_factory=dict)
    dates_shifted: Dict[str, Dict[str, str]] = field(default_factory=dict)
    texts_scrubbed: List[str] = field(default_factory=list)
    private_tags_removed: List[str] = field(default_factory=list)
    
    # Integrity verification
    original_pixel_hash: Optional[str] = None
    anonymized_pixel_hash: Optional[str] = None
    pixel_data_preserved: bool = True
    
    # Date shift applied
    date_shift_days: int = 0
    
    # Compliance profile used
    compliance_profile: str = "safe_harbor"
    
    # ═══════════════════════════════════════════════════════════════════════════
    # PIXEL MASKING AUDIT FIELDS
    # ═══════════════════════════════════════════════════════════════════════════
    
    # Whether pixel data was modified (masked)
    pixel_data_modified: bool = False
    
    # Modality that triggered masking
    pixel_mask_triggered_by: Optional[str] = None
    
    # Masking region details
    pixel_mask_region: Optional[Dict[str, Any]] = None
    
    # Compliance status - distinguishes metadata vs pixel cleaning
    metadata_clean: bool = True
    pixel_clean: bool = False
    
    # Warning if masking failed
    pixel_mask_warning: Optional[str] = None
    
    # Safety notification when masking is intentionally bypassed
    safety_notification: Optional[str] = None


@dataclass
class ComplianceReport:
    """Full compliance report for a batch of anonymized files."""
    
    # Report metadata
    report_id: str
    generation_timestamp: str
    generator_version: str = "1.0.0"
    
    # Compliance standards (will be set dynamically)
    compliance_standards: List[str] = field(default_factory=list)
    
    # Processing summary
    total_files_processed: int = 0
    successful_files: int = 0
    failed_files: int = 0
    
    # Aggregate statistics
    total_tags_removed: int = 0
    total_tags_anonymized: int = 0
    total_uids_remapped: int = 0
    total_dates_shifted: int = 0
    total_texts_scrubbed: int = 0
    total_private_tags_removed: int = 0
    
    # Integrity verification
    all_pixel_data_preserved: bool = True
    
    # ═══════════════════════════════════════════════════════════════════════════
    # PIXEL MASKING STATISTICS
    # ═══════════════════════════════════════════════════════════════════════════
    
    # Files that had pixel masking applied
    files_with_pixel_masking: int = 0
    
    # Files that required masking but it may have failed
    files_with_masking_warnings: int = 0
    
    # All files are metadata clean
    all_metadata_clean: bool = True
    
    # All files are pixel clean (masked if required, or no masking needed)
    all_pixel_clean: bool = True
    
    # Individual file entries
    file_entries: List[AuditEntry] = field(default_factory=list)
    
    # Configuration used
    anonymization_config: Dict[str, Any] = field(default_factory=dict)


class ComplianceReportGenerator:
    """
    Generates compliance reports for DICOM anonymization batches.
    
    Reports include:
    - List of all files processed
    - Tags modified per file
    - SHA-256 hashes of original vs anonymized pixel data
    - Compliance standard verification
    """
    
    VERSION = "1.0.0"
    
    def __init__(self):
        """Initialize the report generator."""
        self._entries: List[AuditEntry] = []
    
    def _format_tag(self, tag: tuple) -> str:
        """Format a DICOM tag tuple as a string."""
        return f"({tag[0]:04X},{tag[1]:04X})"
    
    def add_result(
        self,
        result: AnonymizationResult,
        anonymized_filename: Optional[str] = None,
        compliance_profile: str = "safe_harbor"
    ) -> AuditEntry:
        """
        Add an anonymization result to the report.
        
        Args:
            result: AnonymizationResult from anonymizer
            anonymized_filename: Name of anonymized file (if different)
            compliance_profile: Compliance profile used ("safe_harbor" or "limited_data_set")
            
        Returns:
            AuditEntry created from the result
        """
        entry = AuditEntry(
            original_filename=str(result.original_path.name),
            anonymized_filename=anonymized_filename or str(result.original_path.name),
            processing_timestamp=datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            success=result.success,
            error_message=result.error_message,
            
            # Counts
            tags_removed_count=len(result.tags_removed),
            tags_anonymized_count=len(result.tags_anonymized),
            uids_remapped_count=len(result.uids_remapped),
            dates_shifted_count=len(result.dates_shifted),
            texts_scrubbed_count=len(result.texts_scrubbed),
            private_tags_removed_count=len(result.private_tags_removed),
            
            # Detailed lists
            tags_removed=[self._format_tag(t) for t in result.tags_removed],
            tags_anonymized=[self._format_tag(t) for t in result.tags_anonymized],
            uids_remapped=result.uids_remapped,
            dates_shifted={
                k: {"original": v[0], "shifted": v[1]}
                for k, v in result.dates_shifted.items()
            },
            texts_scrubbed=[self._format_tag(t) for t in result.texts_scrubbed],
            private_tags_removed=[self._format_tag(t) for t in result.private_tags_removed],
            
            # Integrity
            original_pixel_hash=result.original_pixel_hash,
            anonymized_pixel_hash=result.anonymized_pixel_hash,
            pixel_data_preserved=result.pixel_data_preserved,
            
            # Date shift
            date_shift_days=result.date_shift_days,
            
            # Compliance profile
            compliance_profile=compliance_profile,
            
            # Pixel masking
            pixel_data_modified=result.pixel_data_modified,
            pixel_mask_triggered_by=result.pixel_mask_triggered_by,
            pixel_mask_region=result.pixel_mask_region,
            metadata_clean=result.metadata_clean,
            pixel_clean=result.pixel_clean,
            pixel_mask_warning=result.pixel_mask_warning,
            safety_notification=result.safety_notification,
        )
        
        self._entries.append(entry)
        return entry
    
    def generate_report(
        self,
        config_dict: Optional[Dict[str, Any]] = None,
        compliance_profile: str = "safe_harbor"
    ) -> ComplianceReport:
        """
        Generate a compliance report from all added results.
        
        Args:
            config_dict: Anonymization configuration used (for audit trail)
            compliance_profile: Compliance profile used ("safe_harbor" or "limited_data_set")
            
        Returns:
            ComplianceReport with all entries and statistics
        """
        # Generate unique report ID
        report_id = hashlib.sha256(
            f"{datetime.now(timezone.utc).isoformat()}{len(self._entries)}".encode()
        ).hexdigest()[:16]
        
        # Calculate aggregate statistics
        total_files = len(self._entries)
        successful = sum(1 for e in self._entries if e.success)
        failed = total_files - successful
        
        total_tags_removed = sum(e.tags_removed_count for e in self._entries)
        total_tags_anonymized = sum(e.tags_anonymized_count for e in self._entries)
        total_uids_remapped = sum(e.uids_remapped_count for e in self._entries)
        total_dates_shifted = sum(e.dates_shifted_count for e in self._entries)
        total_texts_scrubbed = sum(e.texts_scrubbed_count for e in self._entries)
        total_private_tags_removed = sum(e.private_tags_removed_count for e in self._entries)
        
        all_pixel_preserved = all(e.pixel_data_preserved for e in self._entries)
        
        # Calculate pixel masking statistics
        files_with_pixel_masking = sum(1 for e in self._entries if e.pixel_data_modified)
        files_with_masking_warnings = sum(1 for e in self._entries if e.pixel_mask_warning)
        all_metadata_clean = all(e.metadata_clean for e in self._entries)
        all_pixel_clean = all(e.pixel_clean for e in self._entries)
        
        # Sanitize config for JSON serialization
        safe_config = {}
        if config_dict:
            for k, v in config_dict.items():
                if k == 'secret_salt':
                    safe_config[k] = "[REDACTED]"
                elif isinstance(v, bytes):
                    safe_config[k] = "[BINARY_DATA]"
                elif isinstance(v, set):
                    safe_config[k] = list(v)
                else:
                    safe_config[k] = v
        
        # Set compliance standards based on profile
        if compliance_profile == "safe_harbor":
            compliance_standards = [
                "HIPAA Safe Harbor (45 CFR 164.514(b)(2))",
                "DICOM PS3.15 Basic Application Level Confidentiality Profile"
            ]
        elif compliance_profile == "limited_data_set":
            compliance_standards = [
                "HIPAA Limited Data Set (45 CFR 164.514(e))",
                "DICOM PS3.15 Basic Application Level Confidentiality Profile"
            ]
        else:
            compliance_standards = ["Unknown Compliance Profile"]
        
        report = ComplianceReport(
            report_id=report_id,
            generation_timestamp=datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            generator_version=self.VERSION,
            compliance_standards=compliance_standards,
            
            total_files_processed=total_files,
            successful_files=successful,
            failed_files=failed,
            
            total_tags_removed=total_tags_removed,
            total_tags_anonymized=total_tags_anonymized,
            total_uids_remapped=total_uids_remapped,
            total_dates_shifted=total_dates_shifted,
            total_texts_scrubbed=total_texts_scrubbed,
            total_private_tags_removed=total_private_tags_removed,
            
            all_pixel_data_preserved=all_pixel_preserved,
            
            # Pixel masking statistics
            files_with_pixel_masking=files_with_pixel_masking,
            files_with_masking_warnings=files_with_masking_warnings,
            all_metadata_clean=all_metadata_clean,
            all_pixel_clean=all_pixel_clean,
            
            file_entries=self._entries.copy(),
            anonymization_config=safe_config,
        )
        
        return report
    
    def save_report(
        self,
        output_path: Union[str, Path],
        config_dict: Optional[Dict[str, Any]] = None
    ) -> ComplianceReport:
        """
        Generate and save a compliance report to JSON.
        
        Args:
            output_path: Path to save the JSON report
            config_dict: Anonymization configuration used
            
        Returns:
            Generated ComplianceReport
        """
        report = self.generate_report(config_dict)
        
        # Convert to JSON-serializable dict
        report_dict = self._report_to_dict(report)
        
        # Save to file
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(report_dict, f, indent=2, ensure_ascii=False)
        
        return report
    
    def _report_to_dict(self, report: ComplianceReport) -> Dict[str, Any]:
        """Convert ComplianceReport to JSON-serializable dict."""
        return {
            "report_metadata": {
                "report_id": report.report_id,
                "generation_timestamp": report.generation_timestamp,
                "generator_version": report.generator_version,
            },
            "compliance_standards": report.compliance_standards,
            "processing_summary": {
                "total_files_processed": report.total_files_processed,
                "successful_files": report.successful_files,
                "failed_files": report.failed_files,
            },
            "aggregate_statistics": {
                "total_tags_removed": report.total_tags_removed,
                "total_tags_anonymized": report.total_tags_anonymized,
                "total_uids_remapped": report.total_uids_remapped,
                "total_dates_shifted": report.total_dates_shifted,
                "total_texts_scrubbed": report.total_texts_scrubbed,
                "total_private_tags_removed": report.total_private_tags_removed,
            },
            "integrity_verification": {
                "all_pixel_data_preserved": report.all_pixel_data_preserved,
            },
            "pixel_masking_summary": {
                "files_with_pixel_masking": report.files_with_pixel_masking,
                "files_with_masking_warnings": report.files_with_masking_warnings,
                "all_metadata_clean": report.all_metadata_clean,
                "all_pixel_clean": report.all_pixel_clean,
            },
            "file_entries": [
                self._entry_to_dict(entry) for entry in report.file_entries
            ],
            "anonymization_config": report.anonymization_config,
        }
    
    def _entry_to_dict(self, entry: AuditEntry) -> Dict[str, Any]:
        """Convert AuditEntry to JSON-serializable dict."""
        return {
            "file_identification": {
                "original_filename": entry.original_filename,
                "anonymized_filename": entry.anonymized_filename,
                "processing_timestamp": entry.processing_timestamp,
            },
            "status": {
                "success": entry.success,
                "error_message": entry.error_message,
            },
            "modifications_summary": {
                "tags_removed_count": entry.tags_removed_count,
                "tags_anonymized_count": entry.tags_anonymized_count,
                "uids_remapped_count": entry.uids_remapped_count,
                "dates_shifted_count": entry.dates_shifted_count,
                "texts_scrubbed_count": entry.texts_scrubbed_count,
                "private_tags_removed_count": entry.private_tags_removed_count,
            },
            "detailed_modifications": {
                "tags_removed": entry.tags_removed,
                "tags_anonymized": entry.tags_anonymized,
                "uids_remapped": entry.uids_remapped,
                "dates_shifted": entry.dates_shifted,
                "texts_scrubbed": entry.texts_scrubbed,
                "private_tags_removed": entry.private_tags_removed,
            },
            "integrity_verification": {
                "original_pixel_hash": entry.original_pixel_hash,
                "anonymized_pixel_hash": entry.anonymized_pixel_hash,
                "pixel_data_preserved": entry.pixel_data_preserved,
            },
            "date_shift_applied": {
                "days": entry.date_shift_days,
            },
            "pixel_masking": {
                "pixel_data_modified": entry.pixel_data_modified,
                "triggered_by_modality": entry.pixel_mask_triggered_by,
                "mask_region": entry.pixel_mask_region,
                "warning": entry.pixel_mask_warning,
                "safety_notification": entry.safety_notification,
            },
            "compliance_status": {
                "metadata_clean": entry.metadata_clean,
                "pixel_clean": entry.pixel_clean,
            },
        }
    
    def reset(self):
        """Clear all entries for a new batch."""
        self._entries.clear()


def generate_compliance_report_json_schema() -> Dict[str, Any]:
    """
    Generate JSON Schema for the compliance report format.
    
    Returns:
        JSON Schema dictionary
    """
    return {
        "$schema": "http://json-schema.org/draft-07/schema#",
        "title": "DICOM Anonymization Compliance Report",
        "description": "HIPAA Safe Harbor and DICOM PS3.15 compliance audit report",
        "type": "object",
        "required": [
            "report_metadata",
            "compliance_standards",
            "processing_summary",
            "aggregate_statistics",
            "integrity_verification",
            "file_entries"
        ],
        "properties": {
            "report_metadata": {
                "type": "object",
                "properties": {
                    "report_id": {"type": "string"},
                    "generation_timestamp": {"type": "string", "format": "date-time"},
                    "generator_version": {"type": "string"}
                }
            },
            "compliance_standards": {
                "type": "array",
                "items": {"type": "string"}
            },
            "processing_summary": {
                "type": "object",
                "properties": {
                    "total_files_processed": {"type": "integer"},
                    "successful_files": {"type": "integer"},
                    "failed_files": {"type": "integer"}
                }
            },
            "aggregate_statistics": {
                "type": "object",
                "properties": {
                    "total_tags_removed": {"type": "integer"},
                    "total_tags_anonymized": {"type": "integer"},
                    "total_uids_remapped": {"type": "integer"},
                    "total_dates_shifted": {"type": "integer"},
                    "total_texts_scrubbed": {"type": "integer"},
                    "total_private_tags_removed": {"type": "integer"}
                }
            },
            "integrity_verification": {
                "type": "object",
                "properties": {
                    "all_pixel_data_preserved": {"type": "boolean"}
                }
            },
            "file_entries": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "file_identification": {"type": "object"},
                        "status": {"type": "object"},
                        "modifications_summary": {"type": "object"},
                        "detailed_modifications": {"type": "object"},
                        "integrity_verification": {"type": "object"},
                        "date_shift_applied": {"type": "object"}
                    }
                }
            },
            "anonymization_config": {"type": "object"}
        }
    }
