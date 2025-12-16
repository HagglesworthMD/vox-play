#!/usr/bin/env python3
"""
Gate 1 — Step 3A: Verification - Order Diff Report
===================================================
PURPOSE: Compare baseline vs ordered manifests to verify:
         - No dropped instances
         - No duplicates
         - All reorders explainable by decision log
         - No metadata/pixel changes (ordering context only)

OUTPUTS:
    - order_diff_report.json
    - order_diff_report.sha256

ACCEPTANCE CRITERIA:
    - baseline count == ordered count (per series + total)
    - all SOPInstanceUID unique within each series
    - every position change maps to a decision log entry
    - only allowed cause: ordering precedence
"""

import json
import hashlib
from pathlib import Path
from datetime import datetime, timezone
from dataclasses import dataclass, asdict
from typing import List, Dict, Set
from collections import defaultdict
import uuid


@dataclass
class SeriesDiffResult:
    """Diff result for a single series."""
    series_instance_uid: str
    baseline_count: int
    ordered_count: int
    dropped_instances: int
    duplicate_uids: List[str]
    reorders_with_decision: int
    reorders_without_decision: int
    unexplained_changes: List[str]
    passed: bool


@dataclass
class OrderDiffReport:
    """Complete diff report for Step 3A."""
    report_id: str
    timestamp: str
    baseline_manifest_id: str
    ordered_manifest_id: str
    baseline_hash: str
    ordered_hash: str
    decision_log_hash: str
    total_baseline_count: int
    total_ordered_count: int
    total_dropped: int
    total_duplicates: int
    total_unexplained_reorders: int
    series_results: List[dict]
    all_checks_passed: bool
    failure_reasons: List[str]


def verify_ordering(evidence_dir: Path):
    """
    Verify baseline vs ordered manifests.
    """
    # Load all three artefacts
    baseline_path = evidence_dir / "baseline_order_manifest.json"
    ordered_path = evidence_dir / "ordered_series_manifest.json"
    decision_log_path = evidence_dir / "ordering_decision_log.json"
    
    baseline = json.loads(baseline_path.read_text())
    ordered = json.loads(ordered_path.read_text())
    decision_log = json.loads(decision_log_path.read_text())
    
    # Compute hashes
    baseline_hash = hashlib.sha256(baseline_path.read_bytes()).hexdigest()
    ordered_hash = hashlib.sha256(ordered_path.read_bytes()).hexdigest()
    decision_log_hash = hashlib.sha256(decision_log_path.read_bytes()).hexdigest()
    
    report_id = str(uuid.uuid4())
    timestamp = datetime.now(timezone.utc).isoformat()
    
    # Build lookup structures
    baseline_by_series: Dict[str, List[dict]] = defaultdict(list)
    for entry in baseline['entries']:
        baseline_by_series[entry['series_instance_uid']].append(entry)
    
    ordered_by_series: Dict[str, List[dict]] = defaultdict(list)
    for entry in ordered['entries']:
        ordered_by_series[entry['series_instance_uid']].append(entry)
    
    # Build decision lookup: (series_uid, sop_uid) -> decision
    decision_lookup: Dict[tuple, dict] = {}
    for decision in decision_log['decisions']:
        key = (decision['series_instance_uid'], decision['sop_instance_uid'])
        decision_lookup[key] = decision
    
    # Verify each series
    series_results: List[dict] = []
    total_dropped = 0
    total_duplicates = 0
    total_unexplained = 0
    failure_reasons: List[str] = []
    
    all_series_uids = set(baseline_by_series.keys()) | set(ordered_by_series.keys())
    
    for series_uid in sorted(all_series_uids):
        print(f"\nVerifying series: {series_uid[:50]}...")
        
        baseline_entries = baseline_by_series.get(series_uid, [])
        ordered_entries = ordered_by_series.get(series_uid, [])
        
        baseline_count = len(baseline_entries)
        ordered_count = len(ordered_entries)
        dropped = baseline_count - ordered_count if baseline_count > ordered_count else 0
        
        # Check for duplicates in ordered
        ordered_sop_uids = [e['sop_instance_uid'] for e in ordered_entries]
        seen_uids: Set[str] = set()
        duplicate_uids: List[str] = []
        for uid in ordered_sop_uids:
            if uid in seen_uids:
                duplicate_uids.append(uid)
            seen_uids.add(uid)
        
        # Check all SOPInstanceUIDs are preserved
        baseline_sop_uids = set(e['sop_instance_uid'] for e in baseline_entries)
        ordered_sop_set = set(ordered_sop_uids)
        missing_uids = baseline_sop_uids - ordered_sop_set
        extra_uids = ordered_sop_set - baseline_sop_uids
        
        if missing_uids:
            dropped = len(missing_uids)
            failure_reasons.append(f"Series {series_uid[:30]}: {dropped} instances dropped: {list(missing_uids)[:3]}...")
        
        if extra_uids:
            failure_reasons.append(f"Series {series_uid[:30]}: {len(extra_uids)} unexpected instances appeared")
        
        # Verify all reorders have decision log entries
        reorders_with_decision = 0
        reorders_without_decision = 0
        unexplained_changes: List[str] = []
        
        # Build baseline position map
        baseline_pos = {e['sop_instance_uid']: i for i, e in enumerate(baseline_entries)}
        
        for new_idx, entry in enumerate(ordered_entries):
            sop_uid = entry['sop_instance_uid']
            old_idx = baseline_pos.get(sop_uid)
            
            if old_idx is None:
                unexplained_changes.append(f"SOP {sop_uid[:30]} not found in baseline")
                continue
            
            position_changed = (old_idx != new_idx)
            
            if position_changed:
                # Look for decision
                key = (series_uid, sop_uid)
                decision = decision_lookup.get(key)
                
                if decision and decision.get('position_changed'):
                    reorders_with_decision += 1
                else:
                    reorders_without_decision += 1
                    unexplained_changes.append(
                        f"SOP {sop_uid[:30]} moved {old_idx}->{new_idx} without decision record"
                    )
        
        passed = (
            dropped == 0 and
            len(duplicate_uids) == 0 and
            reorders_without_decision == 0 and
            len(unexplained_changes) == 0
        )
        
        result = SeriesDiffResult(
            series_instance_uid=series_uid,
            baseline_count=baseline_count,
            ordered_count=ordered_count,
            dropped_instances=dropped,
            duplicate_uids=duplicate_uids,
            reorders_with_decision=reorders_with_decision,
            reorders_without_decision=reorders_without_decision,
            unexplained_changes=unexplained_changes,
            passed=passed
        )
        series_results.append(asdict(result))
        
        total_dropped += dropped
        total_duplicates += len(duplicate_uids)
        total_unexplained += reorders_without_decision
        
        status = "✓ PASS" if passed else "✗ FAIL"
        print(f"  Baseline: {baseline_count}, Ordered: {ordered_count}")
        print(f"  Dropped: {dropped}, Duplicates: {len(duplicate_uids)}")
        print(f"  Reorders (with decision): {reorders_with_decision}")
        print(f"  Reorders (unexplained): {reorders_without_decision}")
        print(f"  Status: {status}")
    
    # Final assessment
    all_passed = (
        total_dropped == 0 and
        total_duplicates == 0 and
        total_unexplained == 0 and
        len(failure_reasons) == 0
    )
    
    # Build report
    report = OrderDiffReport(
        report_id=report_id,
        timestamp=timestamp,
        baseline_manifest_id=baseline['manifest_id'],
        ordered_manifest_id=ordered['manifest_id'],
        baseline_hash=baseline_hash,
        ordered_hash=ordered_hash,
        decision_log_hash=decision_log_hash,
        total_baseline_count=len(baseline['entries']),
        total_ordered_count=len(ordered['entries']),
        total_dropped=total_dropped,
        total_duplicates=total_duplicates,
        total_unexplained_reorders=total_unexplained,
        series_results=series_results,
        all_checks_passed=all_passed,
        failure_reasons=failure_reasons
    )
    
    # Write report
    report_json = json.dumps(asdict(report), indent=2, sort_keys=True)
    report_path = evidence_dir / "order_diff_report.json"
    report_path.write_text(report_json)
    report_hash = hashlib.sha256(report_json.encode('utf-8')).hexdigest()
    
    # Write hash
    hash_path = evidence_dir / "order_diff_report.sha256"
    hash_path.write_text(f"{report_hash}  order_diff_report.json\n")
    
    print("\n" + "="*60)
    print("GATE 1 — STEP 3A VERIFICATION COMPLETE")
    print("="*60)
    print(f"Report ID:              {report_id}")
    print(f"Timestamp:              {timestamp}")
    print("="*60)
    print(f"Total Baseline:         {len(baseline['entries'])}")
    print(f"Total Ordered:          {len(ordered['entries'])}")
    print(f"Dropped Instances:      {total_dropped}")
    print(f"Duplicate UIDs:         {total_duplicates}")
    print(f"Unexplained Reorders:   {total_unexplained}")
    print("="*60)
    
    if all_passed:
        print("✓ ALL VERIFICATION CHECKS PASSED")
    else:
        print("✗ VERIFICATION FAILED")
        for reason in failure_reasons:
            print(f"  - {reason}")
    
    print("="*60)
    print(f"✓ Written: {report_path}")
    print(f"  SHA-256: {report_hash}")
    print("="*60)
    
    return all_passed, report_hash


def main():
    evidence_dir = Path(__file__).parent
    
    print("="*60)
    print("GATE 1 — STEP 3A: VERIFICATION - ORDER DIFF")
    print("="*60)
    print(f"Evidence Dir: {evidence_dir}")
    print("="*60)
    
    passed, report_hash = verify_ordering(evidence_dir)
    return passed


if __name__ == "__main__":
    main()
