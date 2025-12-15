# Sprint 1: Audit Decision Trace — Architecture Design

**Version:** 1.0  
**Date:** 2025-12-15  
**Status:** Draft for Senior Engineering Review  
**Author:** VoxelMask Engineering  
**Document Type:** Technical Design Document

---

## 1. Executive Summary

This document specifies the **Audit Decision Trace** subsystem for VoxelMask v0.4.0. The subsystem provides deterministic, human-readable explanations for every anonymisation and masking decision, enabling governance review and long-term defensibility.

### Design Principles

1. **Explainability over opacity** — Every decision traceable to a rule, profile, or explicit user input
2. **Immutability** — Audit records cannot be modified after commit
3. **PHI isolation** — Decision logs contain *reasons*, not *values*
4. **Boring predictability** — No heuristics, no probabilistic language, no AI judgement claims

### What This System Is Not

- Not a clinical decision support system
- Not a diagnostic aid
- Not a PACS router or integration layer
- Not a data retention/archival system beyond decision traceability

---

## 2. Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           VoxelMask Processing Pipeline                     │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌──────────────┐    ┌──────────────────┐    ┌──────────────────────────┐  │
│  │ Input DICOM  │───▶│ Compliance Engine │───▶│ anonymize_metadata()     │  │
│  │              │    │ (profile select)  │    │                          │  │
│  └──────────────┘    └────────┬─────────┘    └────────────┬─────────────┘  │
│                               │                           │                 │
│                               ▼                           ▼                 │
│                      ┌────────────────┐          ┌────────────────────┐    │
│                      │ Decision Trace │◀─────────│ Burned-in PHI      │    │
│                      │ Collector      │          │ Masking            │    │
│                      └───────┬────────┘          └────────────────────┘    │
│                              │                                              │
│                              ▼                                              │
│  ┌──────────────────────────────────────────────────────────────────────┐  │
│  │                     SQLite: decision_trace table                      │  │
│  │  (append-only, FK → scrub_events.scrub_uuid)                         │  │
│  └──────────────────────────────────────────────────────────────────────┘  │
│                              │                                              │
│                              ▼                                              │
│  ┌──────────────────────────────────────────────────────────────────────┐  │
│  │                     PDF Report: Decision Summary                      │  │
│  └──────────────────────────────────────────────────────────────────────┘  │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Component Responsibilities

| Component | Responsibility | Writes To |
|-----------|----------------|-----------|
| `DecisionTraceCollector` | Accumulates decisions during processing | In-memory buffer |
| `DecisionTraceWriter` | Commits decisions atomically with scrub event | `decision_trace` table |
| `DecisionSummarizer` | Generates human-readable summary for PDF | Report buffer |

---

## 3. Schema Definitions

### 3.1 New Table: `decision_trace`

```sql
CREATE TABLE IF NOT EXISTS decision_trace (
    -- Primary key
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    
    -- Foreign key to parent scrub event (immutable reference)
    scrub_uuid      TEXT NOT NULL,
    
    -- Scope: What this decision applies to
    scope_level     TEXT NOT NULL,   -- ENUM: 'STUDY', 'SERIES', 'INSTANCE', 'PIXEL_REGION'
    scope_uid       TEXT,            -- UID of the scoped object (StudyInstanceUID, SeriesInstanceUID, SOPInstanceUID)
    
    -- For pixel-region scope only (nullable for metadata decisions)
    region_x        INTEGER,
    region_y        INTEGER,
    region_w        INTEGER,
    region_h        INTEGER,
    
    -- Action taken
    action_type     TEXT NOT NULL,   -- ENUM: 'REMOVED', 'REPLACED', 'MASKED', 'RETAINED', 'SHIFTED', 'HASHED'
    
    -- Target (what was acted upon)
    target_type     TEXT NOT NULL,   -- ENUM: 'TAG', 'PRIVATE_TAG_GROUP', 'PIXEL_REGION', 'UID', 'DATE_VALUE'
    target_name     TEXT NOT NULL,   -- Human-readable name: 'PatientName', 'PixelRegion[0]', 'StudyInstanceUID'
    
    -- Reason (deterministic, enumerated)
    reason_code     TEXT NOT NULL,   -- From REASON_CODES taxonomy
    
    -- Rule/profile that triggered this decision
    rule_source     TEXT NOT NULL,   -- 'HIPAA_SAFE_HARBOR', 'OAIC_APP11', 'USER_MASK_INPUT', 'FOI_LEGAL_PROFILE', etc.
    
    -- Verification
    checksum_before TEXT,            -- SHA256 of original value (for pixel regions: hash of bounding box)
    checksum_after  TEXT,            -- SHA256 of post-action value (for REMOVED: NULL)
    
    -- Timestamp (UTC, immutable)
    timestamp       TEXT NOT NULL,
    
    -- Constraints
    FOREIGN KEY (scrub_uuid) REFERENCES scrub_events(scrub_uuid),
    CHECK (scope_level IN ('STUDY', 'SERIES', 'INSTANCE', 'PIXEL_REGION')),
    CHECK (action_type IN ('REMOVED', 'REPLACED', 'MASKED', 'RETAINED', 'SHIFTED', 'HASHED')),
    CHECK (target_type IN ('TAG', 'PRIVATE_TAG_GROUP', 'PIXEL_REGION', 'UID', 'DATE_VALUE'))
);

-- Indices for governance queries
CREATE INDEX IF NOT EXISTS idx_dt_scrub_uuid ON decision_trace(scrub_uuid);
CREATE INDEX IF NOT EXISTS idx_dt_reason_code ON decision_trace(reason_code);
CREATE INDEX IF NOT EXISTS idx_dt_timestamp ON decision_trace(timestamp);
CREATE INDEX IF NOT EXISTS idx_dt_action_type ON decision_trace(action_type);
```

### 3.2 Existing Table: `scrub_events` (No Changes)

The existing `scrub_events` table remains unchanged. The `decision_trace` table references it via `scrub_uuid` foreign key. This maintains backward compatibility.

---

## 4. Enumerations

### 4.1 Reason Code Taxonomy

Reason codes are deterministic, governance-friendly identifiers. Each code maps to a specific rule or input type.

```python
# reason_codes.py - Canonical Reason Code Taxonomy

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
    HIPAA_NAME = "HIPAA_18_NAME"                           # Names
    HIPAA_GEOGRAPHIC = "HIPAA_18_GEOGRAPHIC"               # Geographic subdivisions
    HIPAA_DATE = "HIPAA_18_DATE"                           # Dates (except year)
    HIPAA_PHONE = "HIPAA_18_PHONE"                         # Phone numbers
    HIPAA_FAX = "HIPAA_18_FAX"                             # Fax numbers
    HIPAA_EMAIL = "HIPAA_18_EMAIL"                         # Email addresses
    HIPAA_SSN = "HIPAA_18_SSN"                             # Social Security numbers
    HIPAA_MRN = "HIPAA_18_MRN"                             # Medical record numbers
    HIPAA_HEALTH_PLAN = "HIPAA_18_HEALTH_PLAN"             # Health plan numbers
    HIPAA_ACCOUNT = "HIPAA_18_ACCOUNT"                     # Account numbers
    HIPAA_LICENSE = "HIPAA_18_LICENSE"                     # Certificate/license numbers
    HIPAA_VEHICLE = "HIPAA_18_VEHICLE"                     # Vehicle identifiers
    HIPAA_DEVICE = "HIPAA_18_DEVICE"                       # Device identifiers
    HIPAA_URL = "HIPAA_18_URL"                             # Web URLs
    HIPAA_IP = "HIPAA_18_IP"                               # IP addresses
    HIPAA_BIOMETRIC = "HIPAA_18_BIOMETRIC"                 # Biometric identifiers
    HIPAA_PHOTO = "HIPAA_18_PHOTO"                         # Full-face photos
    HIPAA_UNIQUE_ID = "HIPAA_18_UNIQUE_ID"                 # Unique identifiers
    
    # ═══════════════════════════════════════════════════════════════════════
    # AUSTRALIAN OAIC/APP 11
    # ═══════════════════════════════════════════════════════════════════════
    OAIC_INSTITUTION = "OAIC_APP11_INSTITUTION"            # Institution identifiers
    OAIC_STAFF = "OAIC_APP11_STAFF_NAME"                   # Staff/physician names
    OAIC_REFERRING = "OAIC_APP11_REFERRING_PHYSICIAN"      # Referring physician
    
    # ═══════════════════════════════════════════════════════════════════════
    # DICOM PS3.15 REQUIREMENTS
    # ═══════════════════════════════════════════════════════════════════════
    DICOM_PRIVATE_TAG = "DICOM_PS315_PRIVATE_TAG"          # Private tag removal
    DICOM_UID_REMAP = "DICOM_PS315_UID_REMAP"              # UID remapping
    DICOM_DATE_SHIFT = "DICOM_PS315_DATE_SHIFT"            # Date shifting
    
    # ═══════════════════════════════════════════════════════════════════════
    # BURNED-IN PHI DETECTION
    # ═══════════════════════════════════════════════════════════════════════
    BURNED_IN_TEXT = "BURNED_IN_TEXT_DETECTED"             # OCR detected text
    BURNED_IN_STATIC = "BURNED_IN_STATIC_REGION"           # Static region across frames
    BURNED_IN_MODALITY = "BURNED_IN_MODALITY_RULE"         # US/SC/OT modality rule
    
    # ═══════════════════════════════════════════════════════════════════════
    # FOI / LEGAL PROCESSING
    # ═══════════════════════════════════════════════════════════════════════
    FOI_STAFF_REDACT = "FOI_STAFF_REDACTION"               # Staff name redaction (FOI)
    FOI_PRESERVE_PATIENT = "FOI_PRESERVE_PATIENT_DATA"     # Patient data preserved (FOI)
    FOI_PRESERVE_UID = "FOI_PRESERVE_UID"                  # UIDs preserved (Legal)
    FOI_CHAIN_OF_CUSTODY = "FOI_CHAIN_OF_CUSTODY"          # Chain of custody requirement
    
    # ═══════════════════════════════════════════════════════════════════════
    # USER / OPERATOR ACTIONS
    # ═══════════════════════════════════════════════════════════════════════
    USER_MASK_REGION = "USER_MASK_REGION_SELECTED"         # User-selected pixel mask
    USER_OVERRIDE_RETAIN = "USER_OVERRIDE_RETAINED"        # User chose to retain
    USER_CLINICAL_CORRECT = "USER_CLINICAL_CORRECTION"     # Clinical correction input
    
    # ═══════════════════════════════════════════════════════════════════════
    # PROFILE DEFAULTS
    # ═══════════════════════════════════════════════════════════════════════
    PROFILE_INTERNAL_REPAIR = "PROFILE_INTERNAL_REPAIR"    # Internal repair mode
    PROFILE_RESEARCH_DEID = "PROFILE_RESEARCH_DEID"        # Research de-identification
    PROFILE_FOI_LEGAL = "PROFILE_FOI_LEGAL"                # FOI Legal mode
    PROFILE_FOI_PATIENT = "PROFILE_FOI_PATIENT"            # FOI Patient mode
    PROFILE_AU_STRICT = "PROFILE_AU_STRICT_OAIC"           # AU Strict OAIC
    PROFILE_US_RESEARCH = "PROFILE_US_RESEARCH_SAFE_HARBOR"  # US Research Safe Harbor
    
    # ═══════════════════════════════════════════════════════════════════════
    # SYSTEM RULES
    # ═══════════════════════════════════════════════════════════════════════
    SYSTEM_WHITELIST = "SYSTEM_WHITELIST_RETAINED"         # Tag on safe whitelist
    SYSTEM_ML_SAFE = "SYSTEM_ML_PARAMETER_RETAINED"        # ML-critical parameter
    SYSTEM_DIAGNOSTIC = "SYSTEM_DIAGNOSTIC_PRESERVED"      # Diagnostic anatomy preserved


class ActionType:
    """Enumerated action types."""
    REMOVED = "REMOVED"       # Tag/value deleted entirely
    REPLACED = "REPLACED"     # Value replaced with anonymized value
    MASKED = "MASKED"         # Pixel region obscured
    RETAINED = "RETAINED"     # Explicitly kept (with reason)
    SHIFTED = "SHIFTED"       # Date shifted by offset
    HASHED = "HASHED"         # Value hashed (e.g., PatientID → hash)


class ScopeLevel:
    """Enumerated scope levels."""
    STUDY = "STUDY"           # Decision applies to entire study
    SERIES = "SERIES"         # Decision applies to series
    INSTANCE = "INSTANCE"     # Decision applies to single SOP instance
    PIXEL_REGION = "PIXEL_REGION"  # Decision applies to pixel bounding box


class TargetType:
    """Enumerated target types."""
    TAG = "TAG"                         # DICOM tag
    PRIVATE_TAG_GROUP = "PRIVATE_TAG_GROUP"  # Private tag group (odd-numbered)
    PIXEL_REGION = "PIXEL_REGION"       # Pixel bounding box
    UID = "UID"                         # DICOM UID
    DATE_VALUE = "DATE_VALUE"           # Date value
```

### 4.2 Rule Source Identifiers

```python
class RuleSource:
    """
    Identifies the compliance profile or rule set that triggered a decision.
    Maps to compliance_engine.py profile modes.
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
```

---

## 5. Integration Points

### 5.1 Integration with `anonymize_metadata()`

**Location:** `src/run_on_dicom.py`, lines 32–281

**Integration Strategy:**

```python
def anonymize_metadata(
    ds: pydicom.Dataset,
    new_name: str,
    research_context: dict = None,
    clinical_context: dict = None,
    decision_collector: DecisionTraceCollector = None  # NEW PARAMETER
):
    """
    Anonymize DICOM metadata by removing/replacing PHI tags.
    
    If decision_collector is provided, all decisions are recorded.
    """
    # Example: Recording a PatientName removal decision
    if decision_collector:
        decision_collector.add(
            scope_level=ScopeLevel.INSTANCE,
            scope_uid=ds.SOPInstanceUID,
            action_type=ActionType.REPLACED,
            target_type=TargetType.TAG,
            target_name="PatientName",
            reason_code=ReasonCode.HIPAA_NAME,
            rule_source=RuleSource.HIPAA_SAFE_HARBOR,
            checksum_before=hashlib.sha256(str(ds.PatientName).encode()).hexdigest()[:16],
            checksum_after=hashlib.sha256(new_name.encode()).hexdigest()[:16]
        )
    
    # ... existing anonymization logic ...
```

**Instrumentation Locations (within `anonymize_metadata`):**

| Line Range | Action | Reason Code |
|------------|--------|-------------|
| PatientName assignment | REPLACED | HIPAA_18_NAME |
| PatientID assignment | REPLACED or HASHED | HIPAA_18_MRN |
| Date shifting block | SHIFTED | DICOM_PS315_DATE_SHIFT |
| UID regeneration | HASHED | DICOM_PS315_UID_REMAP |
| Private tag removal loop | REMOVED | DICOM_PS315_PRIVATE_TAG |
| AccessionNumber removal | REMOVED | HIPAA_18_MRN |
| Research context UID remap | HASHED | PROFILE_RESEARCH_DEID |

---

### 5.2 Integration with Burned-in PHI Masking

**Location:** `src/run_on_dicom.py` → `detect_text_box_from_array()` and pixel masking in `process_dicom()`

**Integration Strategy:**

```python
def apply_pixel_mask(
    pixel_array: np.ndarray,
    mask_boxes: List[Tuple[int, int, int, int]],
    modality: str,
    decision_collector: DecisionTraceCollector = None
):
    """
    Apply pixel masking to detected or user-specified regions.
    """
    for idx, (x, y, w, h) in enumerate(mask_boxes):
        # Determine reason code
        reason = ReasonCode.USER_MASK_REGION if is_user_selected else ReasonCode.BURNED_IN_TEXT
        rule = RuleSource.USER_MASK_INPUT if is_user_selected else RuleSource.MODALITY_SAFETY_PROTOCOL
        
        if decision_collector:
            decision_collector.add(
                scope_level=ScopeLevel.PIXEL_REGION,
                scope_uid=sop_instance_uid,
                region_x=x, region_y=y, region_w=w, region_h=h,
                action_type=ActionType.MASKED,
                target_type=TargetType.PIXEL_REGION,
                target_name=f"PixelRegion[{idx}]",
                reason_code=reason,
                rule_source=rule,
                checksum_before=compute_region_hash(pixel_array, x, y, w, h)
            )
        
        # Apply black rectangle mask
        pixel_array[y:y+h, x:x+w] = 0
```

**Decision Recording for Modality Skip:**

```python
# In process_dicom() — when masking is skipped for CT/MRI/etc.
if modality not in {'US', 'SC', 'OT'}:
    if decision_collector:
        decision_collector.add(
            scope_level=ScopeLevel.INSTANCE,
            scope_uid=ds.SOPInstanceUID,
            action_type=ActionType.RETAINED,
            target_type=TargetType.PIXEL_REGION,
            target_name="PixelData",
            reason_code=ReasonCode.SYSTEM_DIAGNOSTIC,
            rule_source=RuleSource.MODALITY_SAFETY_PROTOCOL
        )
```

---

### 5.3 Integration with FOI / Research / Clinical-Correction Modes

**Location:** `src/foi_engine.py`, `src/compliance_engine.py`

**FOI Legal Mode:**

```python
# In foi_engine.py → process_foi_legal()
if decision_collector:
    # Record staff redaction
    decision_collector.add(
        scope_level=ScopeLevel.INSTANCE,
        action_type=ActionType.REMOVED,
        target_name="OperatorsName",
        reason_code=ReasonCode.FOI_STAFF_REDACT,
        rule_source=RuleSource.FOI_LEGAL_PROFILE
    )
    
    # Record patient data preservation
    decision_collector.add(
        scope_level=ScopeLevel.INSTANCE,
        action_type=ActionType.RETAINED,
        target_name="PatientName",
        reason_code=ReasonCode.FOI_PRESERVE_PATIENT,
        rule_source=RuleSource.FOI_LEGAL_PROFILE
    )
    
    # Record UID preservation (chain of custody)
    decision_collector.add(
        scope_level=ScopeLevel.STUDY,
        action_type=ActionType.RETAINED,
        target_name="StudyInstanceUID",
        reason_code=ReasonCode.FOI_CHAIN_OF_CUSTODY,
        rule_source=RuleSource.FOI_LEGAL_PROFILE
    )
```

**Research De-ID Mode:**

```python
# In compliance_engine.py → _apply_us_research_safe_harbor()
for tag_name in HIPAA_SAFE_HARBOR_TAGS:
    if decision_collector:
        decision_collector.add(
            action_type=ActionType.REMOVED,
            target_name=tag_name,
            reason_code=ReasonCode.HIPAA_NAME,  # or mapped to specific HIPAA category
            rule_source=RuleSource.US_RESEARCH_PROFILE
        )
```

**Clinical Correction Mode:**

```python
# User-provided corrections are recorded as USER_CLINICAL_CORRECT
if clinical_context and clinical_context.get('patient_name'):
    if decision_collector:
        decision_collector.add(
            action_type=ActionType.REPLACED,
            target_name="PatientName",
            reason_code=ReasonCode.USER_CLINICAL_CORRECT,
            rule_source=RuleSource.USER_CLINICAL_INPUT
        )
```

---

## 6. What Is Intentionally NOT Logged

To prevent PHI leakage in audit logs, the following are **explicitly excluded**:

| Data Type | Reason for Exclusion |
|-----------|---------------------|
| **Original PHI values** | Logging "DOE^JOHN" defeats de-identification |
| **Patient names** | Direct identifier |
| **Patient IDs** | Direct identifier (original ID logged in `scrub_events` for internal audit only) |
| **Date of birth** | Direct identifier |
| **Addresses** | Direct identifier |
| **OCR-extracted text content** | May contain PHI |
| **Image pixel values** | May encode PHI |
| **Private tag values** | May contain proprietary PHI |

### What IS Logged

| Data Type | Safe to Log |
|-----------|-------------|
| **Tag names** | "PatientName" is metadata, not data |
| **Reason codes** | Enumerated, no PHI |
| **Action types** | "REMOVED" is a verb, not a value |
| **UIDs** | Only the *new* anonymized UID (or hash reference) |
| **Region coordinates** | Pixel coordinates contain no PHI |
| **Checksums** | One-way hashes, cannot recover original |
| **Timestamps** | Processing time, not clinical time |

---

## 7. PDF Report: Human-Readable Summary

The decision trace is summarized in the PDF compliance report as follows:

### 7.1 Summary Structure

```
════════════════════════════════════════════════════════════════
DECISION TRACE SUMMARY
────────────────────────────────────────────────────────────────

Processing Profile: US Research (HIPAA Safe Harbor)
Total Decisions Recorded: 47

METADATA ACTIONS:
  • 18 tags REMOVED (HIPAA Safe Harbor identifiers)
  • 3 tags REPLACED (anonymized values)
  • 4 UIDs HASHED (HMAC-SHA256 remapped)
  • 2 dates SHIFTED (deterministic offset applied)
  • 12 tags RETAINED (ML-critical parameters)

PIXEL ACTIONS:
  • 2 regions MASKED (burned-in text detected)
  • 1 region MASKED (user-selected redaction)
  • PixelData RETAINED for 0 CT/MRI instances (diagnostic preservation)

REASON CODE BREAKDOWN:
  HIPAA_18_NAME          : 3
  HIPAA_18_MRN           : 2
  HIPAA_18_DATE          : 4
  DICOM_PS315_UID_REMAP  : 4
  BURNED_IN_TEXT_DETECTED: 2
  USER_MASK_REGION       : 1
  SYSTEM_WHITELIST       : 12
  ... (full list in audit database)

COMPLIANCE ATTESTATION:
  All decisions derived from:
  ✓ Enumerated reason codes (no heuristic judgements)
  ✓ Compliance profile rules (HIPAA Safe Harbor)
  ✓ Explicit user input (1 user-selected mask)
════════════════════════════════════════════════════════════════
```

### 7.2 Implementation in `pdf_reporter.py`

```python
def generate_decision_trace_summary(decisions: List[DecisionTrace]) -> str:
    """
    Generate human-readable summary from decision trace records.
    
    Args:
        decisions: List of DecisionTrace objects for this scrub event
        
    Returns:
        Formatted multi-line string for PDF inclusion
    """
    # Count by action type
    action_counts = Counter(d.action_type for d in decisions)
    
    # Count by reason code
    reason_counts = Counter(d.reason_code for d in decisions)
    
    # Separate metadata vs pixel decisions
    metadata_decisions = [d for d in decisions if d.target_type != TargetType.PIXEL_REGION]
    pixel_decisions = [d for d in decisions if d.target_type == TargetType.PIXEL_REGION]
    
    # Generate summary text
    summary_lines = [
        f"Total Decisions Recorded: {len(decisions)}",
        "",
        "METADATA ACTIONS:",
        f"  • {action_counts.get('REMOVED', 0)} tags REMOVED",
        f"  • {action_counts.get('REPLACED', 0)} tags REPLACED",
        f"  • {action_counts.get('HASHED', 0)} UIDs HASHED",
        f"  • {action_counts.get('SHIFTED', 0)} dates SHIFTED",
        f"  • {action_counts.get('RETAINED', 0)} tags RETAINED",
        "",
        "PIXEL ACTIONS:",
        f"  • {len([d for d in pixel_decisions if d.action_type == 'MASKED'])} regions MASKED",
    ]
    
    return "\n".join(summary_lines)
```

---

## 8. Implementation Classes

### 8.1 DecisionTraceCollector (In-Memory Buffer)

```python
# src/decision_trace.py

from dataclasses import dataclass, field
from typing import List, Optional
from datetime import datetime
import hashlib

@dataclass
class DecisionRecord:
    """Single decision record (in-memory representation)."""
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
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat() + "Z")


class DecisionTraceCollector:
    """
    Collects decision records during DICOM processing.
    
    Thread-safe accumulator that buffers decisions until commit.
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
        region_h: int = None
    ) -> None:
        """
        Add a decision record to the collector.
        
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
            region_h=region_h
        )
        self._decisions.append(record)
    
    def get_decisions(self) -> List[DecisionRecord]:
        """Return a copy of all collected decisions."""
        return list(self._decisions)
    
    def lock(self) -> None:
        """Lock the collector to prevent further additions."""
        self._locked = True
    
    def count(self) -> int:
        """Return number of decisions collected."""
        return len(self._decisions)
```

### 8.2 DecisionTraceWriter (Database Commit)

```python
class DecisionTraceWriter:
    """
    Commits decision trace records to SQLite.
    
    Ensures atomicity with parent scrub_events record.
    """
    
    def __init__(self, db_path: str):
        self.db_path = db_path
        self._ensure_table()
    
    def _ensure_table(self):
        """Create decision_trace table if not exists."""
        # SQL from Section 3.1
        pass
    
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
        
        with sqlite3.connect(self.db_path) as conn:
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
```

---

## 9. Testing Strategy

### 9.1 Unit Tests (Required)

| Component | Test Coverage |
|-----------|--------------|
| `DecisionTraceCollector.add()` | All parameter combinations, locking behavior |
| `DecisionTraceCollector.lock()` | Prevents additions after lock |
| `ReasonCode` enumeration | All codes are valid strings |
| `ActionType` enumeration | All types are valid strings |
| `DecisionTraceWriter._ensure_table()` | Table creation idempotency |
| `DecisionTraceWriter.commit()` | Insert count, foreign key integrity |
| `generate_decision_trace_summary()` | Correct counts, formatting |

**Example Unit Test:**

```python
# tests/test_decision_trace_unit.py

def test_collector_add_decision():
    collector = DecisionTraceCollector()
    collector.add(
        scope_level=ScopeLevel.INSTANCE,
        scope_uid="1.2.3.4",
        action_type=ActionType.REMOVED,
        target_type=TargetType.TAG,
        target_name="PatientName",
        reason_code=ReasonCode.HIPAA_NAME,
        rule_source=RuleSource.HIPAA_SAFE_HARBOR
    )
    assert collector.count() == 1
    decisions = collector.get_decisions()
    assert decisions[0].target_name == "PatientName"

def test_collector_lock_prevents_add():
    collector = DecisionTraceCollector()
    collector.lock()
    with pytest.raises(RuntimeError):
        collector.add(
            scope_level=ScopeLevel.INSTANCE,
            action_type=ActionType.REMOVED,
            target_type=TargetType.TAG,
            target_name="Test",
            reason_code=ReasonCode.HIPAA_NAME,
            rule_source=RuleSource.HIPAA_SAFE_HARBOR
        )

def test_reason_codes_are_strings():
    for attr in dir(ReasonCode):
        if not attr.startswith('_'):
            value = getattr(ReasonCode, attr)
            assert isinstance(value, str)
            assert len(value) > 0
```

### 9.2 Integration Tests (Required)

| Scenario | Test Coverage |
|----------|--------------|
| End-to-end Research De-ID | Decisions recorded for all HIPAA tags |
| End-to-end FOI Legal | Correct preserve/redact decisions |
| Pixel masking with trace | Bounding box recorded correctly |
| PDF summary generation | Summary matches database records |
| Atomic commit failure | Collector locked even on DB failure |

### 9.3 Explicitly Excluded from Tests (with Justification)

| Component | Justification |
|-----------|--------------|
| PDF rendering internals | fpdf2 library responsibility |
| SQLite engine behavior | SQLite library responsibility |
| Checksum calculation correctness | hashlib library responsibility |
| UI integration | Integration-heavy Streamlit layer |

---

## 10. Migration Plan

### 10.1 Database Migration

```sql
-- Migration script: Add decision_trace table
-- Run once on existing databases

CREATE TABLE IF NOT EXISTS decision_trace (
    -- Schema from Section 3.1
);

-- Verify migration
SELECT name FROM sqlite_master WHERE type='table' AND name='decision_trace';
```

### 10.2 Code Migration

1. **Phase 1:** Add `decision_trace.py` with `DecisionTraceCollector`, `DecisionTraceWriter`, and enumerations
2. **Phase 2:** Add `decision_collector` optional parameter to `anonymize_metadata()`
3. **Phase 3:** Instrument `anonymize_metadata()` with decision recording
4. **Phase 4:** Instrument pixel masking with decision recording
5. **Phase 5:** Update `AtomicScrubOperation.execute_scrub()` to accept and commit collector
6. **Phase 6:** Update `pdf_reporter.py` with summary generation
7. **Phase 7:** Add unit tests

---

## 11. Limitations and Out-of-Scope

### Explicitly Out of Scope for Sprint 1

| Feature | Reason |
|---------|--------|
| Role-based access control | Future sprint |
| Decision trace dashboard/UI | Future sprint |
| Trace export to external systems | Future sprint |
| Real-time alerting | Future sprint |
| PACS routing/integration | Violates copy-out-only constraint |
| Machine learning on decision patterns | Never — no AI judgement claims |

### Known Limitations

| Limitation | Mitigation |
|------------|------------|
| SQLite single-writer lock | Acceptable for single-user workstation |
| No distributed audit storage | Copy-out-only mode, local audit sufficient |
| No external verifiability | Checksums provide integrity, not third-party attestation |

---

## 12. Approval Checklist

Before implementation, confirm:

- [ ] Schema reviewed by senior engineer
- [ ] Reason code taxonomy approved for governance use
- [ ] PHI exclusion list verified by privacy officer
- [ ] Integration points approved for all processing modes
- [ ] Testing strategy approved
- [ ] No PACS write-back introduced
- [ ] No clinical decision claims made
- [ ] All decisions explainable via rules/profiles/user input

---

**Document Status:** Ready for Senior Engineering Review  
**Next Steps:** Approval → Implementation → Unit Testing → Integration Testing → Documentation Update

---

*End of Sprint 1: Audit Decision Trace — Architecture Design*
