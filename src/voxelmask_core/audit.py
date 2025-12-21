# src/voxelmask_core/audit.py
"""
Audit event structures for VoxelMask.

NO STREAMLIT IMPORTS ALLOWED IN THIS MODULE.

This module provides audit-safe structures that contain NO PHI.
All audit events use hashes, counts, and categories rather than
actual patient data.

Governance: These structures are designed for defensibility and
must never contain patient names, IDs, DOBs, or other identifiers.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional


class AuditEventType(Enum):
    """Types of auditable events."""
    RUN_STARTED = "run_started"
    RUN_COMPLETED = "run_completed"
    RUN_FAILED = "run_failed"
    
    FILE_PROCESSED = "file_processed"
    FILE_SKIPPED = "file_skipped"
    FILE_EXCLUDED = "file_excluded"
    
    DETECTION_STARTED = "detection_started"
    DETECTION_COMPLETED = "detection_completed"
    
    REVIEW_ACCEPTED = "review_accepted"
    REVIEW_REJECTED = "review_rejected"
    
    REGION_MASKED = "region_masked"
    REGION_UNMASKED = "region_unmasked"
    REGION_ADDED = "region_added"
    REGION_DELETED = "region_deleted"
    
    EXPORT_GENERATED = "export_generated"


@dataclass
class AuditEvent:
    """
    A single audit event record.
    
    Contains NO PHI - only operational metadata.
    """
    event_type: AuditEventType
    timestamp: str  # ISO 8601 format
    run_id: Optional[str] = None
    
    # Event-specific data (NO PHI)
    details: Dict[str, Any] = field(default_factory=dict)
    
    @classmethod
    def create(
        cls,
        event_type: AuditEventType,
        run_id: Optional[str] = None,
        **details
    ) -> 'AuditEvent':
        """Create a new audit event with current timestamp."""
        return cls(
            event_type=event_type,
            timestamp=datetime.now(timezone.utc).isoformat(timespec='seconds'),
            run_id=run_id,
            details=details,
        )
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            'event_type': self.event_type.value,
            'timestamp': self.timestamp,
            'run_id': self.run_id,
            'details': self.details,
        }


@dataclass
class ProcessingAuditSummary:
    """
    Summary of processing for audit purposes.
    
    Contains aggregate statistics only - NO individual file details
    that could identify patients.
    """
    run_id: str
    started_at: str
    completed_at: Optional[str] = None
    
    # Aggregate counts
    total_files_input: int = 0
    total_files_output: int = 0
    files_masked: int = 0
    files_anonymized: int = 0
    files_skipped: int = 0
    files_failed: int = 0
    
    # Region statistics
    total_regions_detected: int = 0
    regions_masked: int = 0
    regions_unmasked: int = 0
    manual_regions_added: int = 0
    
    # Processing mode (no PHI)
    gateway_profile: str = ""
    include_documents: bool = False
    include_images: bool = True
    
    # Hashes for integrity (not identifying)
    input_manifest_hash: Optional[str] = None
    output_manifest_hash: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            'run_id': self.run_id,
            'started_at': self.started_at,
            'completed_at': self.completed_at,
            'total_files_input': self.total_files_input,
            'total_files_output': self.total_files_output,
            'files_masked': self.files_masked,
            'files_anonymized': self.files_anonymized,
            'files_skipped': self.files_skipped,
            'files_failed': self.files_failed,
            'total_regions_detected': self.total_regions_detected,
            'regions_masked': self.regions_masked,
            'regions_unmasked': self.regions_unmasked,
            'manual_regions_added': self.manual_regions_added,
            'gateway_profile': self.gateway_profile,
            'include_documents': self.include_documents,
            'include_images': self.include_images,
            'input_manifest_hash': self.input_manifest_hash,
            'output_manifest_hash': self.output_manifest_hash,
        }


def create_scope_audit_block(
    include_images: bool,
    include_documents: bool,
    gateway_profile: str,
) -> str:
    """
    Generate an audit block for selection scope.
    
    This is a text block suitable for inclusion in audit logs.
    Contains NO PHI.
    
    Args:
        include_images: Whether images were included
        include_documents: Whether documents were included
        gateway_profile: The processing profile used
        
    Returns:
        Formatted audit block string
    """
    lines = [
        "=" * 60,
        "SELECTION SCOPE (Phase 6)",
        "=" * 60,
        f"Gateway Profile: {gateway_profile}",
        f"Include Images: {include_images}",
        f"Include Documents: {include_documents}",
        "=" * 60,
    ]
    return '\n'.join(lines)


def create_processing_stats(
    processing_time_seconds: float,
    total_input_bytes: int,
    total_output_bytes: int,
    file_count: int,
    masking_failures: int = 0,
) -> Dict[str, Any]:
    """
    Create processing statistics dict for UI display.
    
    Contains only aggregate statistics, no PHI.
    """
    throughput_mbps = 0.0
    if processing_time_seconds > 0 and total_input_bytes > 0:
        throughput_mbps = (total_input_bytes / (1024 * 1024)) / processing_time_seconds
    
    return {
        'processing_time_seconds': round(processing_time_seconds, 2),
        'total_input_bytes': total_input_bytes,
        'total_output_bytes': total_output_bytes,
        'total_input_mb': round(total_input_bytes / (1024 * 1024), 2),
        'total_output_mb': round(total_output_bytes / (1024 * 1024), 2),
        'file_count': file_count,
        'throughput_mbps': round(throughput_mbps, 2),
        'masking_failures': masking_failures,
    }
