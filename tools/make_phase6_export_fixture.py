#!/usr/bin/env python3
"""
Phase 6.1 HTML Export Viewer — Synthetic Fixture Generator
=========================================================

Creates a synthetic multi-series DICOM set from a single input DICOM.

Purpose:
- Validate export ZIP HTML viewer (viewer_index.json + PNG previews) without real data.
- Validate: series grouping, instance navigation, OT/SC hiding toggle, and image path mapping.

Governance:
- Synthetic only; no patient data required.
- Output is for internal testing/pilot artefacts.
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import List, Tuple

import pydicom
from pydicom.uid import generate_uid


def _ensure_str(v):
    return "" if v is None else str(v)


def clone_series(
    ds: pydicom.Dataset,
    series_number: int,
    series_desc: str,
    modality: str,
    count: int,
) -> List[pydicom.Dataset]:
    """Clone a dataset into a new series with `count` instances."""
    import copy
    
    series_uid = generate_uid()
    out: List[pydicom.Dataset] = []

    for i in range(1, count + 1):
        d = copy.deepcopy(ds)  # Deep copy to ensure truly independent instances

        # Series identity
        d.SeriesInstanceUID = series_uid
        d.SeriesNumber = series_number
        d.SeriesDescription = series_desc
        d.Modality = modality

        # Instance identity
        d.SOPInstanceUID = generate_uid()
        d.InstanceNumber = i

        # Make filenames deterministic-ish
        # Optional: tweak AcquisitionTime/ContentTime for ordering clarity
        if "AcquisitionTime" in d:
            d.AcquisitionTime = f"{90000 + i:06d}"  # 090001, 090002...
        if "ContentTime" in d:
            d.ContentTime = f"{90000 + i:06d}"

        out.append(d)

    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True, help="Path to a source synthetic DICOM (single file).")
    ap.add_argument("--output", required=True, help="Output folder to write generated DICOM files.")
    ap.add_argument("--us_a", type=int, default=7, help="Count of instances in US series A.")
    ap.add_argument("--us_b", type=int, default=5, help="Count of instances in US series B.")
    ap.add_argument("--ot", type=int, default=3, help="Count of instances in OT series (document-like).")
    args = ap.parse_args()

    in_path = Path(args.input).expanduser().resolve()
    out_dir = Path(args.output).expanduser().resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    ds = pydicom.dcmread(str(in_path), force=True)

    # Keep study identity stable across all series
    # but ensure it exists.
    if not getattr(ds, "StudyInstanceUID", None):
        ds.StudyInstanceUID = generate_uid()

    # Optional: sanitize "patient-ish" tags in case the synthetic file has anything odd
    # (Still synthetic, but keep it clean.)
    ds.PatientName = "VM^SYNTHETIC"
    ds.PatientID = "VM-SYNTHETIC"
    ds.AccessionNumber = "VM-ACC-TEST"
    ds.StudyDescription = "VoxelMask Synthetic Phase6 Fixture"
    ds.StudyDate = "20251217"

    # Build series
    us_a = clone_series(ds, series_number=1, series_desc="US Series A (synthetic)", modality="US", count=args.us_a)
    us_b = clone_series(ds, series_number=2, series_desc="US Series B (synthetic)", modality="US", count=args.us_b)

    # OT "document-like" series (still uses same pixel data; that's okay for viewer logic)
    ot_s = clone_series(ds, series_number=99, series_desc="OT Documents (synthetic)", modality="OT", count=args.ot)

    all_sets: List[Tuple[str, List[pydicom.Dataset]]] = [
        ("US_S001", us_a),
        ("US_S002", us_b),
        ("OT_S099", ot_s),
    ]

    total = 0
    for folder_name, dsets in all_sets:
        series_dir = out_dir / folder_name
        series_dir.mkdir(parents=True, exist_ok=True)

        for d in dsets:
            inst = int(getattr(d, "InstanceNumber", 0) or 0)
            fname = f"IMG_{inst:04d}.dcm"
            d.save_as(str(series_dir / fname))
            total += 1

    print("✅ Synthetic fixture generated")
    print(f"Input:  {in_path}")
    print(f"Output: {out_dir}")
    print(f"Total instances: {total}")
    print("Folders:")
    for folder_name, dsets in all_sets:
        print(f"  - {folder_name}: {len(dsets)}")


if __name__ == "__main__":
    main()
