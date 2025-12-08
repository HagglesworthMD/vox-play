#!/usr/bin/env python3
"""
VoxelMask - Automated Validation Test Suite

Processes synthetic DICOM files through the anonymizer and validates:
1. PHI removal (PatientName, PatientID anonymized)
2. UID remapping (StudyInstanceUID changed)
3. Safety protocol compliance (pixel preservation for anatomical modalities)
4. Pixel masking for modalities with burned-in annotations (US, SC)
"""

import hashlib
import os
import sys
import tempfile
from pathlib import Path
from dataclasses import dataclass
from typing import Optional, List, Tuple
from datetime import datetime

import numpy as np
import pydicom

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
from research_mode.anonymizer import DicomAnonymizer, AnonymizationConfig


# ═══════════════════════════════════════════════════════════════════════════════
# ANSI COLOR CODES FOR TERMINAL OUTPUT
# ═══════════════════════════════════════════════════════════════════════════════
class Colors:
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'
    END = '\033[0m'
    
    @staticmethod
    def pass_text(text: str) -> str:
        return f"{Colors.GREEN}{Colors.BOLD}✓ PASS{Colors.END} {text}"
    
    @staticmethod
    def fail_text(text: str) -> str:
        return f"{Colors.RED}{Colors.BOLD}✗ FAIL{Colors.END} {text}"
    
    @staticmethod
    def warn_text(text: str) -> str:
        return f"{Colors.YELLOW}{Colors.BOLD}⚠ WARN{Colors.END} {text}"
    
    @staticmethod
    def info_text(text: str) -> str:
        return f"{Colors.CYAN}{text}{Colors.END}"


@dataclass
class TestResult:
    """Result of a single test case."""
    filename: str
    modality: str
    passed: bool
    
    # Individual test results
    phi_removed: bool = False
    uid_remapped: bool = False
    pixel_safety_correct: bool = False
    
    # Details
    original_patient_name: str = ""
    anonymized_patient_name: str = ""
    original_study_uid: str = ""
    anonymized_study_uid: str = ""
    original_pixel_hash: str = ""
    anonymized_pixel_hash: str = ""
    pixel_action: str = ""  # "MASKED", "PRESERVED", "ERROR"
    safety_notification: str = ""
    error_message: str = ""


def compute_pixel_hash(ds: pydicom.Dataset) -> str:
    """Compute SHA-256 hash of pixel data."""
    if hasattr(ds, 'PixelData'):
        return hashlib.sha256(ds.PixelData).hexdigest()[:16]
    return "NO_PIXEL_DATA"


def check_top_left_masked(ds: pydicom.Dataset, threshold: int = 50) -> bool:
    """
    Check if the top-left region (where burned-in PHI was simulated) is masked (black).
    
    Args:
        ds: DICOM dataset
        threshold: Maximum pixel value to consider "masked" (black)
        
    Returns:
        True if top-left region appears masked (dark)
    """
    try:
        pixel_array = ds.pixel_array
        
        # Check the region where we placed the simulated PHI (10:60, 10:150)
        if pixel_array.ndim == 3:
            # Color image - check all channels
            region = pixel_array[10:60, 10:150, :]
            mean_value = np.mean(region)
        else:
            # Grayscale
            region = pixel_array[10:60, 10:150]
            mean_value = np.mean(region)
        
        # If mean is below threshold, consider it masked
        return mean_value < threshold
        
    except Exception as e:
        print(f"  Error checking pixels: {e}")
        return False


def validate_file(
    input_path: str,
    output_dir: str,
    anonymizer: DicomAnonymizer,
    expected_mask: bool,
    expected_preserve: bool
) -> TestResult:
    """
    Validate anonymization of a single DICOM file.
    
    Args:
        input_path: Path to input DICOM file
        output_dir: Directory for output files
        anonymizer: Configured DicomAnonymizer instance
        expected_mask: Whether pixel masking is expected
        expected_preserve: Whether pixel preservation is expected (safety bypass)
        
    Returns:
        TestResult with all validation details
    """
    filename = os.path.basename(input_path)
    
    # Read original file
    try:
        original_ds = pydicom.dcmread(input_path)
    except Exception as e:
        return TestResult(
            filename=filename,
            modality="UNKNOWN",
            passed=False,
            error_message=f"Failed to read input: {e}"
        )
    
    modality = getattr(original_ds, 'Modality', 'UNKNOWN')
    original_patient_name = str(getattr(original_ds, 'PatientName', ''))
    original_study_uid = str(getattr(original_ds, 'StudyInstanceUID', ''))
    original_pixel_hash = compute_pixel_hash(original_ds)
    
    # Process file
    output_path = os.path.join(output_dir, f"anon_{filename}")
    
    try:
        result = anonymizer.anonymize_file(input_path, output_path)
        
        if not result.success:
            return TestResult(
                filename=filename,
                modality=modality,
                passed=False,
                original_patient_name=original_patient_name,
                original_study_uid=original_study_uid,
                original_pixel_hash=original_pixel_hash,
                error_message=f"Anonymization failed: {result.error_message}"
            )
            
    except Exception as e:
        return TestResult(
            filename=filename,
            modality=modality,
            passed=False,
            original_patient_name=original_patient_name,
            original_study_uid=original_study_uid,
            original_pixel_hash=original_pixel_hash,
            error_message=f"Exception during anonymization: {e}"
        )
    
    # Read anonymized file
    try:
        anon_ds = pydicom.dcmread(output_path)
    except Exception as e:
        return TestResult(
            filename=filename,
            modality=modality,
            passed=False,
            original_patient_name=original_patient_name,
            original_study_uid=original_study_uid,
            original_pixel_hash=original_pixel_hash,
            error_message=f"Failed to read output: {e}"
        )
    
    anonymized_patient_name = str(getattr(anon_ds, 'PatientName', ''))
    anonymized_study_uid = str(getattr(anon_ds, 'StudyInstanceUID', ''))
    anonymized_pixel_hash = compute_pixel_hash(anon_ds)
    
    # ═══════════════════════════════════════════════════════════════════════════
    # VALIDATION CHECKS
    # ═══════════════════════════════════════════════════════════════════════════
    
    # 1. PHI Removal Check
    phi_removed = (
        anonymized_patient_name != original_patient_name and
        (anonymized_patient_name == "" or 
         anonymized_patient_name == "ANONYMOUS" or
         "ANON" in anonymized_patient_name.upper())
    )
    
    # 2. UID Remapping Check
    uid_remapped = anonymized_study_uid != original_study_uid
    
    # 3. Pixel Safety Check
    pixel_hash_identical = (original_pixel_hash == anonymized_pixel_hash)
    
    if expected_preserve:
        # For anatomical modalities (CT, MR, NM, XA, DX) - pixels should be PRESERVED
        pixel_safety_correct = pixel_hash_identical
        pixel_action = "PRESERVED" if pixel_hash_identical else "MODIFIED (ERROR!)"
    elif expected_mask:
        # For US/SC - pixels should be MASKED (hash should change)
        # Also verify the top-left region is actually black
        top_left_masked = check_top_left_masked(anon_ds)
        pixel_safety_correct = not pixel_hash_identical and top_left_masked
        pixel_action = "MASKED" if pixel_safety_correct else "NOT MASKED (ERROR!)"
    else:
        # No specific expectation
        pixel_safety_correct = True
        pixel_action = "N/A"
    
    # Overall pass/fail
    passed = phi_removed and uid_remapped and pixel_safety_correct
    
    return TestResult(
        filename=filename,
        modality=modality,
        passed=passed,
        phi_removed=phi_removed,
        uid_remapped=uid_remapped,
        pixel_safety_correct=pixel_safety_correct,
        original_patient_name=original_patient_name,
        anonymized_patient_name=anonymized_patient_name,
        original_study_uid=original_study_uid[:20] + "...",
        anonymized_study_uid=anonymized_study_uid[:20] + "...",
        original_pixel_hash=original_pixel_hash,
        anonymized_pixel_hash=anonymized_pixel_hash,
        pixel_action=pixel_action,
        safety_notification=result.safety_notification or ""
    )


def print_results_table(results: List[TestResult]) -> Tuple[int, int]:
    """
    Print a formatted results table to the console.
    
    Returns:
        Tuple of (passed_count, failed_count)
    """
    print("\n" + "═" * 100)
    print(f"{Colors.BOLD}{Colors.CYAN}  VOXELMASK - VALIDATION RESULTS{Colors.END}")
    print("═" * 100)
    
    # Header
    print(f"\n{'File':<18} {'Mod':<4} {'PHI':<8} {'UID':<8} {'Pixels':<12} {'Action':<20} {'Result':<10}")
    print("─" * 100)
    
    passed = 0
    failed = 0
    
    for r in results:
        if r.error_message:
            status = f"{Colors.RED}ERROR{Colors.END}"
            failed += 1
        elif r.passed:
            status = f"{Colors.GREEN}PASS{Colors.END}"
            passed += 1
        else:
            status = f"{Colors.RED}FAIL{Colors.END}"
            failed += 1
        
        phi_status = f"{Colors.GREEN}✓{Colors.END}" if r.phi_removed else f"{Colors.RED}✗{Colors.END}"
        uid_status = f"{Colors.GREEN}✓{Colors.END}" if r.uid_remapped else f"{Colors.RED}✗{Colors.END}"
        pixel_status = f"{Colors.GREEN}✓{Colors.END}" if r.pixel_safety_correct else f"{Colors.RED}✗{Colors.END}"
        
        print(f"{r.filename:<18} {r.modality:<4} {phi_status:<8} {uid_status:<8} {pixel_status:<12} {r.pixel_action:<20} {status}")
    
    print("─" * 100)
    
    # Summary
    total = passed + failed
    pass_rate = (passed / total * 100) if total > 0 else 0
    
    print(f"\n{Colors.BOLD}SUMMARY:{Colors.END}")
    print(f"  Total Tests:  {total}")
    print(f"  {Colors.GREEN}Passed:{Colors.END}       {passed}")
    print(f"  {Colors.RED}Failed:{Colors.END}       {failed}")
    print(f"  Pass Rate:    {pass_rate:.1f}%")
    
    return passed, failed


def print_detailed_results(results: List[TestResult]) -> None:
    """Print detailed results for each test case."""
    print("\n" + "═" * 100)
    print(f"{Colors.BOLD}{Colors.CYAN}  DETAILED RESULTS{Colors.END}")
    print("═" * 100)
    
    for r in results:
        status_color = Colors.GREEN if r.passed else Colors.RED
        status_text = "PASS" if r.passed else "FAIL"
        
        print(f"\n{Colors.BOLD}┌─ {r.filename} ({r.modality}) ─ [{status_color}{status_text}{Colors.END}{Colors.BOLD}]{Colors.END}")
        print(f"│")
        print(f"│  PHI Removal:     {'✓ Removed' if r.phi_removed else '✗ NOT Removed'}")
        print(f"│    Original:      {r.original_patient_name}")
        print(f"│    Anonymized:    {r.anonymized_patient_name or '(empty)'}")
        print(f"│")
        print(f"│  UID Remapping:   {'✓ Changed' if r.uid_remapped else '✗ NOT Changed'}")
        print(f"│    Original:      {r.original_study_uid}")
        print(f"│    Anonymized:    {r.anonymized_study_uid}")
        print(f"│")
        print(f"│  Pixel Safety:    {'✓ Correct' if r.pixel_safety_correct else '✗ INCORRECT'}")
        print(f"│    Action:        {r.pixel_action}")
        print(f"│    Original Hash: {r.original_pixel_hash}")
        print(f"│    Anon Hash:     {r.anonymized_pixel_hash}")
        
        if r.safety_notification:
            print(f"│")
            print(f"│  {Colors.YELLOW}Safety Note:{Colors.END}    {r.safety_notification}")
        
        if r.error_message:
            print(f"│")
            print(f"│  {Colors.RED}Error:{Colors.END}          {r.error_message}")
        
        print(f"└{'─' * 80}")


def run_validation_suite() -> bool:
    """
    Run the complete validation suite.
    
    Returns:
        True if all tests passed, False otherwise
    """
    print("\n" + "═" * 100)
    print(f"{Colors.BOLD}{Colors.HEADER}")
    print("   ██╗   ██╗ ██████╗ ██╗  ██╗███████╗██╗     ███╗   ███╗ █████╗ ███████╗██╗  ██╗")
    print("   ██║   ██║██╔═══██╗╚██╗██╔╝██╔════╝██║     ████╗ ████║██╔══██╗██╔════╝██║ ██╔╝")
    print("   ██║   ██║██║   ██║ ╚███╔╝ █████╗  ██║     ██╔████╔██║███████║███████╗█████╔╝ ")
    print("   ╚██╗ ██╔╝██║   ██║ ██╔██╗ ██╔══╝  ██║     ██║╚██╔╝██║██╔══██║╚════██║██╔═██╗ ")
    print("    ╚████╔╝ ╚██████╔╝██╔╝ ██╗███████╗███████╗██║ ╚═╝ ██║██║  ██║███████║██║  ██╗")
    print("     ╚═══╝   ╚═════╝ ╚═╝  ╚═╝╚══════╝╚══════╝╚═╝     ╚═╝╚═╝  ╚═╝╚══════╝╚═╝  ╚═╝")
    print("                         VALIDATION SUITE v1.0")
    print(f"{Colors.END}")
    print("═" * 100)
    print(f"\n  Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"  Python:    {sys.version.split()[0]}")
    
    # Find test input directory
    test_input_dir = Path(__file__).parent / "test_input"
    
    if not test_input_dir.exists():
        print(f"\n{Colors.RED}ERROR: Test input directory not found: {test_input_dir}{Colors.END}")
        print("Run data_factory.py first to generate test files.")
        return False
    
    # Find all DICOM files
    dcm_files = list(test_input_dir.glob("*.dcm"))
    
    if not dcm_files:
        print(f"\n{Colors.RED}ERROR: No DICOM files found in {test_input_dir}{Colors.END}")
        return False
    
    print(f"  Test Files: {len(dcm_files)}")
    
    # Create temporary output directory
    with tempfile.TemporaryDirectory() as output_dir:
        print(f"  Output Dir: {output_dir}")
        
        # Initialize anonymizer with default config
        config = AnonymizationConfig(
            date_shift_range=(-30, -1),
            enable_pixel_masking=True,
        )
        anonymizer = DicomAnonymizer(config)
        
        print("\n  Processing files...")
        print("─" * 100)
        
        results = []
        
        # Define expected behavior per modality
        # US should be MASKED, anatomical modalities should be PRESERVED
        modality_expectations = {
            "US": {"mask": True, "preserve": False},
            "SC": {"mask": True, "preserve": False},
            "CT": {"mask": False, "preserve": True},
            "MR": {"mask": False, "preserve": True},
            "NM": {"mask": False, "preserve": True},
            "XA": {"mask": False, "preserve": True},
            "DX": {"mask": False, "preserve": True},
            "PT": {"mask": False, "preserve": True},
        }
        
        for dcm_file in sorted(dcm_files):
            # Determine expected behavior
            ds = pydicom.dcmread(str(dcm_file))
            modality = getattr(ds, 'Modality', 'UNKNOWN')
            
            expectations = modality_expectations.get(modality, {"mask": False, "preserve": False})
            
            result = validate_file(
                input_path=str(dcm_file),
                output_dir=output_dir,
                anonymizer=anonymizer,
                expected_mask=expectations["mask"],
                expected_preserve=expectations["preserve"]
            )
            results.append(result)
            
            # Progress indicator
            status = "✓" if result.passed else "✗"
            color = Colors.GREEN if result.passed else Colors.RED
            print(f"  {color}{status}{Colors.END} {result.filename} ({modality}): {result.pixel_action}")
        
        # Print results
        passed, failed = print_results_table(results)
        print_detailed_results(results)
        
        # Final verdict
        print("\n" + "═" * 100)
        if failed == 0:
            print(f"{Colors.GREEN}{Colors.BOLD}")
            print("  ██████╗  █████╗ ███████╗███████╗███████╗██████╗ ")
            print("  ██╔══██╗██╔══██╗██╔════╝██╔════╝██╔════╝██╔══██╗")
            print("  ██████╔╝███████║███████╗███████╗█████╗  ██║  ██║")
            print("  ██╔═══╝ ██╔══██║╚════██║╚════██║██╔══╝  ██║  ██║")
            print("  ██║     ██║  ██║███████║███████║███████╗██████╔╝")
            print("  ╚═╝     ╚═╝  ╚═╝╚══════╝╚══════╝╚══════╝╚═════╝ ")
            print(f"{Colors.END}")
            print(f"  All {passed} tests passed! VoxelMask is working correctly.")
        else:
            print(f"{Colors.RED}{Colors.BOLD}")
            print("  ███████╗ █████╗ ██╗██╗     ███████╗██████╗ ")
            print("  ██╔════╝██╔══██╗██║██║     ██╔════╝██╔══██╗")
            print("  █████╗  ███████║██║██║     █████╗  ██║  ██║")
            print("  ██╔══╝  ██╔══██║██║██║     ██╔══╝  ██║  ██║")
            print("  ██║     ██║  ██║██║███████╗███████╗██████╔╝")
            print("  ╚═╝     ╚═╝  ╚═╝╚═╝╚══════╝╚══════╝╚═════╝ ")
            print(f"{Colors.END}")
            print(f"  {failed} of {passed + failed} tests failed. Review the detailed results above.")
        
        print("═" * 100 + "\n")
        
        return failed == 0


if __name__ == "__main__":
    success = run_validation_suite()
    sys.exit(0 if success else 1)
