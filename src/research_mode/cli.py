#!/usr/bin/env python3
"""
Research Mode DICOM Anonymization CLI

Command-line interface for HIPAA Safe Harbor and DICOM PS3.15 compliant
anonymization of DICOM files for commercial research and ML data preparation.

Usage:
    python -m research_mode.cli input.dcm -o output.dcm
    python -m research_mode.cli input_dir/ -o output_dir/ --report compliance.json
"""

import argparse
import json
import os
import secrets
import sys
from pathlib import Path
from typing import List, Optional

from .anonymizer import DicomAnonymizer, AnonymizationConfig
from .audit import ComplianceReportGenerator


def find_dicom_files(path: Path) -> List[Path]:
    """Find all DICOM files in a directory."""
    if path.is_file():
        return [path]
    
    dicom_files = []
    for ext in ['*.dcm', '*.DCM', '*.dicom', '*.DICOM']:
        dicom_files.extend(path.glob(f'**/{ext}'))
    
    # Also check files without extension (common for DICOM)
    for file_path in path.glob('**/*'):
        if file_path.is_file() and not file_path.suffix:
            # Quick check for DICOM magic bytes
            try:
                with open(file_path, 'rb') as f:
                    f.seek(128)
                    if f.read(4) == b'DICM':
                        dicom_files.append(file_path)
            except Exception:
                pass
    
    return sorted(set(dicom_files))


def main():
    parser = argparse.ArgumentParser(
        description='HIPAA Safe Harbor compliant DICOM anonymization for research',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Anonymize a single file
  python -m research_mode.cli input.dcm -o output.dcm

  # Anonymize a directory
  python -m research_mode.cli input_dir/ -o output_dir/

  # Generate compliance report
  python -m research_mode.cli input_dir/ -o output_dir/ --report compliance_report.json

  # Use custom salt file for reproducible UIDs
  python -m research_mode.cli input.dcm -o output.dcm --salt-file my_salt.key
        """
    )
    
    parser.add_argument(
        'input',
        type=Path,
        help='Input DICOM file or directory'
    )
    
    parser.add_argument(
        '-o', '--output',
        type=Path,
        required=True,
        help='Output DICOM file or directory'
    )
    
    parser.add_argument(
        '--report',
        type=Path,
        help='Path to save compliance report JSON'
    )
    
    parser.add_argument(
        '--salt-file',
        type=Path,
        help='File containing secret salt for reproducible UID generation'
    )
    
    parser.add_argument(
        '--generate-salt',
        type=Path,
        help='Generate a new salt file and save to this path'
    )
    
    parser.add_argument(
        '--date-shift-min',
        type=int,
        default=-365,
        help='Minimum date shift in days (default: -365)'
    )
    
    parser.add_argument(
        '--date-shift-max',
        type=int,
        default=-30,
        help='Maximum date shift in days (default: -30)'
    )
    
    parser.add_argument(
        '--keep-patient-sex',
        action='store_true',
        default=True,
        help='Keep PatientSex tag (default: True)'
    )
    
    parser.add_argument(
        '--keep-patient-age',
        action='store_true',
        default=False,
        help='Keep PatientAge tag (default: False)'
    )
    
    parser.add_argument(
        '-v', '--verbose',
        action='store_true',
        help='Verbose output'
    )
    
    args = parser.parse_args()
    
    # Generate salt if requested
    if args.generate_salt:
        salt = secrets.token_bytes(32)
        args.generate_salt.parent.mkdir(parents=True, exist_ok=True)
        with open(args.generate_salt, 'wb') as f:
            f.write(salt)
        print(f"Generated salt file: {args.generate_salt}")
        if not args.input.exists():
            return 0
    
    # Validate input
    if not args.input.exists():
        print(f"Error: Input path does not exist: {args.input}", file=sys.stderr)
        return 1
    
    # Load or generate salt
    if args.salt_file:
        if not args.salt_file.exists():
            print(f"Error: Salt file does not exist: {args.salt_file}", file=sys.stderr)
            return 1
        with open(args.salt_file, 'rb') as f:
            secret_salt = f.read()
    else:
        secret_salt = secrets.token_bytes(32)
        if args.verbose:
            print("Warning: Using random salt. UIDs will not be reproducible.")
    
    # Configure anonymizer
    config = AnonymizationConfig(
        secret_salt=secret_salt,
        date_shift_range=(args.date_shift_min, args.date_shift_max),
        keep_patient_sex=args.keep_patient_sex,
        keep_patient_age=args.keep_patient_age,
    )
    
    anonymizer = DicomAnonymizer(config)
    report_generator = ComplianceReportGenerator()
    
    # Find DICOM files
    input_files = find_dicom_files(args.input)
    
    if not input_files:
        print(f"Error: No DICOM files found in: {args.input}", file=sys.stderr)
        return 1
    
    if args.verbose:
        print(f"Found {len(input_files)} DICOM file(s)")
    
    # Prepare output
    if args.input.is_file():
        # Single file
        args.output.parent.mkdir(parents=True, exist_ok=True)
        output_paths = [args.output]
    else:
        # Directory
        args.output.mkdir(parents=True, exist_ok=True)
        output_paths = [
            args.output / f.relative_to(args.input)
            for f in input_files
        ]
    
    # Process files
    success_count = 0
    fail_count = 0
    
    for input_path, output_path in zip(input_files, output_paths):
        if args.verbose:
            print(f"Processing: {input_path}")
        
        # Ensure output directory exists
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Anonymize
        result = anonymizer.anonymize_file(input_path, output_path)
        report_generator.add_result(result, output_path.name)
        
        if result.success:
            success_count += 1
            if args.verbose:
                print(f"  ✓ Anonymized: {output_path}")
                print(f"    Tags removed: {len(result.tags_removed)}")
                print(f"    UIDs remapped: {len(result.uids_remapped)}")
                print(f"    Dates shifted: {result.date_shift_days} days")
        else:
            fail_count += 1
            print(f"  ✗ Failed: {result.error_message}", file=sys.stderr)
    
    # Generate report
    if args.report:
        config_dict = {
            "date_shift_range": list(config.date_shift_range),
            "keep_patient_sex": config.keep_patient_sex,
            "keep_patient_age": config.keep_patient_age,
            "uid_prefix": config.uid_prefix,
        }
        report = report_generator.save_report(args.report, config_dict)
        if args.verbose:
            print(f"\nCompliance report saved: {args.report}")
    
    # Summary
    print(f"\nProcessing complete:")
    print(f"  Successful: {success_count}")
    print(f"  Failed: {fail_count}")
    
    if args.report:
        print(f"  Report: {args.report}")
    
    return 0 if fail_count == 0 else 1


if __name__ == '__main__':
    sys.exit(main())
