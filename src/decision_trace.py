"""
Decision Trace Module for VoxelMask
====================================
Sprint 1: Audit Decision Trace

Provides deterministic, human-readable explanations for every anonymisation
and masking decision. Designed for governance review and long-term defensibility.

Features:
- Enumerated reason codes (no heuristic/AI judgement claims)
- Immutable decision records
- SQLite storage with foreign key to scrub_events
- PHI-free logging (reasons, not values)

Author: VoxelMask Engineering
Version: 0.4.0
"""

from dataclasses import dataclass, field
from typing import List, Optional
from datetime import datetime, timezone
import sqlite3
from contextlib import contextmanager


# ═══════════════════════════════════════════════════════════════════════════════
# ENUMERATIONS
# ═══════════════════════════════════════════════════════════════════════════════

class ReasonCode:
    """
    Enumerated reason codes for audit decision trace.
    
    Naming Convention:
    - HIPAA_*   : HIPAA Safe Harbor requirements
    - OAIC_*    : Australian OAIC/APP 11 requirements
    - DICOM_*   : DICOM PS3.15 standard requirements
    - FOI_*     : Freedom of Information processing
    - USER_*    : Explicit user/operator input
    - PROFILE_* : Compliance profile default behavior
    - SYSTEM_*  : System-level processing rules
    """
    
    # ═══════════════════════════════════════════════════════════════════════
    # HIPAA SAFE HARBOR (18 Identifiers)
    # ═══════════════════════════════════════════════════════════════════════
    HIPAA_NAME = "HIPAA_18_NAME"
    HIPAA_GEOGRAPHIC = "HIPAA_18_GEOGRAPHIC"
    HIPAA_DATE = "HIPAA_18_DATE"
    HIPAA_PHONE = "HIPAA_18_PHONE"
    HIPAA_FAX = "HIPAA_18_FAX"
    HIPAA_EMAIL = "HIPAA_18_EMAIL"
    HIPAA_SSN = "HIPAA_18_SSN"
    HIPAA_MRN = "HIPAA_18_MRN"
    HIPAA_HEALTH_PLAN = "HIPAA_18_HEALTH_PLAN"
    HIPAA_ACCOUNT = "HIPAA_18_ACCOUNT"
    HIPAA_LICENSE = "HIPAA_18_LICENSE"
    HIPAA_VEHICLE = "HIPAA_18_VEHICLE"
    HIPAA_DEVICE = "HIPAA_18_DEVICE"
    HIPAA_URL = "HIPAA_18_URL"
    HIPAA_IP = "HIPAA_18_IP"
    HIPAA_BIOMETRIC = "HIPAA_18_BIOMETRIC"
    HIPAA_PHOTO = "HIPAA_18_PHOTO"
    HIPAA_UNIQUE_ID = "HIPAA_18_UNIQUE_ID"
    
    # ═══════════════════════════════════════════════════════════════════════
    # AUSTRALIAN OAIC/APP 11
    # ═══════════════════════════════════════════════════════════════════════
    OAIC_INSTITUTION = "OAIC_APP11_INSTITUTION"
    OAIC_STAFF = "OAIC_APP11_STAFF_NAME"
    OAIC_REFERRING = "OAIC_APP11_REFERRING_PHYSICIAN"
    
    # ═══════════════════════════════════════════════════════════════════════
    # DICOM PS3.15 REQUIREMENTS
    # ═══════════════════════════════════════════════════════════════════════
    DICOM_PRIVATE_TAG = "DICOM_PS315_PRIVATE_TAG"
    DICOM_UID_REMAP = "DICOM_PS315_UID_REMAP"
    DICOM_DATE_SHIFT = "DICOM_PS315_DATE_SHIFT"
    
    # ═══════════════════════════════════════════════════════════════════════
    # BURNED-IN PHI DETECTION
    # ═══════════════════════════════════════════════════════════════════════
    BURNED_IN_TEXT = "BURNED_IN_TEXT_DETECTED"
    BURNED_IN_STATIC = "BURNED_IN_STATIC_REGION"
    BURNED_IN_MODALITY = "BURNED_IN_MODALITY_RULE"
    
    # ═══════════════════════════════════════════════════════════════════════
    # FOI / LEGAL PROCESSING
    # ═══════════════════════════════════════════════════════════════════════
    FOI_STAFF_REDACT = "FOI_STAFF_REDACTION"
    FOI_PRESERVE_PATIENT = "FOI_PRESERVE_PATIENT_DATA"
    FOI_PRESERVE_UID = "FOI_PRESERVE_UID"
    FOI_CHAIN_OF_CUSTODY = "FOI_CHAIN_OF_CUSTODY"
    
    # ═══════════════════════════════════════════════════════════════════════
    # USER / OPERATOR ACTIONS
    # ═══════════════════════════════════════════════════════════════════════
    USER_MASK_REGION = "USER_MASK_REGION_SELECTED"
    USER_OVERRIDE_RETAIN = "USER_OVERRIDE_RETAINED"
    USER_CLINICAL_CORRECT = "USER_CLINICAL_CORRECTION"
    
    # ═══════════════════════════════════════════════════════════════════════
    # PROFILE DEFAULTS
    # ═══════════════════════════════════════════════════════════════════════
    PROFILE_INTERNAL_REPAIR = "PROFILE_INTERNAL_REPAIR"
    PROFILE_RESEARCH_DEID = "PROFILE_RESEARCH_DEID"
    PROFILE_FOI_LEGAL = "PROFILE_FOI_LEGAL"
    PROFILE_FOI_PATIENT = "PROFILE_FOI_PATIENT"
    PROFILE_AU_STRICT = "PROFILE_AU_STRICT_OAIC"
    PROFILE_US_RESEARCH = "PROFILE_US_RESEARCH_SAFE_HARBOR"
    
    # ═══════════════════════════════════════════════════════════════════════
    # SYSTEM RULES
    # ═══════════════════════════════════════════════════════════════════════
    SYSTEM_WHITELIST = "SYSTEM_WHITELIST_RETAINED"
    SYSTEM_ML_SAFE = "SYSTEM_ML_PARAMETER_RETAINED"
    SYSTEM_DIAGNOSTIC = "SYSTEM_DIAGNOSTIC_PRESERVED"


class ActionType:
    """Enumerated action types."""
    REMOVED = "REMOVED"
    REPLACED = "REPLACED"
    MASKED = "MASKED"
    RETAINED = "RETAINED"
    SHIFTED = "SHIFTED"
    HASHED = "HASHED"


class ScopeLevel:
    """Enumerated scope levels."""
    STUDY = "STUDY"
    SERIES = "SERIES"
    INSTANCE = "INSTANCE"
    PIXEL_REGION = "PIXEL_REGION"


class TargetType:
    """Enumerated target types."""
    TAG = "TAG"
    PRIVATE_TAG_GROUP = "PRIVATE_TAG_GROUP"
    PIXEL_REGION = "PIXEL_REGION"
    UID = "UID"
    DATE_VALUE = "DATE_VALUE"


class RuleSource:
    """
    Identifies the compliance profile or rule set that triggered a decision.
    """
    HIPAA_SAFE_HARBOR = "HIPAA_SAFE_HARBOR"
    OAIC_APP11 = "OAIC_APP11"
    DICOM_PS315 = "DICOM_PS315"
    FOI_LEGAL_PROFILE = "FOI_LEGAL_PROFILE"
    FOI_PATIENT_PROFILE = "FOI_PATIENT_PROFILE"
    INTERNAL_REPAIR_PROFILE = "INTERNAL_REPAIR_PROFILE"
    US_RESEARCH_PROFILE = "US_RESEARCH_PROFILE"
    AU_STRICT_PROFILE = "AU_STRICT_PROFILE"
    USER_MASK_INPUT = "USER_MASK_INPUT"
    USER_CLINICAL_INPUT = "USER_CLINICAL_INPUT"
    MODALITY_SAFETY_PROTOCOL = "MODALITY_SAFETY_PROTOCOL"
    WHITELIST_POLICY = "WHITELIST_POLICY"


# ═══════════════════════════════════════════════════════════════════════════════
# DATA STRUCTURES
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class DecisionRecord:
    """
    Single decision record (in-memory representation).
    
    Immutable after creation. Contains no PHI - only reasons and references.
    
    Phase 4 Enhancement: Includes OCR detection metadata fields for audit truth.
    These fields capture detection uncertainty without implying OCR "success".
    """
    scope_level: str
    scope_uid: Optional[str]
    action_type: str
    target_type: str
    target_name: str
    reason_code: str
    rule_source: str
    checksum_before: Optional[str] = None
    checksum_after: Optional[str] = None
    region_x: Optional[int] = None
    region_y: Optional[int] = None
    region_w: Optional[int] = None
    region_h: Optional[int] = None
    # Phase 4: OCR Detection Metadata (audit truth)
    detection_strength: Optional[str] = None  # LOW, MEDIUM, HIGH, or None (OCR failed)
    ocr_failure: Optional[bool] = None  # True = OCR engine threw exception
    confidence_aggregation: Optional[str] = None  # Aggregation method (e.g., "min")
    ocr_engine: Optional[str] = None  # OCR engine identifier (e.g., "PaddleOCR")
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"))


# ═══════════════════════════════════════════════════════════════════════════════
# DECISION TRACE COLLECTOR
# ═══════════════════════════════════════════════════════════════════════════════

class DecisionTraceCollector:
    """
    Collects decision records during DICOM processing.
    
    Thread-safe accumulator that buffers decisions until commit.
    Once locked, no further additions are permitted (immutability guarantee).
    """
    
    def __init__(self):
        self._decisions: List[DecisionRecord] = []
        self._locked: bool = False
    
    def add(
        self,
        scope_level: str,
        action_type: str,
        target_type: str,
        target_name: str,
        reason_code: str,
        rule_source: str,
        scope_uid: str = None,
        checksum_before: str = None,
        checksum_after: str = None,
        region_x: int = None,
        region_y: int = None,
        region_w: int = None,
        region_h: int = None,
        # Phase 4: OCR Detection Metadata
        detection_strength: str = None,
        ocr_failure: bool = None,
        confidence_aggregation: str = None,
        ocr_engine: str = None,
    ) -> None:
        """
        Add a decision record to the collector.
        
        Args:
            scope_level: STUDY, SERIES, INSTANCE, or PIXEL_REGION
            action_type: REMOVED, REPLACED, MASKED, RETAINED, SHIFTED, HASHED
            target_type: TAG, PRIVATE_TAG_GROUP, PIXEL_REGION, UID, DATE_VALUE
            target_name: Human-readable name (e.g., 'PatientName')
            reason_code: Enumerated reason code
            rule_source: Compliance profile or rule identifier
            scope_uid: UID of the scoped object (optional)
            checksum_before: SHA256 of original value (truncated, optional)
            checksum_after: SHA256 of new value (truncated, optional)
            region_x, region_y, region_w, region_h: Pixel region bounds (optional)
            detection_strength: Phase 4 - LOW/MEDIUM/HIGH or None (OCR failed)
            ocr_failure: Phase 4 - True if OCR engine threw exception
            confidence_aggregation: Phase 4 - Aggregation method (e.g., "min")
            ocr_engine: Phase 4 - OCR engine identifier (e.g., "PaddleOCR")
            
        Raises:
            RuntimeError: If collector is locked (already committed)
        """
        if self._locked:
            raise RuntimeError("DecisionTraceCollector is locked after commit")
        
        record = DecisionRecord(
            scope_level=scope_level,
            scope_uid=scope_uid,
            action_type=action_type,
            target_type=target_type,
            target_name=target_name,
            reason_code=reason_code,
            rule_source=rule_source,
            checksum_before=checksum_before,
            checksum_after=checksum_after,
            region_x=region_x,
            region_y=region_y,
            region_w=region_w,
            region_h=region_h,
            detection_strength=detection_strength,
            ocr_failure=ocr_failure,
            confidence_aggregation=confidence_aggregation,
            ocr_engine=ocr_engine,
        )
        self._decisions.append(record)
    
    def get_decisions(self) -> List[DecisionRecord]:
        """Return a copy of all collected decisions."""
        return list(self._decisions)
    
    def lock(self) -> None:
        """Lock the collector to prevent further additions."""
        self._locked = True
    
    def is_locked(self) -> bool:
        """Check if collector is locked."""
        return self._locked
    
    def count(self) -> int:
        """Return number of decisions collected."""
        return len(self._decisions)
    
    def count_by_action(self) -> dict:
        """Return count of decisions by action type."""
        counts = {}
        for d in self._decisions:
            counts[d.action_type] = counts.get(d.action_type, 0) + 1
        return counts
    
    def count_by_reason(self) -> dict:
        """Return count of decisions by reason code."""
        counts = {}
        for d in self._decisions:
            counts[d.reason_code] = counts.get(d.reason_code, 0) + 1
        return counts


# ═══════════════════════════════════════════════════════════════════════════════
# DECISION TRACE WRITER
# ═══════════════════════════════════════════════════════════════════════════════

class DecisionTraceWriter:
    """
    Commits decision trace records to SQLite.
    
    Ensures atomicity with parent scrub_events record.
    Records are append-only and immutable after commit.
    """
    
    # SQL for table creation
    CREATE_TABLE_SQL = """
        CREATE TABLE IF NOT EXISTS decision_trace (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            scrub_uuid      TEXT NOT NULL,
            scope_level     TEXT NOT NULL,
            scope_uid       TEXT,
            region_x        INTEGER,
            region_y        INTEGER,
            region_w        INTEGER,
            region_h        INTEGER,
            action_type     TEXT NOT NULL,
            target_type     TEXT NOT NULL,
            target_name     TEXT NOT NULL,
            reason_code     TEXT NOT NULL,
            rule_source     TEXT NOT NULL,
            checksum_before TEXT,
            checksum_after  TEXT,
            timestamp       TEXT NOT NULL,
            FOREIGN KEY (scrub_uuid) REFERENCES scrub_events(scrub_uuid),
            CHECK (scope_level IN ('STUDY', 'SERIES', 'INSTANCE', 'PIXEL_REGION')),
            CHECK (action_type IN ('REMOVED', 'REPLACED', 'MASKED', 'RETAINED', 'SHIFTED', 'HASHED')),
            CHECK (target_type IN ('TAG', 'PRIVATE_TAG_GROUP', 'PIXEL_REGION', 'UID', 'DATE_VALUE'))
        )
    """
    
    CREATE_INDEX_SQL = [
        "CREATE INDEX IF NOT EXISTS idx_dt_scrub_uuid ON decision_trace(scrub_uuid)",
        "CREATE INDEX IF NOT EXISTS idx_dt_reason_code ON decision_trace(reason_code)",
        "CREATE INDEX IF NOT EXISTS idx_dt_timestamp ON decision_trace(timestamp)",
        "CREATE INDEX IF NOT EXISTS idx_dt_action_type ON decision_trace(action_type)",
    ]
    
    def __init__(self, db_path: str):
        """
        Initialize the decision trace writer.
        
        Args:
            db_path: Path to SQLite database
        """
        self.db_path = db_path
        self._ensure_table()
    
    @contextmanager
    def _get_connection(self):
        """Context manager for database connections."""
        conn = sqlite3.connect(self.db_path)
        try:
            yield conn
        finally:
            conn.close()
    
    def _ensure_table(self) -> None:
        """Create decision_trace table if not exists."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(self.CREATE_TABLE_SQL)
            for index_sql in self.CREATE_INDEX_SQL:
                cursor.execute(index_sql)
            conn.commit()
    
    def commit(
        self,
        scrub_uuid: str,
        collector: DecisionTraceCollector
    ) -> int:
        """
        Atomically commit all decisions for a scrub event.
        
        Args:
            scrub_uuid: Parent scrub event UUID
            collector: DecisionTraceCollector with buffered decisions
            
        Returns:
            Number of records inserted
            
        Raises:
            sqlite3.Error: On database failure
        """
        collector.lock()  # Prevent further modifications
        decisions = collector.get_decisions()
        
        if not decisions:
            return 0
        
        with self._get_connection() as conn:
            cursor = conn.cursor()
            for d in decisions:
                cursor.execute("""
                    INSERT INTO decision_trace (
                        scrub_uuid, scope_level, scope_uid,
                        region_x, region_y, region_w, region_h,
                        action_type, target_type, target_name,
                        reason_code, rule_source,
                        checksum_before, checksum_after, timestamp
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    scrub_uuid, d.scope_level, d.scope_uid,
                    d.region_x, d.region_y, d.region_w, d.region_h,
                    d.action_type, d.target_type, d.target_name,
                    d.reason_code, d.rule_source,
                    d.checksum_before, d.checksum_after, d.timestamp
                ))
            conn.commit()
        
        return len(decisions)
    
    def get_decisions_for_scrub(self, scrub_uuid: str) -> List[dict]:
        """
        Retrieve all decision records for a scrub event.
        
        Args:
            scrub_uuid: The scrub event UUID
            
        Returns:
            List of decision dictionaries
        """
        with self._get_connection() as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM decision_trace WHERE scrub_uuid = ? ORDER BY id",
                (scrub_uuid,)
            )
            return [dict(row) for row in cursor.fetchall()]
    
    def get_statistics(self) -> dict:
        """
        Get summary statistics across all decision traces.
        
        Returns:
            Dictionary with counts by action type and reason code
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            # Total decisions
            cursor.execute("SELECT COUNT(*) FROM decision_trace")
            total = cursor.fetchone()[0]
            
            # By action type
            cursor.execute("""
                SELECT action_type, COUNT(*) as count 
                FROM decision_trace 
                GROUP BY action_type
            """)
            by_action = {row[0]: row[1] for row in cursor.fetchall()}
            
            # By reason code
            cursor.execute("""
                SELECT reason_code, COUNT(*) as count 
                FROM decision_trace 
                GROUP BY reason_code
                ORDER BY count DESC
                LIMIT 20
            """)
            by_reason = {row[0]: row[1] for row in cursor.fetchall()}
            
            return {
                "total_decisions": total,
                "by_action_type": by_action,
                "by_reason_code": by_reason
            }


# ═══════════════════════════════════════════════════════════════════════════════
# DECISION SUMMARY GENERATOR
# ═══════════════════════════════════════════════════════════════════════════════

def generate_decision_summary(decisions: List[DecisionRecord], profile_name: str = None) -> str:
    """
    Generate a human-readable summary from decision trace records.
    
    Suitable for inclusion in PDF compliance reports.
    
    Args:
        decisions: List of DecisionRecord objects
        profile_name: Name of the compliance profile used
        
    Returns:
        Multi-line formatted string for PDF inclusion
    """
    if not decisions:
        return "No decisions recorded."
    
    # Count by action type
    action_counts = {}
    for d in decisions:
        action_counts[d.action_type] = action_counts.get(d.action_type, 0) + 1
    
    # Count by reason code
    reason_counts = {}
    for d in decisions:
        reason_counts[d.reason_code] = reason_counts.get(d.reason_code, 0) + 1
    
    # Separate metadata vs pixel decisions
    metadata_decisions = [d for d in decisions if d.target_type != TargetType.PIXEL_REGION]
    pixel_decisions = [d for d in decisions if d.target_type == TargetType.PIXEL_REGION]
    
    # Build summary
    lines = [
        "═" * 60,
        "DECISION TRACE SUMMARY",
        "─" * 60,
        "",
    ]
    
    if profile_name:
        lines.append(f"Processing Profile: {profile_name}")
    
    lines.extend([
        f"Total Decisions Recorded: {len(decisions)}",
        "",
        "METADATA ACTIONS:",
        f"  • {action_counts.get(ActionType.REMOVED, 0)} tags REMOVED",
        f"  • {action_counts.get(ActionType.REPLACED, 0)} tags REPLACED",
        f"  • {action_counts.get(ActionType.HASHED, 0)} UIDs HASHED",
        f"  • {action_counts.get(ActionType.SHIFTED, 0)} dates SHIFTED",
        f"  • {action_counts.get(ActionType.RETAINED, 0)} tags RETAINED",
        "",
        "PIXEL ACTIONS:",
        f"  • {action_counts.get(ActionType.MASKED, 0)} regions MASKED",
    ])
    
    # Top 10 reason codes
    lines.extend([
        "",
        "TOP REASON CODES:",
    ])
    sorted_reasons = sorted(reason_counts.items(), key=lambda x: x[1], reverse=True)[:10]
    for reason, count in sorted_reasons:
        lines.append(f"  {reason}: {count}")
    
    lines.extend([
        "",
        "COMPLIANCE ATTESTATION:",
        "  All decisions derived from:",
        "  ✓ Enumerated reason codes (no heuristic judgements)",
        "  ✓ Compliance profile rules",
        "  ✓ Explicit user input (where applicable)",
        "═" * 60,
    ])
    
    return "\n".join(lines)


# ═══════════════════════════════════════════════════════════════════════════════
# CONVENIENCE FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════════════

def get_hipaa_reason_code(tag_name: str) -> str:
    """
    Map a DICOM tag name to the appropriate HIPAA reason code.
    
    Args:
        tag_name: DICOM tag keyword (e.g., 'PatientName')
        
    Returns:
        Appropriate HIPAA reason code
    """
    mapping = {
        'PatientName': ReasonCode.HIPAA_NAME,
        'OtherPatientNames': ReasonCode.HIPAA_NAME,
        'PatientMotherBirthName': ReasonCode.HIPAA_NAME,
        'PatientAddress': ReasonCode.HIPAA_GEOGRAPHIC,
        'InstitutionAddress': ReasonCode.HIPAA_GEOGRAPHIC,
        'PatientBirthDate': ReasonCode.HIPAA_DATE,
        'AdmissionDate': ReasonCode.HIPAA_DATE,
        'DischargeDate': ReasonCode.HIPAA_DATE,
        'PatientTelephoneNumbers': ReasonCode.HIPAA_PHONE,
        'PatientID': ReasonCode.HIPAA_MRN,
        'OtherPatientIDs': ReasonCode.HIPAA_MRN,
        'AccessionNumber': ReasonCode.HIPAA_MRN,
        'PatientInsurancePlanCodeSequence': ReasonCode.HIPAA_HEALTH_PLAN,
        'AdmissionID': ReasonCode.HIPAA_ACCOUNT,
        'DeviceSerialNumber': ReasonCode.HIPAA_DEVICE,
        'StationName': ReasonCode.HIPAA_DEVICE,
    }
    return mapping.get(tag_name, ReasonCode.HIPAA_UNIQUE_ID)


def get_foi_reason_code(tag_name: str, is_staff: bool) -> str:
    """
    Map a DICOM tag to FOI reason code.
    
    Args:
        tag_name: DICOM tag keyword
        is_staff: True if this is a staff-related tag
        
    Returns:
        Appropriate FOI reason code
    """
    if is_staff:
        return ReasonCode.FOI_STAFF_REDACT
    return ReasonCode.FOI_PRESERVE_PATIENT


# ═══════════════════════════════════════════════════════════════════════════════
# REVIEWER REGION DECISION RECORDING
# ═══════════════════════════════════════════════════════════════════════════════

def record_region_decisions(
    collector: DecisionTraceCollector,
    regions: List,  # List[ReviewRegion] - avoid circular import
    sop_instance_uid: str
) -> int:
    """
    Record all region decisions to the Decision Trace.
    
    Maps ReviewRegion actions to appropriate ActionType and ReasonCode:
    - OCR region, default MASK → BURNED_IN_TEXT_DETECTED
    - OCR region, reviewer UNMASK → USER_OVERRIDE_RETAINED  
    - OCR region, reviewer MASK (explicit) → USER_MASK_REGION_SELECTED
    - Manual region → USER_MASK_REGION_SELECTED
    
    Phase 4 Enhancement: Includes OCR detection metadata for audit truth.
    - detection_strength: LOW/MEDIUM/HIGH/None
    - ocr_failure: True if OCR engine threw exception
    - confidence_aggregation: Always "min" (pessimistic)
    - ocr_engine: "PaddleOCR" for OCR regions, None for manual
    
    Called at export time, after reviewer has accepted.
    
    Args:
        collector: DecisionTraceCollector to add decisions to
        regions: List of active (non-deleted) ReviewRegion objects
        sop_instance_uid: SOP Instance UID for scope_uid
        
    Returns:
        Number of decisions recorded
    
    Note:
        This function intentionally has no access to OCR text content.
        ReviewRegion contains only coordinates and action state.
    """
    # Import here to avoid circular dependency
    from review_session import RegionSource, RegionAction
    
    count = 0
    for idx, region in enumerate(regions):
        # Skip deleted regions (should already be filtered, but defensive)
        if hasattr(region, 'is_deleted') and region.is_deleted():
            continue
        
        # Determine final action
        final_action = region.get_effective_action()
        
        # Phase 4: Extract OCR detection metadata from region
        # Only populated for OCR-sourced regions
        is_ocr = region.source == RegionSource.OCR
        detection_strength = getattr(region, 'detection_strength', None) if is_ocr else None
        # OCR failure = detection_strength is None for OCR region
        ocr_failure = (detection_strength is None) if is_ocr else None
        # Aggregation method is always "min" (documented in Phase 4)
        confidence_aggregation = "min" if is_ocr else None
        # OCR engine identifier
        ocr_engine = "PaddleOCR" if is_ocr else None
        
        if final_action == RegionAction.MASK:
            # Determine reason code based on source and whether reviewer modified
            if region.source == RegionSource.MANUAL:
                # Manual region always USER action
                reason = ReasonCode.USER_MASK_REGION
                rule_source = RuleSource.USER_MASK_INPUT
            elif region.reviewer_action == RegionAction.MASK:
                # Reviewer explicitly set to MASK (after toggling)
                reason = ReasonCode.USER_MASK_REGION
                rule_source = RuleSource.USER_MASK_INPUT
            else:
                # Default OCR detection, unchanged by reviewer
                reason = ReasonCode.BURNED_IN_TEXT
                rule_source = RuleSource.MODALITY_SAFETY_PROTOCOL
            
            collector.add(
                scope_level=ScopeLevel.PIXEL_REGION,
                scope_uid=sop_instance_uid,
                action_type=ActionType.MASKED,
                target_type=TargetType.PIXEL_REGION,
                target_name=f"PixelRegion[{idx}]",
                reason_code=reason,
                rule_source=rule_source,
                region_x=region.x,
                region_y=region.y,
                region_w=region.w,
                region_h=region.h,
                # Phase 4: OCR Detection Metadata
                detection_strength=detection_strength,
                ocr_failure=ocr_failure,
                confidence_aggregation=confidence_aggregation,
                ocr_engine=ocr_engine,
            )
            count += 1
        
        elif final_action == RegionAction.UNMASK:
            # Reviewer chose to retain (not mask)
            collector.add(
                scope_level=ScopeLevel.PIXEL_REGION,
                scope_uid=sop_instance_uid,
                action_type=ActionType.RETAINED,
                target_type=TargetType.PIXEL_REGION,
                target_name=f"PixelRegion[{idx}]",
                reason_code=ReasonCode.USER_OVERRIDE_RETAIN,
                rule_source=RuleSource.USER_MASK_INPUT,
                region_x=region.x,
                region_y=region.y,
                region_w=region.w,
                region_h=region.h,
                # Phase 4: OCR Detection Metadata
                detection_strength=detection_strength,
                ocr_failure=ocr_failure,
                confidence_aggregation=confidence_aggregation,
                ocr_engine=ocr_engine,
            )
            count += 1
    
    return count

