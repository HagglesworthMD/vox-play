#!/usr/bin/env python3
"""
Gate 1 — Step 1: Baseline Capture Script
=========================================
PURPOSE: Extract and persist baseline ordering metadata from DICOM source files.
         No mutation. Copy-out only.

OUTPUTS:
  - baseline_order_manifest.json
  - baseline_order_manifest.sha256

GUARDRAILS:
  - Copy-out only
  - No metadata changes
  - No pixel mutation
"""

import json
import hashlib
import os
from pathlib import Path
from datetime import datetime, timezone
from dataclasses import dataclass, asdict
from typing import Optional, List
import sys

# Add project root to path for pydicom if in venv
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root / ".venv/lib/python3.11/site-packages"))
sys.path.insert(0, str(project_root / ".venv/lib/python3.12/site-packages"))

try:
    import pydicom
except ImportError:
    print("ERROR: pydicom not available. Activate venv first.")
    sys.exit(1)


@dataclass
class BaselineEntry:
    """Single instance entry in baseline manifest."""
    file_index: int                        # Filesystem index (observational only)
    relative_path: str                     # Path relative to source root
    sop_instance_uid: str                  # SOPInstanceUID (0008,0018)
    series_instance_uid: str               # SeriesInstanceUID (0020,000E)
    study_instance_uid: str                # StudyInstanceUID (0020,000D)
    instance_number: Optional[int]         # InstanceNumber (0020,0013)
    acquisition_time: Optional[str]        # AcquisitionTime (0008,0032)
    acquisition_datetime: Optional[str]    # AcquisitionDateTime (0008,002A)
    modality: str                          # Modality (0008,0060)
    sop_class_uid: str                     # SOPClassUID (0008,0016)
    number_of_frames: Optional[int]        # NumberOfFrames (0028,0008) - for multi-frame
    is_multiframe: bool                    # True if NumberOfFrames > 1


@dataclass  
class BaselineOrderManifest:
    """Complete baseline manifest for Gate 1 Step 1."""
    manifest_id: str                       # Script-generated UUID
    capture_timestamp: str                 # ISO 8601 UTC
    source_directory: str                  # Absolute path to source
    total_files: int                       # Count of DICOM files
    total_series: int                      # Count of unique SeriesInstanceUIDs
    modality_flags: dict                   # Modality-specific observations
    entries: List[dict]                    # List of BaselineEntry as dicts
    script_version: str                    # Script version for reproducibility


def get_safe_value(ds, tag_name: str, default=None):
    """Safely extract a DICOM tag value without mutation."""
    try:
        if hasattr(ds, tag_name):
            val = getattr(ds, tag_name)
            if val is not None:
                if tag_name in ['InstanceNumber', 'NumberOfFrames']:
                    return int(val)
                return str(val)
    except Exception:
        pass
    return default


def capture_baseline(source_dir: Path, output_dir: Path) -> str:
    """
    Capture baseline ordering metadata from all DICOM files in source_dir.
    
    Returns: SHA-256 hash of the manifest
    """
    import uuid
    
    manifest_id = str(uuid.uuid4())
    capture_timestamp = datetime.now(timezone.utc).isoformat()
    
    # Find all DICOM files (with or without .dcm extension)
    dcm_files = []
    for ext in ['*.dcm', '*.DCM', '*']:
        dcm_files.extend(source_dir.rglob(ext))
    
    # Filter to actual files and deduplicate
    dcm_files = sorted(set(f for f in dcm_files if f.is_file()))
    
    # Track entries and modality flags
    entries = []
    series_uids = set()
    modality_flags = {
        "us_multiframe_present": False,
        "ct_mr_cine_present": False,
        "encapsulated_pdf_present": False,
        "modalities_found": set()
    }
    
    file_index = 0
    for filepath in dcm_files:
        # Skip non-DICOM files
        try:
            ds = pydicom.dcmread(str(filepath), stop_before_pixels=True, force=True)
        except Exception as e:
            print(f"  SKIP (not DICOM): {filepath.name}")
            continue
        
        # Validate it's a valid DICOM
        if not hasattr(ds, 'SOPInstanceUID'):
            print(f"  SKIP (no SOPInstanceUID): {filepath.name}")
            continue
        
        file_index += 1
        
        # Extract metadata (NO MUTATION)
        sop_instance_uid = str(ds.SOPInstanceUID)
        series_instance_uid = get_safe_value(ds, 'SeriesInstanceUID', 'UNKNOWN')
        study_instance_uid = get_safe_value(ds, 'StudyInstanceUID', 'UNKNOWN')
        instance_number = get_safe_value(ds, 'InstanceNumber')
        acquisition_time = get_safe_value(ds, 'AcquisitionTime')
        acquisition_datetime = get_safe_value(ds, 'AcquisitionDateTime')
        modality = get_safe_value(ds, 'Modality', 'UNKNOWN')
        sop_class_uid = get_safe_value(ds, 'SOPClassUID', 'UNKNOWN')
        number_of_frames = get_safe_value(ds, 'NumberOfFrames')
        
        is_multiframe = number_of_frames is not None and number_of_frames > 1
        
        # Track series
        series_uids.add(series_instance_uid)
        
        # Update modality flags
        modality_flags["modalities_found"].add(modality)
        if modality == 'US' and is_multiframe:
            modality_flags["us_multiframe_present"] = True
        if modality in ('CT', 'MR') and is_multiframe:
            modality_flags["ct_mr_cine_present"] = True
        if 'Encapsulated' in sop_class_uid or modality == 'DOC':
            modality_flags["encapsulated_pdf_present"] = True
        
        entry = BaselineEntry(
            file_index=file_index,
            relative_path=str(filepath.relative_to(source_dir)),
            sop_instance_uid=sop_instance_uid,
            series_instance_uid=series_instance_uid,
            study_instance_uid=study_instance_uid,
            instance_number=instance_number,
            acquisition_time=acquisition_time,
            acquisition_datetime=acquisition_datetime,
            modality=modality,
            sop_class_uid=sop_class_uid,
            number_of_frames=number_of_frames,
            is_multiframe=is_multiframe
        )
        entries.append(asdict(entry))
        
        print(f"  [{file_index:03d}] {modality:4s} IN={instance_number or 'N/A':10} SOP={sop_instance_uid[:30]}...")
    
    # Convert set to list for JSON serialization
    modality_flags["modalities_found"] = sorted(list(modality_flags["modalities_found"]))
    
    # Build manifest
    manifest = BaselineOrderManifest(
        manifest_id=manifest_id,
        capture_timestamp=capture_timestamp,
        source_directory=str(source_dir.absolute()),
        total_files=len(entries),
        total_series=len(series_uids),
        modality_flags=modality_flags,
        entries=entries,
        script_version="1.0.0"
    )
    
    # Serialize to JSON (sorted for determinism)
    manifest_dict = asdict(manifest)
    manifest_json = json.dumps(manifest_dict, indent=2, sort_keys=True)
    
    # Write manifest
    manifest_path = output_dir / "baseline_order_manifest.json"
    manifest_path.write_text(manifest_json)
    print(f"\n✓ Written: {manifest_path}")
    
    # Compute SHA-256
    manifest_hash = hashlib.sha256(manifest_json.encode('utf-8')).hexdigest()
    
    # Write hash file
    hash_path = output_dir / "baseline_order_manifest.sha256"
    hash_content = f"{manifest_hash}  baseline_order_manifest.json\n"
    hash_path.write_text(hash_content)
    print(f"✓ Written: {hash_path}")
    
    # Summary
    print("\n" + "="*60)
    print("GATE 1 — STEP 1 BASELINE CAPTURE COMPLETE")
    print("="*60)
    print(f"Manifest ID:    {manifest_id}")
    print(f"Timestamp:      {capture_timestamp}")
    print(f"Total Files:    {len(entries)}")
    print(f"Total Series:   {len(series_uids)}")
    print(f"Modalities:     {', '.join(modality_flags['modalities_found'])}")
    print(f"Multi-frame US: {modality_flags['us_multiframe_present']}")
    print(f"SHA-256:        {manifest_hash}")
    print("="*60)
    
    return manifest_hash


def main():
    """Main entry point."""
    script_dir = Path(__file__).parent
    source_dir = script_dir / "source_data" / "FOI_5015705699"
    output_dir = script_dir
    
    print("="*60)
    print("GATE 1 — STEP 1: BASELINE CAPTURE")
    print("="*60)
    print(f"Source: {source_dir}")
    print(f"Output: {output_dir}")
    print("="*60)
    print("\nScanning DICOM files...\n")
    
    if not source_dir.exists():
        print(f"ERROR: Source directory not found: {source_dir}")
        sys.exit(1)
    
    manifest_hash = capture_baseline(source_dir, output_dir)
    return manifest_hash


if __name__ == "__main__":
    main()
