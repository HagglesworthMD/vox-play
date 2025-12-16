#!/usr/bin/env python3
"""
Gate 1 — Step 2: Apply Ordering Logic
======================================
PURPOSE: Apply deterministic ordering rules to baseline manifest.
         Generate ordered manifest and decision log.

ORDERING PRECEDENCE (per Gate 1 Runbook):
    1. Multi-frame index (if applicable)
    2. InstanceNumber (numeric, stable)
    3. AcquisitionDateTime / AcquisitionTime
    4. SOPInstanceUID (lexical tie-breaker)

OUTPUTS:
    - ordered_series_manifest.json
    - ordered_series_manifest.sha256
    - ordering_decision_log.json

GUARDRAILS:
    - Deterministic, repeatable
    - No pixel, OCR, masking, or anonymisation paths invoked
"""

import json
import hashlib
from pathlib import Path
from datetime import datetime, timezone
from dataclasses import dataclass, asdict, field
from typing import Optional, List, Dict, Any
from collections import defaultdict
import uuid


@dataclass
class OrderingDecision:
    """Record of a single ordering decision."""
    series_instance_uid: str
    entry_index_before: int
    entry_index_after: int
    sop_instance_uid: str
    instance_number: Optional[int]
    acquisition_time: Optional[str]
    ordering_method_used: str  # "INSTANCE_NUMBER" | "ACQUISITION_TIME" | "SOP_UID_TIEBREAK"
    tie_break_applied: bool
    tie_break_reason: Optional[str]
    position_changed: bool


@dataclass
class SeriesOrderingResult:
    """Ordering result for a single series."""
    series_instance_uid: str
    total_instances: int
    ordering_method: str
    instances_reordered: int
    ties_by_instance_number: int
    ties_resolved_by_time: int
    ties_resolved_by_uid: int
    missing_instance_number: int
    missing_acquisition_time: int


@dataclass
class OrderingDecisionLog:
    """Complete decision log for Step 2."""
    log_id: str
    timestamp: str
    baseline_manifest_id: str
    baseline_manifest_hash: str
    series_results: List[dict]
    decisions: List[dict]
    summary: dict


def parse_acquisition_time(time_str: Optional[str]) -> Optional[float]:
    """
    Parse DICOM time string to comparable float.
    Format: HHMMSS.FFFFFF or HHMMSS
    """
    if not time_str:
        return None
    try:
        # Remove any trailing spaces
        time_str = time_str.strip()
        # Handle HHMMSS.FFFFFF format
        if '.' in time_str:
            parts = time_str.split('.')
            hms = parts[0]
            frac = float('0.' + parts[1]) if len(parts) > 1 else 0.0
        else:
            hms = time_str
            frac = 0.0
        
        if len(hms) >= 6:
            h = int(hms[0:2])
            m = int(hms[2:4])
            s = int(hms[4:6])
            return h * 3600 + m * 60 + s + frac
        return None
    except (ValueError, IndexError):
        return None


def sort_key_for_entry(entry: dict) -> tuple:
    """
    Generate sort key following Gate 1 precedence:
    1. Multi-frame index (if applicable) - N/A for this dataset
    2. InstanceNumber (numeric)
    3. AcquisitionDateTime / AcquisitionTime
    4. SOPInstanceUID (lexical)
    """
    # Multi-frame index (use frame_number if present, else 0)
    frame_idx = entry.get('frame_number') or 0
    
    # InstanceNumber (use large value if missing to push to end)
    instance_num = entry.get('instance_number')
    if instance_num is None:
        instance_num = float('inf')
    
    # AcquisitionDateTime first, then AcquisitionTime
    acq_datetime = entry.get('acquisition_datetime')
    acq_time = entry.get('acquisition_time')
    
    time_value = None
    if acq_datetime:
        # Try to parse datetime
        try:
            time_value = float(acq_datetime.replace('.', ''))
        except:
            pass
    if time_value is None and acq_time:
        time_value = parse_acquisition_time(acq_time)
    
    # Use infinity if no time available
    if time_value is None:
        time_value = float('inf')
    
    # SOPInstanceUID as final tie-breaker (lexical)
    sop_uid = entry.get('sop_instance_uid', '')
    
    return (frame_idx, instance_num, time_value, sop_uid)


def determine_ordering_method(entry: dict, prev_entry: Optional[dict]) -> tuple:
    """
    Determine which ordering method was used for placing this entry.
    Returns (method_name, is_tie_break, reason)
    """
    if prev_entry is None:
        return ("FIRST_ENTRY", False, None)
    
    # Check what differentiated this from previous
    curr_in = entry.get('instance_number')
    prev_in = prev_entry.get('instance_number')
    
    # If InstanceNumbers differ, that was the deciding factor
    if curr_in != prev_in and curr_in is not None and prev_in is not None:
        return ("INSTANCE_NUMBER", False, None)
    
    # InstanceNumbers are same or missing - check time
    curr_time = parse_acquisition_time(entry.get('acquisition_time'))
    prev_time = parse_acquisition_time(prev_entry.get('acquisition_time'))
    
    if curr_time != prev_time and curr_time is not None and prev_time is not None:
        return ("ACQUISITION_TIME", True, f"IN={curr_in} tied, resolved by AcquisitionTime")
    
    # Fall through to UID tie-breaker
    return ("SOP_UID_TIEBREAK", True, f"IN={curr_in} and AcquisitionTime tied/missing, resolved by SOPInstanceUID lexical order")


def apply_ordering(baseline_path: Path, output_dir: Path):
    """
    Apply Gate 1 ordering logic to baseline manifest.
    """
    # Load baseline manifest
    baseline_data = json.loads(baseline_path.read_text())
    baseline_hash = hashlib.sha256(baseline_path.read_bytes()).hexdigest()
    
    log_id = str(uuid.uuid4())
    timestamp = datetime.now(timezone.utc).isoformat()
    
    # Group entries by SeriesInstanceUID
    series_entries: Dict[str, List[dict]] = defaultdict(list)
    for entry in baseline_data['entries']:
        series_uid = entry['series_instance_uid']
        series_entries[series_uid].append(entry)
    
    # Track decisions and results
    all_decisions: List[dict] = []
    series_results: List[dict] = []
    ordered_entries: List[dict] = []
    
    # Summary stats
    total_reordered = 0
    total_uid_tiebreaks = 0
    total_missing_in = 0
    total_missing_time = 0
    
    for series_uid, entries in sorted(series_entries.items()):
        print(f"\nProcessing series: {series_uid[:50]}...")
        print(f"  Entries: {len(entries)}")
        
        # Track original order (by file_index as observational baseline)
        original_order = {e['sop_instance_uid']: i for i, e in enumerate(entries)}
        
        # Sort by Gate 1 precedence
        sorted_entries = sorted(entries, key=sort_key_for_entry)
        
        # Analyze what changed
        series_reordered = 0
        series_in_ties = 0
        series_time_ties = 0
        series_uid_ties = 0
        series_missing_in = 0
        series_missing_time = 0
        
        prev_entry = None
        for new_idx, entry in enumerate(sorted_entries):
            sop_uid = entry['sop_instance_uid']
            old_idx = original_order[sop_uid]
            position_changed = (old_idx != new_idx)
            
            if position_changed:
                series_reordered += 1
            
            # Check for missing data
            if entry.get('instance_number') is None:
                series_missing_in += 1
            if entry.get('acquisition_time') is None and entry.get('acquisition_datetime') is None:
                series_missing_time += 1
            
            # Determine ordering method
            method, is_tiebreak, reason = determine_ordering_method(entry, prev_entry)
            
            if is_tiebreak:
                if method == "ACQUISITION_TIME":
                    series_time_ties += 1
                elif method == "SOP_UID_TIEBREAK":
                    series_uid_ties += 1
            
            # Check for InstanceNumber ties (same IN as previous)
            if prev_entry and entry.get('instance_number') == prev_entry.get('instance_number'):
                series_in_ties += 1
            
            decision = OrderingDecision(
                series_instance_uid=series_uid,
                entry_index_before=old_idx,
                entry_index_after=new_idx,
                sop_instance_uid=sop_uid,
                instance_number=entry.get('instance_number'),
                acquisition_time=entry.get('acquisition_time'),
                ordering_method_used=method,
                tie_break_applied=is_tiebreak,
                tie_break_reason=reason,
                position_changed=position_changed
            )
            all_decisions.append(asdict(decision))
            
            # Add ordered index to entry
            ordered_entry = entry.copy()
            ordered_entry['ordered_index'] = new_idx + 1  # 1-indexed
            ordered_entry['original_file_index'] = entry['file_index']
            ordered_entries.append(ordered_entry)
            
            prev_entry = entry
        
        result = SeriesOrderingResult(
            series_instance_uid=series_uid,
            total_instances=len(entries),
            ordering_method="INSTANCE_NUMBER" if series_uid_ties == 0 else "MIXED",
            instances_reordered=series_reordered,
            ties_by_instance_number=series_in_ties,
            ties_resolved_by_time=series_time_ties,
            ties_resolved_by_uid=series_uid_ties,
            missing_instance_number=series_missing_in,
            missing_acquisition_time=series_missing_time
        )
        series_results.append(asdict(result))
        
        total_reordered += series_reordered
        total_uid_tiebreaks += series_uid_ties
        total_missing_in += series_missing_in
        total_missing_time += series_missing_time
        
        print(f"  Reordered: {series_reordered}")
        print(f"  IN ties: {series_in_ties}")
        print(f"  Time ties: {series_time_ties}")
        print(f"  UID tie-breaks: {series_uid_ties}")
        print(f"  Missing IN: {series_missing_in}")
        print(f"  Missing AcqTime: {series_missing_time}")
    
    # Build decision log
    decision_log = OrderingDecisionLog(
        log_id=log_id,
        timestamp=timestamp,
        baseline_manifest_id=baseline_data['manifest_id'],
        baseline_manifest_hash=baseline_hash,
        series_results=series_results,
        decisions=all_decisions,
        summary={
            "total_entries": len(baseline_data['entries']),
            "total_series": len(series_entries),
            "total_instances_reordered": total_reordered,
            "total_ties_resolved_by_uid": total_uid_tiebreaks,
            "total_missing_instance_number": total_missing_in,
            "total_missing_acquisition_time": total_missing_time
        }
    )
    
    # Build ordered manifest
    ordered_manifest = {
        "manifest_id": str(uuid.uuid4()),
        "generation_timestamp": timestamp,
        "baseline_manifest_id": baseline_data['manifest_id'],
        "baseline_manifest_hash": baseline_hash,
        "ordering_precedence": [
            "1. Multi-frame index (if applicable)",
            "2. InstanceNumber (numeric)",
            "3. AcquisitionDateTime / AcquisitionTime",
            "4. SOPInstanceUID (lexical tie-breaker)"
        ],
        "total_entries": len(ordered_entries),
        "total_series": len(series_entries),
        "entries": ordered_entries,
        "script_version": "1.0.0"
    }
    
    # Write ordered manifest
    ordered_manifest_json = json.dumps(ordered_manifest, indent=2, sort_keys=True)
    ordered_path = output_dir / "ordered_series_manifest.json"
    ordered_path.write_text(ordered_manifest_json)
    ordered_hash = hashlib.sha256(ordered_manifest_json.encode('utf-8')).hexdigest()
    
    # Write ordered manifest hash
    hash_path = output_dir / "ordered_series_manifest.sha256"
    hash_path.write_text(f"{ordered_hash}  ordered_series_manifest.json\n")
    
    # Write decision log
    decision_log_json = json.dumps(asdict(decision_log), indent=2, sort_keys=True)
    log_path = output_dir / "ordering_decision_log.json"
    log_path.write_text(decision_log_json)
    log_hash = hashlib.sha256(decision_log_json.encode('utf-8')).hexdigest()
    
    print("\n" + "="*60)
    print("GATE 1 — STEP 2 APPLY ORDERING COMPLETE")
    print("="*60)
    print(f"Log ID:                    {log_id}")
    print(f"Timestamp:                 {timestamp}")
    print(f"Baseline Manifest ID:      {baseline_data['manifest_id']}")
    print(f"Baseline Manifest Hash:    {baseline_hash}")
    print("="*60)
    print(f"Total Entries:             {len(ordered_entries)}")
    print(f"Total Series:              {len(series_entries)}")
    print(f"Instances Reordered:       {total_reordered}")
    print(f"Ties Resolved by UID:      {total_uid_tiebreaks}")
    print(f"Missing InstanceNumber:    {total_missing_in}")
    print(f"Missing AcquisitionTime:   {total_missing_time}")
    print("="*60)
    print(f"✓ Written: {ordered_path}")
    print(f"  SHA-256: {ordered_hash}")
    print(f"✓ Written: {log_path}")
    print(f"  SHA-256: {log_hash}")
    print("="*60)
    
    return ordered_hash, log_hash, total_reordered, total_uid_tiebreaks, total_missing_in + total_missing_time


def main():
    script_dir = Path(__file__).parent
    baseline_path = script_dir / "baseline_order_manifest.json"
    output_dir = script_dir
    
    print("="*60)
    print("GATE 1 — STEP 2: APPLY ORDERING LOGIC")
    print("="*60)
    print(f"Baseline: {baseline_path}")
    print(f"Output:   {output_dir}")
    print("="*60)
    
    if not baseline_path.exists():
        print(f"ERROR: Baseline manifest not found: {baseline_path}")
        return
    
    apply_ordering(baseline_path, output_dir)


if __name__ == "__main__":
    main()
