#!/usr/bin/env python3
"""
DICOM De-identification Script

Processes DICOM ultrasound files to replace burned-in patient information
using the ClinicalCorrector engine. Handles both single-frame and multi-frame
(video) ultrasound data.

Usage:
    python src/run_on_dicom.py --input scan.dcm --output fixed.dcm --old "SMITH" --new "JONES"
"""

import argparse
import hashlib
import sys
import uuid
from dataclasses import dataclass

import cv2
import numpy as np
import pydicom
from pydicom.uid import ExplicitVRLittleEndian, UID

from clinical_corrector import ClinicalCorrector
from compliance import enforce_dicom_compliance
from utils import apply_deterministic_sanitization, should_render_pixels, estimate_pixel_memory
from pixel_invariant import (
    PixelAction,
    decide_pixel_action,
    validate_uid_only_output,
    sha256_bytes,
)

# Evidence bundle import (Gate 2/3 Model B compliance)
try:
    from audit.evidence_bundle import EvidenceBundle, SCHEMA_VERSION
    EVIDENCE_BUNDLE_AVAILABLE = True
except ImportError:
    EVIDENCE_BUNDLE_AVAILABLE = False
    EvidenceBundle = None
    SCHEMA_VERSION = None


# Namespace UUID for deterministic UID generation (random but fixed)
DEID_NAMESPACE = uuid.UUID('a1b2c3d4-e5f6-7890-abcd-ef1234567890')


def anonymize_metadata(ds: pydicom.Dataset, new_name: str, research_context: dict = None, clinical_context: dict = None) -> None:
    """
    Anonymize DICOM metadata by removing/replacing PHI tags.
    Uses deterministic UID generation to keep batch files grouped.
    
    Args:
        ds: pydicom Dataset to modify in-place
        new_name: New patient name to apply
        research_context: Optional dict with research de-id fields:
            - study_id: Research Study ID (e.g., "LUNG_TRIAL_2025")
            - subject_id: Subject ID (e.g., "SUB_001")
            - time_point: Time Point (e.g., "BASELINE", "WEEK_4")
            - deid_date: De-identification date string
        clinical_context: Optional dict with clinical correction fields:
            - patient_name, patient_sex, patient_dob, accession_number
            - study_date, study_time, study_type, location, gestational_age
            - sonographer, referring_physician
            - reason_for_correction, correction_notes, operator_name
    """
    # UID Remapping helper - defined first for use in both paths
    def generate_new_uid(original_uid: str) -> str:
        """Generate a deterministic new UID from original using uuid5."""
        new_uuid = uuid.uuid5(DEID_NAMESPACE, original_uid)
        uid_int = int(new_uuid.hex, 16)
        new_uid = f"2.25.{uid_int}"
        return new_uid[:64]
    
    # Determine mode and prepare details for compliance module
    # Note: Accession numbers are now handled by apply_deterministic_sanitization
    if research_context:
        mode = "RESEARCH"
        new_details = {
            'patient_name': research_context.get('subject_id', 'SUB-001'),
            'patient_id': research_context.get('subject_id', 'SUB-001'),
            'institution': 'DE-IDENTIFIED RESEARCH'
        }
    elif clinical_context:
        mode = "CLINICAL"
        new_details = {
            'patient_name': clinical_context.get('patient_name', new_name),
            'patient_id': clinical_context.get('patient_name', ''),  # Use patient name as patient_id
            'patient_dob': clinical_context.get('patient_dob', ''),
            'institution': clinical_context.get('location', '')
        }
    else:
        mode = "CLINICAL"
        new_details = {
            'patient_name': new_name,
            'patient_id': '',
            'patient_dob': '',
            'institution': 'DE-IDENTIFIED'
        }
    
    # Apply compliance standards and PHI removal via the compliance module
    ds = enforce_dicom_compliance(ds, mode, new_details, 
                                operator_id="WEBAPP_USER", 
                                reason_code="CLINICAL_CORRECTION" if mode == "CLINICAL" else "RESEARCH_DEID",
                                scrub_uuid=None)
    
    # Apply unified deterministic sanitization (accession, dates, UIDs)
    # This ensures consistent treatment across ALL processing paths
    apply_deterministic_sanitization(ds)
    
    # ==============================================================================
    # FINAL LOG SYNC: FORCE READ FROM MODIFIED DATASET
    # ==============================================================================
    # The dataset has been modified by 'apply_deterministic_sanitization'.
    # We must pull the NEW values directly from the object to ensure the log is accurate.
    
    final_accession = "UNKNOWN"
    final_date = "N/A"
    
    # 1. Extract Accession Number (Safe Read)
    if "AccessionNumber" in ds:
        val = ds.AccessionNumber
        # Handle pydicom DataElement vs raw value
        final_accession = val.value if hasattr(val, 'value') else str(val)
    
    # 2. Extract Study Date (Safe Read)
    if "StudyDate" in ds:
        val = ds.StudyDate
        final_date = val.value if hasattr(val, 'value') else str(val)
    
    # 3. OVERWRITE the logging dictionary (support both naming conventions)
    # Update research_context if it exists
    if 'research_context' in locals() and research_context is not None:
        research_context['accession'] = final_accession
        research_context['accession_number'] = final_accession
        research_context['new_study_date'] = final_date
    
    # Update clinical_context if it exists
    if 'clinical_context' in locals() and clinical_context is not None:
        clinical_context['accession'] = final_accession
        clinical_context['accession_number'] = final_accession
        clinical_context['new_study_date'] = final_date
    # ==============================================================================
    
    # Continue with mode-specific metadata updates and UID remapping
    if research_context:
        # ═══════════════════════════════════════════════════════════════════
        # RESEARCH DE-ID MODE - Add Clinical Trial Tags (already handled by compliance, but add extra tags)
        # ═══════════════════════════════════════════════════════════════════
        trial_id = research_context.get('trial_id', research_context.get('study_id', 'TRIAL-001'))
        site_id = research_context.get('site_id', 'SITE-01')
        subject_id = research_context.get('subject_id', 'SUB-001')
        time_point = research_context.get('time_point', 'Baseline')
        deid_date = research_context.get('deid_date', '')
        
        # ─────────────────────────────────────────────────────────────────
        # Inject Clinical Trial Tags (Group 0012) - Standard DICOM Tags
        # ─────────────────────────────────────────────────────────────────
        from pydicom.dataelem import DataElement
        from pydicom.tag import Tag
        
        # (0012,0010) Clinical Trial Sponsor Name - LO
        ds.add_new(Tag(0x0012, 0x0010), 'LO', 'DE-IDENTIFIED RESEARCH')
        # (0012,0020) Clinical Trial Protocol ID - LO (Trial ID)
        ds.add_new(Tag(0x0012, 0x0020), 'LO', trial_id[:64])
        # (0012,0021) Clinical Trial Protocol Name - LO
        ds.add_new(Tag(0x0012, 0x0021), 'LO', trial_id[:64])
        # (0012,0030) Clinical Trial Site ID - LO (Site ID)
        ds.add_new(Tag(0x0012, 0x0030), 'LO', site_id[:64])
        # (0012,0040) Clinical Trial Subject ID - LO (Subject ID)
        ds.add_new(Tag(0x0012, 0x0040), 'LO', subject_id[:64])
        # (0012,0050) Clinical Trial Time Point ID - LO (Timepoint)
        ds.add_new(Tag(0x0012, 0x0050), 'LO', time_point[:64])
        # (0012,0051) Clinical Trial Time Point Description - ST
        ds.add_new(Tag(0x0012, 0x0051), 'ST', time_point[:1024])
        
        # Add de-identification date to ContentDate if provided
        if deid_date:
            ds.ContentDate = deid_date.replace('-', '')
        
        print(f"Research metadata applied: Trial={trial_id}, Site={site_id}, Subject={subject_id}, Timepoint={time_point}")
    elif clinical_context:
        # ═══════════════════════════════════════════════════════════════════
        # CLINICAL CORRECTION MODE - Update with provided clinical data
        # ═══════════════════════════════════════════════════════════════════
        
        # ─────────────────────────────────────────────────────────────────
        # Patient Demographics (already handled by compliance module)
        # ─────────────────────────────────────────────────────────────────
        
        # ─────────────────────────────────────────────────────────────────
        # Study Information
        # ─────────────────────────────────────────────────────────────────
        if clinical_context.get('study_date'):
            # Convert YYYY-MM-DD to YYYYMMDD
            study_date = clinical_context['study_date'].replace('-', '')
            ds.StudyDate = study_date
        
        if clinical_context.get('study_time'):
            # Convert HH:MM:SS to HHMMSS
            study_time = clinical_context['study_time'].replace(':', '')
            ds.StudyTime = study_time
        
        if clinical_context.get('study_type'):
            ds.StudyDescription = clinical_context['study_type']
        
        # ─────────────────────────────────────────────────────────────────
        # Personnel
        # ─────────────────────────────────────────────────────────────────
        if clinical_context.get('sonographer'):
            ds.OperatorsName = clinical_context['sonographer']
        
        if clinical_context.get('referring_physician'):
            ds.ReferringPhysicianName = clinical_context['referring_physician']
        
        # ─────────────────────────────────────────────────────────────────
        # Audit Trail - Image Comments (0020,4000)
        # ─────────────────────────────────────────────────────────────────
        audit_parts = []
        
        if clinical_context.get('reason_for_correction'):
            audit_parts.append(f"Reason: {clinical_context['reason_for_correction']}")
        
        if clinical_context.get('correction_notes'):
            audit_parts.append(f"Notes: {clinical_context['correction_notes']}")
        
        if clinical_context.get('operator_name'):
            audit_parts.append(f"Corrected by: {clinical_context['operator_name']}")
        
        if clinical_context.get('auto_timestamp', False):
            from datetime import datetime
            audit_parts.append(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        # Record original patient name for audit
        original_name = getattr(ds, 'PatientName', 'UNKNOWN')
        if str(original_name) != clinical_context.get('patient_name', ''):
            audit_parts.insert(0, f"Original: {original_name}")
        
        if audit_parts:
            audit_text = " | ".join(audit_parts)
            # Add to Image Comments tag (0020,4000)
            ds.ImageComments = f"[CORRECTED] {audit_text}"
        
        print(f"Clinical correction applied: {clinical_context.get('patient_name', new_name)}")
        print(f"Audit trail: {audit_parts}")
    else:
        # Fallback - basic correction without clinical context (already handled by compliance module)
        print(f"Metadata anonymized (basic): PatientID={ds.PatientID}")
    
    # ─────────────────────────────────────────────────────────────────────
    # UID Remapping (applies to both modes)
    # ─────────────────────────────────────────────────────────────────────
    if hasattr(ds, 'StudyInstanceUID') and ds.StudyInstanceUID:
        ds.StudyInstanceUID = generate_new_uid(str(ds.StudyInstanceUID))
    
    if hasattr(ds, 'SeriesInstanceUID') and ds.SeriesInstanceUID:
        ds.SeriesInstanceUID = generate_new_uid(str(ds.SeriesInstanceUID))
    
    if hasattr(ds, 'SOPInstanceUID') and ds.SOPInstanceUID:
        new_sop_uid = generate_new_uid(str(ds.SOPInstanceUID))
        ds.SOPInstanceUID = new_sop_uid
        if hasattr(ds, 'file_meta') and hasattr(ds.file_meta, 'MediaStorageSOPInstanceUID'):
            ds.file_meta.MediaStorageSOPInstanceUID = new_sop_uid

    # --- CRITICAL FIX: SYNC LOG WITH FINAL DATASET ---
    # The dataset has been modified. We MUST update the logging dictionaries to match the output file.
    # ═══════════════════════════════════════════════════════════════════════════
    # SAFE DEFAULT INITIALIZATION (Fixes UnboundLocalError)
    # ═══════════════════════════════════════════════════════════════════════════
    final_acc = "UNKNOWN_ACC"  # Safe default
    final_date = "UNKNOWN_DATE"  # Safe default
    
    # Override with actual values if present
    if "AccessionNumber" in ds:
        final_acc = str(ds.AccessionNumber)
    
    # Update contexts with the final accession value
    if 'research_context' in locals() and research_context is not None:
        research_context['accession'] = final_acc
        research_context['accession_number'] = final_acc
    
    if 'clinical_context' in locals() and clinical_context is not None:
        clinical_context['accession'] = final_acc
        clinical_context['accession_number'] = final_acc
    
    # Override date with actual value if present
    if "StudyDate" in ds:
        final_date = str(ds.StudyDate)
    
    # Update contexts with the final date value    
    if 'research_context' in locals() and research_context is not None:
        research_context['new_study_date'] = final_date
    if 'clinical_context' in locals() and clinical_context is not None:
        clinical_context['new_study_date'] = final_date

    # NOW call the logger with the updated dictionary
    # generate_audit_log(activity_id, log_details, dataset=ds)


def process_dataset(
    ds: pydicom.Dataset,
    *,
    old_name_text: str,
    new_name_text: str,
    manual_box: tuple = None,
    research_context: dict = None,
    mask_list: list = None,
    clinical_context: dict = None,
    audit_dict: dict = None,
) -> pydicom.Dataset:
    """
    Pure in-memory processing: anonymize metadata and (optionally) apply pixel masking.
    
    This is the test-friendly core function that operates on an in-memory Dataset
    without filesystem I/O. The process_dicom() function is a thin wrapper that
    handles file reading/writing.
    
    PHASE 3 ENHANCEMENT: Enforces pixel invariant in UID-only mode.
    When pixel_action == NOT_APPLIED, PixelData bytes are preserved exactly.
    
    Args:
        ds: pydicom Dataset to process (modified in-place and returned)
        old_name_text: Original patient name for audit trail
        new_name_text: New patient name to apply
        manual_box: Optional tuple (x, y, w, h) for manual mask override
        research_context: Optional dict with research de-id fields
        mask_list: Optional list of (x, y, w, h) tuples for multiple mask regions
        clinical_context: Optional dict with clinical correction fields
        audit_dict: Optional dict to populate with audit fields (pixel_action, pixel_invariant, etc.)
        
    Returns:
        The processed Dataset (same object, modified in-place)
    """
    # ═══════════════════════════════════════════════════════════════════════════
    # PHASE 3: PIXEL ACTION DECISION (Single Source of Truth)
    # ═══════════════════════════════════════════════════════════════════════════
    pixel_action = decide_pixel_action(
        clinical_context=clinical_context,
        apply_mask=(manual_box is not None or (mask_list is not None and len(mask_list) > 0)),
        mask_list=mask_list,
        manual_box=manual_box
    )
    
    # Store baseline hash for UID-only mode invariant check
    baseline_hash = None
    if pixel_action == PixelAction.NOT_APPLIED and hasattr(ds, 'PixelData') and ds.PixelData:
        baseline_hash = sha256_bytes(ds.PixelData)
    
    # Always anonymize metadata first
    anonymize_metadata(ds, new_name_text, research_context, clinical_context)
    
    # If no pixel data, we are done (metadata-only DICOM)
    if not hasattr(ds, "PixelData") or ds.PixelData is None:
        # Update audit dict
        if audit_dict is not None:
            audit_dict['pixel_action'] = pixel_action.value
            audit_dict['pixel_invariant'] = 'N/A'
        return ds
    
    # ═══════════════════════════════════════════════════════════════════════════
    # PHASE 3: PIXEL INVARIANT ENFORCEMENT (UID-only mode)
    # ═══════════════════════════════════════════════════════════════════════════
    if pixel_action == PixelAction.NOT_APPLIED:
        # Verify pixel data was not mutated by metadata anonymization
        if baseline_hash is not None:
            current_hash = sha256_bytes(ds.PixelData)
            if current_hash != baseline_hash:
                raise RuntimeError(
                    f"Pixel invariant violated during metadata anonymization: "
                    f"PixelData hash changed from {baseline_hash[:16]}... to {current_hash[:16]}... "
                    f"This is forbidden in UID-only mode."
                )
        
        # Update audit dict
        if audit_dict is not None:
            audit_dict['pixel_action'] = pixel_action.value
            audit_dict['pixel_invariant'] = 'PASS'
            if baseline_hash:
                audit_dict['pixel_sha'] = baseline_hash
        
        return ds
    
    # MASK_APPLIED path - pixel processing handled by process_dicom()
    if audit_dict is not None:
        audit_dict['pixel_action'] = pixel_action.value
        audit_dict['pixel_invariant'] = 'N/A'
    
    # Pixel processing will be handled by the full process_dicom() for now
    # Future: migrate pixel pipeline here for better testability
    return ds


@dataclass
class DetectionResult:
    """
    Result of OCR text detection on an image array.
    
    Phase 4: Surfaces OCR confidence and failure states explicitly.
    Detection-only — no masking or pixel behavior changes.
    
    Phase 4 Option B: Includes zone classification for each detected box.
    Zones are determined by vertical position (header/footer/body bands).
    
    Attributes:
        static_box: Bounding box (x, y, w, h) of consistent text region, or None
        all_detected_boxes: List of all detected boxes across sampled frames
        detection_strength: LOW/MEDIUM/HIGH based on OCR confidence, or None if OCR failed
        ocr_failure: True if OCR engine threw an exception
        confidence_scores: Raw confidence scores for audit (may be empty)
        region_zones: Zone classification for each box ("HEADER", "FOOTER", "BODY")
        image_height: Image height used for zone calculation
    """
    static_box: tuple  # (x, y, w, h) or None
    all_detected_boxes: list  # List of (x, y, w, h)
    detection_strength: str  # "LOW", "MEDIUM", "HIGH", or None
    ocr_failure: bool  # True if OCR engine failed
    confidence_scores: list  # Raw scores for audit trail
    # Phase 4 Option B: Zone classification
    region_zones: list = None  # List of zone strings for each box
    image_height: int = None  # Image height for zone calculations


# ═══════════════════════════════════════════════════════════════════════════════
# PHASE 4 OPTION B: STATIC HEADER/FOOTER BANDING
# ═══════════════════════════════════════════════════════════════════════════════

# Default zone thresholds (percentage of image height)
# Conservative: biases toward "risky" zones (header/footer)
ZONE_HEADER_THRESHOLD = 0.15  # Top 15% = header
ZONE_FOOTER_THRESHOLD = 0.85  # Bottom 15% = footer (y > 85% of height)

# Modality-specific overrides (US/SC have tighter header zones)
MODALITY_ZONE_THRESHOLDS = {
    "US": {"header": 0.12, "footer": 0.88},  # Ultrasound: top 12%, bottom 12%
    "SC": {"header": 0.15, "footer": 0.85},  # Secondary Capture: standard
    "OT": {"header": 0.15, "footer": 0.85},  # Other: standard
}


def _classify_zone(y: int, h: int, image_height: int, modality: str = None) -> str:
    """
    Classify a detected region's zone based on vertical position.
    
    Phase 4 Option B: Static percentage banding.
    
    Uses center-of-box y coordinate for classification:
    - HEADER: box center in top threshold% of image
    - FOOTER: box center in bottom (1-threshold)% of image  
    - BODY: everything else
    
    Args:
        y: Top y coordinate of box
        h: Height of box
        image_height: Total image height in pixels
        modality: Optional modality for modality-aware thresholds
        
    Returns:
        Zone string: "HEADER", "FOOTER", or "BODY"
    """
    if image_height <= 0:
        return "BODY"  # Defensive
    
    # Get thresholds (modality-specific or default)
    if modality and modality.upper() in MODALITY_ZONE_THRESHOLDS:
        thresholds = MODALITY_ZONE_THRESHOLDS[modality.upper()]
        header_threshold = thresholds["header"]
        footer_threshold = thresholds["footer"]
    else:
        header_threshold = ZONE_HEADER_THRESHOLD
        footer_threshold = ZONE_FOOTER_THRESHOLD
    
    # Use center of box for classification
    box_center_y = y + (h / 2)
    relative_position = box_center_y / image_height
    
    if relative_position <= header_threshold:
        return "HEADER"
    elif relative_position >= footer_threshold:
        return "FOOTER"
    else:
        return "BODY"


def _classify_all_zones(boxes: list, image_height: int, modality: str = None) -> list:
    """
    Classify zones for all detected boxes.
    
    Args:
        boxes: List of (x, y, w, h) tuples
        image_height: Image height in pixels
        modality: Optional modality for thresholds
        
    Returns:
        List of zone strings, same length as boxes
    """
    zones = []
    for box in boxes:
        if len(box) == 4:
            x, y, w, h = box
            zones.append(_classify_zone(y, h, image_height, modality))
        else:
            zones.append("BODY")  # Defensive
    return zones




def _map_confidence_to_strength(confidence: float) -> str:
    """
    Map OCR confidence score (0.0-1.0) to detection strength.
    
    Uses conservative thresholds — intentionally pessimistic.
    
    Thresholds:
        >= 0.80 → HIGH
        0.50-0.79 → MEDIUM  
        < 0.50 → LOW
    
    These thresholds are documented and tunable in future versions.
    
    Args:
        confidence: OCR confidence score (0.0-1.0)
        
    Returns:
        DetectionStrength value (LOW, MEDIUM, HIGH)
    """
    if confidence >= 0.80:
        return "HIGH"
    elif confidence >= 0.50:
        return "MEDIUM"
    else:
        return "LOW"


def _aggregate_confidence(scores: list) -> float:
    """
    Aggregate multiple confidence scores into a single value.
    
    Uses minimum (most conservative) to avoid false reassurance.
    
    Args:
        scores: List of confidence scores (0.0-1.0)
        
    Returns:
        Aggregated confidence score, or 0.0 if empty
    """
    if not scores:
        return 0.0
    return min(scores)


def detect_text_box_from_array(
    corrector: ClinicalCorrector,
    arr: np.ndarray,
    debug_frame: np.ndarray = None
) -> DetectionResult:
    """
    Detect static text region from a numpy array (first frame).
    
    Phase 4 Enhancement: Returns DetectionResult with explicit confidence
    and failure state. Detection-only — no masking behavior changes.

    Args:
        corrector: ClinicalCorrector instance
        arr: 4D numpy array (Frames, H, W, C)
        debug_frame: If provided, will be modified with red detection boxes

    Returns:
        DetectionResult containing:
        - static_box: (x, y, w, h) or None
        - all_detected_boxes: list of all detected boxes
        - detection_strength: LOW/MEDIUM/HIGH or None if OCR failed
        - ocr_failure: True if OCR engine threw exception
        - confidence_scores: raw scores for audit
    """
    # Sample first and last frames for detection
    num_frames = arr.shape[0]
    if num_frames < 2:
        sample_indices = [0]
    elif num_frames < 10:
        sample_indices = list(range(num_frames))
    else:
        sample_indices = list(range(5)) + list(range(num_frames - 5, num_frames))

    all_boxes = []
    all_detected_boxes = []  # For debug output
    all_confidence_scores = []  # Phase 4: collect confidence
    ocr_failure_occurred = False  # Phase 4: track failures
    
    # Phase 4 Option B: Get image dimensions for zone classification
    image_height = arr.shape[1] if len(arr.shape) >= 2 else 0

    for idx in sample_indices:
        frame = arr[idx]
        # Ensure frame is BGR for OCR (convert if grayscale)
        if frame.ndim == 2:
            frame = cv2.cvtColor(frame, cv2.COLOR_GRAY2BGR)
        elif frame.shape[2] == 4:
            frame = cv2.cvtColor(frame, cv2.COLOR_RGBA2BGR)

        # Pre-process frame for better OCR detection ("The Glasses")
        frame_processed = corrector._preprocess_for_ocr(frame)

        # Scale factor for converting back from upscaled coordinates
        scale_factor = 2

        try:
            result = corrector.ocr.predict(frame_processed)
            frame_boxes = []

            if result and isinstance(result, list) and len(result) > 0:
                res = result[0]
                if isinstance(res, dict) and 'det_boxes' in res:
                    # Dict format: {'det_boxes': [...], 'det_scores': [...]}
                    det_scores = res.get('det_scores', [])
                    for i, box_points in enumerate(res['det_boxes']):
                        x_coords = [p[0] for p in box_points]
                        y_coords = [p[1] for p in box_points]
                        # Scale back to original size
                        x = int(min(x_coords) / scale_factor)
                        y = int(min(y_coords) / scale_factor)
                        w = int((max(x_coords) - min(x_coords)) / scale_factor)
                        h = int((max(y_coords) - min(y_coords)) / scale_factor)
                        frame_boxes.append((x, y, w, h))
                        all_detected_boxes.append((x, y, w, h))
                        # Extract confidence if available
                        if i < len(det_scores):
                            all_confidence_scores.append(float(det_scores[i]))
                elif isinstance(res, list):
                    # List format: [[[box_points], (text, confidence)], ...]
                    for line in res:
                        box_points = line[0]
                        x_coords = [p[0] for p in box_points]
                        y_coords = [p[1] for p in box_points]
                        # Scale back to original size
                        x = int(min(x_coords) / scale_factor)
                        y = int(min(y_coords) / scale_factor)
                        w = int((max(x_coords) - min(x_coords)) / scale_factor)
                        h = int((max(y_coords) - min(y_coords)) / scale_factor)
                        frame_boxes.append((x, y, w, h))
                        all_detected_boxes.append((x, y, w, h))
                        # Extract confidence from (text, confidence) tuple
                        if len(line) > 1 and isinstance(line[1], (tuple, list)) and len(line[1]) > 1:
                            all_confidence_scores.append(float(line[1][1]))

            all_boxes.append(frame_boxes)
        except Exception as e:
            print(f"OCR error on frame {idx}: {e}")
            all_boxes.append([])
            ocr_failure_occurred = True  # Phase 4: explicit failure tracking

    print(f"Total boxes detected across all frames: {len(all_detected_boxes)}")

    # Phase 4: Compute detection strength from confidence
    if ocr_failure_occurred:
        # OCR engine failed — explicit uncertainty
        detection_strength = None
        print("[Phase4] OCR failure detected — detection_strength=None (explicit uncertainty)")
    elif not all_detected_boxes:
        # No detections, but OCR didn't fail — LOW confidence
        detection_strength = "LOW"
        print("[Phase4] No text detected — detection_strength=LOW")
    elif all_confidence_scores:
        # Have confidence scores — compute strength from minimum (conservative)
        aggregated = _aggregate_confidence(all_confidence_scores)
        detection_strength = _map_confidence_to_strength(aggregated)
        print(f"[Phase4] Confidence scores: min={aggregated:.3f} → detection_strength={detection_strength}")
    else:
        # OCR succeeded but no confidence scores available (legacy format)
        # Default to MEDIUM — not confident enough for HIGH, not failing
        detection_strength = "MEDIUM"
        print("[Phase4] OCR succeeded but no confidence scores — detection_strength=MEDIUM (conservative default)")

    # Find consistent (static) boxes
    if not all_boxes or not all_boxes[0]:
        # Phase 4 Option B: Classify zones even when no static box found
        region_zones = _classify_all_zones(all_detected_boxes, image_height)
        return DetectionResult(
            static_box=None,
            all_detected_boxes=all_detected_boxes,
            detection_strength=detection_strength,
            ocr_failure=ocr_failure_occurred,
            confidence_scores=all_confidence_scores,
            region_zones=region_zones,
            image_height=image_height,
        )

    reference_boxes = all_boxes[0]
    static_box = None
    max_consistency = 0

    for ref_box in reference_boxes:
        consistency = 0
        for frame_boxes in all_boxes[1:]:
            for box in frame_boxes:
                if corrector._boxes_overlap(ref_box, box, tolerance=20):
                    consistency += 1
                    break

        if consistency > max_consistency:
            max_consistency = consistency
            static_box = ref_box

    if max_consistency >= len(all_boxes) // 2:
        # Phase 4 Option B: Classify zones for all detected boxes
        region_zones = _classify_all_zones(all_detected_boxes, image_height)
        return DetectionResult(
            static_box=static_box,
            all_detected_boxes=all_detected_boxes,
            detection_strength=detection_strength,
            ocr_failure=ocr_failure_occurred,
            confidence_scores=all_confidence_scores,
            region_zones=region_zones,
            image_height=image_height,
        )

    # Phase 4 Option B: Classify zones for fallback path
    region_zones = _classify_all_zones(all_detected_boxes, image_height)
    return DetectionResult(
        static_box=None,
        all_detected_boxes=all_detected_boxes,
        detection_strength=detection_strength,
        ocr_failure=ocr_failure_occurred,
        confidence_scores=all_confidence_scores,
        region_zones=region_zones,
        image_height=image_height,
    )


# NOTE: process_dicom is integration-heavy (I/O + pixel pipeline)
# and is intentionally excluded from unit-level coverage.
def process_dicom(  # pragma: no cover
    input_path: str,
    output_path: str,
    old_name_text: str,
    new_name_text: str,
    manual_box: tuple = None,
    research_context: dict = None,
    mask_list: list = None,
    clinical_context: dict = None,
    evidence_bundle: 'EvidenceBundle' = None,
) -> bool:
    """
    Process a DICOM file to de-identify patient information.

    Args:
        input_path: Path to input DICOM file
        output_path: Path for output DICOM file
        old_name_text: Original patient name to record in audit
        new_name_text: New patient name to apply
        manual_box: Optional tuple (x, y, w, h) for manual mask override.
                    If provided, skips AI detection and uses these coordinates.
        research_context: Optional dict with research de-id fields for clinical trial mode
        mask_list: Optional list of (x, y, w, h) tuples for multiple mask regions.
                   Used for interactive redaction mode. Takes precedence over manual_box.
        clinical_context: Optional dict with clinical correction fields (patient demographics,
                         study info, personnel, audit trail)

    Returns:
        True if processing succeeded, False otherwise
    """
    print(f"Loading DICOM file: {input_path}")
    
    # ═══════════════════════════════════════════════════════════════════════════
    # EVIDENCE BUNDLE: Early exception handler wrapper
    # ═══════════════════════════════════════════════════════════════════════════
    source_sop_uid = None
    source_pixel_hash = None

    # Load the DICOM file (force=True handles files without standard header)
    try:
        ds = pydicom.dcmread(input_path, force=True)
        # EVIDENCE: Extract source UIDs immediately
        source_sop_uid = str(getattr(ds, 'SOPInstanceUID', 'UNKNOWN'))
        source_series_uid = str(getattr(ds, 'SeriesInstanceUID', 'UNKNOWN'))
        source_study_uid = str(getattr(ds, 'StudyInstanceUID', 'UNKNOWN'))
    except Exception as e:
        if evidence_bundle:
            try:
                evidence_bundle.add_exception(
                    exception_type="SOURCE_READ_FAILURE",
                    message=str(e),
                    severity="ERROR",
                    source_sop_uid=None
                )
            except:
                pass
        raise RuntimeError(f"Failed to read DICOM file: {e}")

    # ═══════════════════════════════════════════════════════════════════════════
    # Extract original scan date/time for research label
    # ═══════════════════════════════════════════════════════════════════════════
    study_date_raw = ds.get("StudyDate", "")
    study_time_raw = ds.get("StudyTime", "")
    
    # Format date: YYYYMMDD -> YYYY-MM-DD
    if study_date_raw and len(study_date_raw) >= 8:
        formatted_date = f"{study_date_raw[:4]}-{study_date_raw[4:6]}-{study_date_raw[6:8]}"
    else:
        formatted_date = "Unknown"
    
    # Format time: HHMMSS.ffffff -> HH:MM
    if study_time_raw and len(study_time_raw) >= 4:
        formatted_time = f"{study_time_raw[:2]}:{study_time_raw[2:4]}"
    else:
        formatted_time = ""
    
    scan_datetime = f"{formatted_date} {formatted_time}".strip()
    print(f"Original scan datetime: {scan_datetime}")

    # Log original photometric interpretation for debugging
    original_photometric = getattr(ds, 'PhotometricInterpretation', 'UNKNOWN')
    print(f"Input format: {original_photometric}")

    # ═══════════════════════════════════════════════════════════════════════════
    # MEMORY GUARD: SKIP PIXELS IF TOO LARGE
    # ═══════════════════════════════════════════════════════════════════════════
    if not should_render_pixels(ds):
        est_bytes = estimate_pixel_memory(ds)
        print(f"⚠️ [MEMORY GUARD] Skipping pixel processing. Estimate: {est_bytes / (1024*1024):.1f} MB (Uncompressed)")
        
        # Log to evidence bundle
        if evidence_bundle:
            try:
                evidence_bundle.add_exception(
                    exception_type="PIXEL_PROCESSING_SKIPPED",
                    message=f"Dataset too large for pixel processing (Estimate: {est_bytes} bytes). Metadata anonymization only.",
                    severity="WARNING",
                    source_sop_uid=source_sop_uid
                )
            except:
                pass
        
        # Skip pixel processing blocks, jump to metadata
        # We need to set arr_out to None or similar to signal "no new pixels"
        # But wait, the code below expects arr_out.
        # We should probably restructure the flow or wrap the HUGE block in "if render_pixels:"
        
        # Better strategy: Wrap the entire pixel pipeline in an else block or return early if I can refactor.
        # Given the linear structure, let's use a flag.
        pixel_processing_enabled = False
    else:
        pixel_processing_enabled = True

    # Decompress pixels (required for OpenCV editing)
    # Note: pydicom usually converts YBR* to RGB automatically on decompress
    if pixel_processing_enabled:
        print("Decompressing pixel data...")
        try:
            ds.decompress()
        except Exception as e:
            print(f"Warning: Decompression failed or not needed: {e}")


    # Get pixel array
    if pixel_processing_enabled:
        try:
            arr = ds.pixel_array.copy()  # Copy to ensure writability
            # EVIDENCE: Compute source pixel hash BEFORE any modification (Model B backbone)
            if evidence_bundle:
                try:
                    source_pixel_hash = sha256_bytes(ds.PixelData)
                    evidence_bundle.add_source_hash(
                        sop_instance_uid=source_sop_uid,
                        pixel_hash=f"sha256:{source_pixel_hash}",
                        series_uid=source_series_uid,
                        instance_number=getattr(ds, 'InstanceNumber', None)
                    )
                except Exception as he:
                    print(f"[EVIDENCE] Warning: Could not compute source hash: {he}")
        except Exception as e:
            if evidence_bundle:
                try:
                    evidence_bundle.add_exception(
                        exception_type="PIXEL_ARRAY_FAILURE",
                        message=str(e),
                        severity="ERROR",
                        source_sop_uid=source_sop_uid
                    )
                except:
                    pass
            raise RuntimeError(f"Failed to extract pixel array: {e}")
    
        print(f"Original array shape: {arr.shape}, dtype: {arr.dtype}")
    
        # Handle dimensions: ensure 4D (Frames, H, W, C)
        original_ndim = arr.ndim
        if arr.ndim == 2:
            # Grayscale single frame: (H, W) -> (1, H, W, 1)
            arr = arr[np.newaxis, :, :, np.newaxis]
            arr = np.repeat(arr, 3, axis=3)  # Convert to RGB
        elif arr.ndim == 3:
            # Could be (H, W, C) single frame or (Frames, H, W) grayscale video
            if arr.shape[2] in (3, 4):
                # Single frame with channels: (H, W, C) -> (1, H, W, C)
                arr = arr[np.newaxis, :, :, :]
            else:
                # Grayscale video: (Frames, H, W) -> (Frames, H, W, 3)
                arr = arr[:, :, :, np.newaxis]
                arr = np.repeat(arr, 3, axis=3)
        elif arr.ndim == 4:
            # Already 4D: (Frames, H, W, C)
            if arr.shape[3] == 1:
                # Grayscale video with channel dim
                arr = np.repeat(arr, 3, axis=3)
    
        print(f"Normalized array shape: {arr.shape}")
    
        # ═══════════════════════════════════════════════════════════════════════════
        # ZERO-LOSS BIT-DEPTH HANDLING
        # ═══════════════════════════════════════════════════════════════════════════
        # Store original dtype for later restoration (e.g., uint16 for X-Ray)
        original_dtype = arr.dtype
        original_max_value = arr.max()
        
        # For display/OpenCV processing, we may need uint8, but we'll restore later
        # Key insight: Mask application uses simple = 0, which works at any bit depth
        if arr.dtype != np.uint8:
            # Scale to uint8 ONLY for display purposes (OCR detection)
            # Keep original array separate for final save
            arr_original_depth = arr.copy()  # Preserve original bit-depth data
            
            if original_max_value > 255:
                # Scale to 8-bit for processing
                arr = ((arr.astype(np.float32) / original_max_value) * 255).astype(np.uint8)
                print(f"[BIT-DEPTH] Scaled from {original_dtype} (max={original_max_value}) to uint8 for processing")
            else:
                arr = arr.astype(np.uint8)
        else:
            arr_original_depth = None  # Already uint8, no need for separate array
    
        # Initialize corrector
        print("Initializing ClinicalCorrector...")
        corrector = ClinicalCorrector()
    
        frame_h, frame_w = arr.shape[1:3]
    
        # ═══════════════════════════════════════════════════════════════════════════
        # STEP 1: DETERMINE MASK COORDINATES (mask_list > manual_box > AI Detection)
        # ═══════════════════════════════════════════════════════════════════════════
        all_masks = []  # List of (x, y, w, h) tuples
        
        if mask_list is not None and len(mask_list) > 0:
            # Interactive redaction mode - multiple masks provided
            print(f"[MASK] Using INTERACTIVE mask list: {len(mask_list)} region(s)")
            all_masks = list(mask_list)
        elif manual_box is not None:
            # Single manual mask provided - convert to list
            print(f"[MASK] Using MANUAL mask override: {manual_box}")
            all_masks = [manual_box]
        else:
            # AI Detection fallback
            print("[MASK] No manual mask - running AI detection...")
            detection_result = detect_text_box_from_array(corrector, arr)
    
            # Save debug image with RED rectangles around all detections
            debug_frame = arr[0].copy()
            for box in detection_result.all_detected_boxes:
                bx, by, bw, bh = box
                cv2.rectangle(debug_frame, (bx, by), (bx + bw, by + bh), (0, 0, 255), 2)  # RED
            debug_path = "studies/debug_detection.png"
            cv2.imwrite(debug_path, cv2.cvtColor(debug_frame, cv2.COLOR_RGB2BGR))
            print(f"[MASK] Debug image saved to: {debug_path} (showing {len(detection_result.all_detected_boxes)} detections)")
            
            # Phase 4: Log detection strength
            print(f"[Phase4] Detection strength: {detection_result.detection_strength}, OCR failure: {detection_result.ocr_failure}")
            
            # EVIDENCE: Log detection results (NO PHI text stored - only locations/confidence)
            if evidence_bundle and detection_result.all_detected_boxes:
                try:
                    modality = str(getattr(ds, 'Modality', 'UNKNOWN'))
                    for i, box in enumerate(detection_result.all_detected_boxes):
                        confidence = detection_result.confidence_scores[i] if i < len(detection_result.confidence_scores) else 0.0
                        zone = detection_result.region_zones[i] if detection_result.region_zones and i < len(detection_result.region_zones) else "BODY"
                        evidence_bundle.add_detection(
                            source_sop_uid=source_sop_uid,
                            bbox=list(box),
                            confidence=confidence,
                            region=zone,
                            engine="PaddleOCR",
                            engine_version="2.7.0",
                            ruleset_id=f"{modality}_ZONE",
                            config_hash="sha256:runtime",
                            frame_index=None
                        )
                except Exception as de:
                    print(f"[EVIDENCE] Warning: Could not log detection: {de}")
    
            # Use default region if detection fails
            text_box = detection_result.static_box
            if text_box is None:
                print("[MASK] No text detected, using default top-left region")
                text_box = (10, 10, 200, 30)
            else:
                print(f"[MASK] Detected text box: {text_box}")
    
            x, y, w, h = text_box
    
            # Add padding
            padding = 5
            x = max(0, x - padding)
            y = max(0, y - padding)
            w = min(frame_w - x, w + 2 * padding)
            h = min(frame_h - y, h + 2 * padding)
    
            all_masks = [(x, y, w, h)]
        
        # ═══════════════════════════════════════════════════════════════════════════
        # STEP 2: THE UNIVERSAL ERASER - Draw black boxes for ALL masks
        # Apply to BOTH 8-bit display array AND original bit-depth array (zero-loss)
        # ═══════════════════════════════════════════════════════════════════════════
        num_frames = arr.shape[0]
        print(f"[PIXEL SCRUB] Drawing {len(all_masks)} BLACK BOX(es) on {num_frames} frame(s)...")
        
        for i in range(num_frames):
            frame = arr[i]
            # Also get original depth frame if available
            frame_orig = arr_original_depth[i] if arr_original_depth is not None else None
            
            for mask_idx, (x, y, w, h) in enumerate(all_masks):
                # Clamp coordinates to frame boundaries
                x_end = min(x + w, frame_w)
                y_end = min(y + h, frame_h)
                x_start = max(0, x)
                y_start = max(0, y)
                
                # DRAW THE BLACK BOX - This is the universal eraser
                # Apply to 8-bit display array
                frame[y_start:y_end, x_start:x_end] = 0
                
                # ZERO-LOSS: Also apply to original bit-depth array
                if frame_orig is not None:
                    frame_orig[y_start:y_end, x_start:x_end] = 0
            
            if (i + 1) % 10 == 0 or i == num_frames - 1:
                print(f"  [PIXEL SCRUB] Erased frame {i + 1}/{num_frames}")
        
        print(f"[PIXEL SCRUB] {len(all_masks)} BLACK BOX(es) applied to all frames")
        if arr_original_depth is not None:
            print(f"[ZERO-LOSS] Masks also applied to original {original_dtype} data")
        
        # EVIDENCE: Log masking actions (what was done, not what was found)
        if evidence_bundle and all_masks:
            try:
                for mask_idx, (mx, my, mw, mh) in enumerate(all_masks):
                    evidence_bundle.add_masking_action(
                        masked_sop_uid="PENDING",  # Will be updated after UID generation
                        action_type="black_box",
                        bbox_applied=[mx, my, mw, mh],
                        parameters={"color": [0, 0, 0], "padding": 5},
                        result="success",
                        reason=None,
                        frame_index=None
                    )
            except Exception as me:
                print(f"[EVIDENCE] Warning: Could not log masking action: {me}")
        
        # Use first mask for text overlay positioning (if any masks exist)
        if all_masks:
            x, y, w, h = all_masks[0]
        else:
            x, y, w, h = 10, 10, 200, 30  # Default fallback
        
        # ═══════════════════════════════════════════════════════════════════════════
        # STEP 3: THE CONDITIONAL PEN - Write text overlay for BOTH modes
        # ═══════════════════════════════════════════════════════════════════════════
        if research_context:
            # Research mode - construct comprehensive research label (Clinical Trial format)
            trial_id = research_context.get('trial_id', research_context.get('study_id', 'TRIAL'))
            site_id = research_context.get('site_id', 'SITE-01')
            subject_id = research_context.get('subject_id', 'SUB-001')
            time_point = research_context.get('time_point', 'Baseline')
            
            # Build standard Clinical Trial header: "{TrialID} | Site: {SiteID} | Sub: {SubjectID} | {Timepoint} | {ScanDate}"
            overlay_text = f"{trial_id} | Site: {site_id} | Sub: {subject_id} | {time_point} | {scan_datetime}"
            print(f"[MODE] Research De-ID: Overlaying '{overlay_text}'")
        elif clinical_context and clinical_context.get('patient_name'):
            # Clinical mode with full context - build Toshiba/Aplio style header
            # Line 1: [Accession]:PATIENT NAME | [Sex] [Age] | [Date]
            # Line 2: [Location] | [Study Type] | [GA] | [Sonographer] | [Time]
            
            patient_name = clinical_context.get('patient_name', new_name_text)
            accession = clinical_context.get('accession_number', '')
            patient_sex = clinical_context.get('patient_sex', '')
            patient_dob = clinical_context.get('patient_dob', '')
            study_date_str = clinical_context.get('study_date', '')
            study_time_str = clinical_context.get('study_time', '')
            location = clinical_context.get('location', '')
            study_type = clinical_context.get('study_type', '')
            gestational_age = clinical_context.get('gestational_age', '')
            sonographer = clinical_context.get('sonographer', '')
            
            # Calculate age if DOB provided
            age_str = ''
            if patient_dob:
                try:
                    from datetime import datetime, date
                    dob = datetime.strptime(patient_dob, '%Y-%m-%d').date()
                    today = date.today()
                    age = today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))
                    age_str = str(age)
                except:
                    pass
            
            # Format date for display (YYYY-MM-DD -> DD/MM/YYYY)
            display_date = ''
            if study_date_str:
                try:
                    parts = study_date_str.split('-')
                    if len(parts) == 3:
                        display_date = f"{parts[2]}/{parts[1]}/{parts[0]}"
                except:
                    display_date = study_date_str
            
            # Format time for display (HH:MM:SS -> H:MM:SS PM)
            display_time = ''
            if study_time_str:
                try:
                    from datetime import datetime
                    t = datetime.strptime(study_time_str, '%H:%M:%S')
                    display_time = t.strftime('%I:%M:%S %p').lstrip('0')
                except:
                    display_time = study_time_str
            
            # Build Line 1: Accession:NAME | Sex Age | Date
            line1_parts = []
            if accession:
                line1_parts.append(f"{accession}:{patient_name}")
            else:
                line1_parts.append(patient_name)
            
            if patient_sex or age_str:
                sex_age = f"{patient_sex} {age_str}".strip()
                line1_parts.append(sex_age)
            
            if display_date:
                line1_parts.append(display_date)
            
            line1 = "  |  ".join(line1_parts) if len(line1_parts) > 1 else line1_parts[0] if line1_parts else patient_name
            
            # Build Line 2: Location | Type | GA | Sonographer | Time
            line2_parts = []
            if location:
                line2_parts.append(location)
            if study_type:
                line2_parts.append(study_type)
            if gestational_age:
                line2_parts.append(gestational_age)
            if sonographer:
                line2_parts.append(sonographer)
            if display_time:
                line2_parts.append(display_time)
            
            line2 = "  |  ".join(line2_parts) if line2_parts else ''
            
            # Combine lines
            if line2:
                overlay_text = f"{line1}\n{line2}"
            else:
                overlay_text = line1
            
            print(f"[MODE] Clinical Correction (Full): Overlaying '{overlay_text}'")
        else:
            # Clinical mode - basic, just display new patient name
            overlay_text = new_name_text
            print(f"[MODE] Clinical Correction (Basic): Overlaying '{overlay_text}'")
        
        # Generate and apply overlay for both modes (with auto-scaling for long text)
        # For multi-line text, we need to handle it specially
        overlay = corrector.generate_medical_overlay(overlay_text, w, h, auto_scale=True)
        
        for i in range(num_frames):
            frame = arr[i]
            # Apply overlay on top of the black box
            x_end = min(x + w, frame_w)
            y_end = min(y + h, frame_h)
            x_start = max(0, x)
            y_start = max(0, y)
            actual_w = x_end - x_start
            actual_h = y_end - y_start
            
            if actual_w > 0 and actual_h > 0:
                overlay_resized = overlay[:actual_h, :actual_w]
                frame[y_start:y_start + actual_h, x_start:x_start + actual_w] = overlay_resized
            
            if (i + 1) % 10 == 0 or i == num_frames - 1:
                print(f"  [OVERLAY] Applied to frame {i + 1}/{num_frames}")
    
        # ═══════════════════════════════════════════════════════════════════════════
        # PREPARE PIXEL DATA FOR DICOM - MODALITY-AWARE OUTPUT
        # ═══════════════════════════════════════════════════════════════════════════
        print("Preparing pixel data for DICOM...")
        
        # Get modality for output format decision
        modality = getattr(ds, 'Modality', 'US').upper()
        
        # Decide output format based on modality
        # XR, CR, DX = Radiography (preserve grayscale, original bit-depth)
        # US, XA = Ultrasound/Angio (RGB overlay acceptable)
        # CT, MR = Cross-sectional (usually grayscale)
        preserve_grayscale = modality in ['XR', 'CR', 'DX', 'CT', 'MR', 'PT', 'NM']
        
        if preserve_grayscale and arr_original_depth is not None:
            # ═══════════════════════════════════════════════════════════════════════
            # ZERO-LOSS PATH: Use original bit-depth data (16-bit for X-Ray etc)
            # ═══════════════════════════════════════════════════════════════════════
            print(f"[ZERO-LOSS] Using original {original_dtype} data for {modality} modality")
            
            # Use the masked original depth array (grayscale)
            if arr_original_depth.shape[3] == 3:
                # Convert RGB back to grayscale (take first channel or average)
                arr_out = arr_original_depth[:, :, :, 0]  # Shape: (Frames, H, W)
            else:
                arr_out = arr_original_depth[:, :, :, 0] if arr_original_depth.shape[3] == 1 else arr_original_depth
            
            # For single frame, remove frame dimension
            if arr_out.shape[0] == 1:
                arr_out = arr_out[0]  # Shape: (H, W)
            
            print(f"Output array shape: {arr_out.shape}, dtype: {arr_out.dtype}")
            
            # Update DICOM header for grayscale
            ds.PhotometricInterpretation = original_photometric if 'MONOCHROME' in original_photometric else 'MONOCHROME2'
            ds.SamplesPerPixel = 1
            if hasattr(ds, 'PlanarConfiguration'):
                del ds.PlanarConfiguration
            
            # Preserve original bit depth
            if original_dtype == np.uint16:
                ds.BitsAllocated = 16
                ds.BitsStored = 16
                ds.HighBit = 15
            else:
                ds.BitsAllocated = 8
                ds.BitsStored = 8
                ds.HighBit = 7
            ds.PixelRepresentation = 0  # Unsigned
            
        else:
            # ═══════════════════════════════════════════════════════════════════════
            # STANDARD PATH: RGB output (for US, XA with overlay)
            # ═══════════════════════════════════════════════════════════════════════
            print(f"[STANDARD] Using RGB output for {modality} modality")
            
            # Keep as 4D RGB array (Frames, H, W, 3) - ensure 3 channels
            if arr.shape[3] == 4:
                # Remove alpha channel if present
                arr = arr[:, :, :, :3]
            
            # Safety cast: ensure uint8 (0-255)
            arr = arr.astype(np.uint8)
            
            # For single frame, remove the frame dimension
            if arr.shape[0] == 1:
                arr_out = arr[0]  # Shape: (H, W, 3)
            else:
                arr_out = arr  # Shape: (Frames, H, W, 3)
            
            print(f"Output array shape: {arr_out.shape}, dtype: {arr_out.dtype}")
            
            # Update DICOM header for RGB
            ds.PhotometricInterpretation = "RGB"
            ds.SamplesPerPixel = 3
            ds.PlanarConfiguration = 0  # Interleaved
            ds.BitsAllocated = 8
            ds.BitsStored = 8
            ds.HighBit = 7
            ds.PixelRepresentation = 0
    else:
        # Pixel processing disabled (Memory Guard)
        # We perform NO pixel operations. We just keep the original PixelData as is.
        # However, we must ensure we don't accidentally write broken pixel data.
        print("[MEMORY GUARD] Bypassing pixel manipulation/masking pipeline.")
        arr_out = None  # Signal that we have no new array

    # Update DICOM header and anonymize metadata
    print("Updating DICOM metadata...")
    
    # Inject audit tag using private block (before anonymization)
    try:
        private_creator = "ClinicalCorrector"
        block = ds.private_block(0x0009, private_creator, create=True)
        audit_string = f"Original: {old_name_text} | Fixed: {new_name_text}"
        block.add_new(0x10, 'LO', audit_string[:64])
    except Exception as e:
        print(f"Warning: Could not add audit tag: {e}")
    
    # Full metadata anonymization (PHI removal + UID remapping)
    anonymize_metadata(ds, new_name_text, research_context=research_context, clinical_context=clinical_context)

    # Update frame count if multi-frame
    if arr_out.ndim == 4:
        ds.NumberOfFrames = arr_out.shape[0]
    elif arr_out.ndim == 3 and arr.shape[0] > 1:
        # Grayscale multi-frame: (Frames, H, W)
        ds.NumberOfFrames = arr_out.shape[0]
    elif hasattr(ds, 'NumberOfFrames'):
        del ds.NumberOfFrames

    # Update pixel data (ONLY if we processed it)
    if pixel_processing_enabled and arr_out is not None:
        ds.PixelData = arr_out.tobytes()

        # Reset compression to Explicit VR Little Endian (uncompressed) only if we changed pixels
        ds.file_meta.TransferSyntaxUID = ExplicitVRLittleEndian

    # Save the modified DICOM
    print(f"Saving to: {output_path}")
    try:
        ds.save_as(output_path)
    except Exception as e:
        if evidence_bundle:
            try:
                evidence_bundle.add_exception(
                    exception_type="SAVE_FAILURE",
                    message=str(e),
                    severity="ERROR",
                    source_sop_uid=source_sop_uid
                )
            except:
                pass
        raise RuntimeError(f"Failed to save DICOM file: {e}")
    
    # EVIDENCE: Record linkage (source -> masked) and decision
    if evidence_bundle:
        try:
            # Get the NEW UIDs after remapping
            masked_sop_uid = str(getattr(ds, 'SOPInstanceUID', 'UNKNOWN'))
            masked_series_uid = str(getattr(ds, 'SeriesInstanceUID', 'UNKNOWN'))
            masked_study_uid = str(getattr(ds, 'StudyInstanceUID', 'UNKNOWN'))
            
            # Record linkage
            evidence_bundle.add_linkage(
                source_study_uid=source_study_uid,
                source_series_uid=source_series_uid,
                source_sop_uid=source_sop_uid,
                masked_study_uid=masked_study_uid,
                masked_series_uid=masked_series_uid,
                masked_sop_uid=masked_sop_uid,
                uid_strategy="REGENERATE_DETERMINISTIC"
            )
            
            # Record decision
            evidence_bundle.add_decision(
                decision_type="MASK" if all_masks else "SKIP",
                source_sop_uid=source_sop_uid,
                masked_sop_uid=masked_sop_uid,
                detections_count=len(evidence_bundle.detection_results),
                actions_count=len(all_masks),
                status="complete"
            )
            
            # Record masked output hash
            evidence_bundle.add_masked_hash(
                sop_instance_uid=masked_sop_uid,
                pixel_hash=f"sha256:{sha256_bytes(ds.PixelData)}",
                series_uid=masked_series_uid
            )
        except Exception as le:
            print(f"[EVIDENCE] Warning: Could not log linkage/decision: {le}")

    print("Processing complete!")
    return True


def main():  # pragma: no cover
    """Main entry point with CLI argument parsing."""
    parser = argparse.ArgumentParser(
        description="De-identify patient information in DICOM ultrasound files",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python src/run_on_dicom.py --input scan.dcm --output fixed.dcm --old "SMITH" --new "JONES"
    python src/run_on_dicom.py -i patient.dcm -o anonymized.dcm --old "DOE, JOHN" --new "ANON001"
    
    # With evidence bundle (Gate 2/3 Model B compliance):
    python src/run_on_dicom.py -i scan.dcm -o masked.dcm --old "X" --new "Y" --evidence-bundle-dir ./evidence
        """
    )

    parser.add_argument(
        "-i", "--input",
        required=True,
        help="Path to input DICOM file"
    )
    parser.add_argument(
        "-o", "--output",
        required=True,
        help="Path for output DICOM file"
    )
    parser.add_argument(
        "--old",
        required=True,
        help="Original patient name (for audit trail)"
    )
    parser.add_argument(
        "--new",
        required=True,
        help="New patient name to apply"
    )
    parser.add_argument(
        "--evidence-bundle-dir",
        default=None,
        help="Optional: Directory to write evidence bundle (Gate 2/3 Model B compliance)"
    )

    args = parser.parse_args()
    
    # ═══════════════════════════════════════════════════════════════════════════
    # EVIDENCE BUNDLE LIFECYCLE
    # ═══════════════════════════════════════════════════════════════════════════
    evidence_bundle = None
    if args.evidence_bundle_dir and EVIDENCE_BUNDLE_AVAILABLE:
        from pathlib import Path
        import platform
        import sys as _sys
        
        print(f"[EVIDENCE] Creating evidence bundle in: {args.evidence_bundle_dir}")
        evidence_bundle = EvidenceBundle(
            voxelmask_version="0.5.0",
            compliance_profile="FOI"
        )
        evidence_bundle.start_processing()
        
        # Set app build info
        evidence_bundle.set_app_build(
            version="0.5.0",
            git_commit="unknown",
            ocr_engine="PaddleOCR",
            ocr_version="2.7.0"
        )
        evidence_bundle.set_runtime_env(
            python_version=f"{_sys.version_info.major}.{_sys.version_info.minor}.{_sys.version_info.micro}",
            platform=platform.platform()
        )
    elif args.evidence_bundle_dir and not EVIDENCE_BUNDLE_AVAILABLE:
        print("[EVIDENCE] Warning: Evidence bundle requested but audit module not available")

    try:
        success = process_dicom(
            input_path=args.input,
            output_path=args.output,
            old_name_text=args.old,
            new_name_text=args.new,
            evidence_bundle=evidence_bundle
        )
        
        # Finalize evidence bundle on success
        if evidence_bundle and success:
            try:
                from pathlib import Path
                evidence_bundle.end_processing()
                bundle_path = evidence_bundle.finalize(Path(args.evidence_bundle_dir))
                print(f"[EVIDENCE] Bundle written to: {bundle_path}")
            except Exception as fe:
                print(f"[EVIDENCE] Warning: Failed to finalize bundle: {fe}")
        
        if success:
            print(f"\nSuccess! De-identified DICOM saved to: {args.output}")
            sys.exit(0)
        else:
            print("\nProcessing failed.")
            sys.exit(1)
    except Exception as e:
        # Attempt to finalize evidence bundle even on failure
        if evidence_bundle:
            try:
                from pathlib import Path
                evidence_bundle.add_exception(
                    exception_type="PROCESSING_FAILURE",
                    message=str(e),
                    severity="ERROR"
                )
                evidence_bundle.end_processing()
                bundle_path = evidence_bundle.finalize(Path(args.evidence_bundle_dir))
                print(f"[EVIDENCE] Failure bundle written to: {bundle_path}")
            except Exception as fe:
                print(f"[EVIDENCE] Warning: Failed to write failure bundle: {fe}")
        
        print(f"\nError: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
