"""
VoxelMask File Handling Tests
=============================
Tests for ZIP file extraction and DICOM file detection.

Verifies:
1. ZIP files are correctly extracted
2. Nested folder structures are handled
3. DICOM files are identified by magic bytes (not just extension)
4. Non-DICOM files (txt, html, etc.) are ignored
5. Processing produces valid anonymized output

Run with: pytest tests/test_file_handling.py -v
"""

import os
import sys
import tempfile
import zipfile

import pytest
import pydicom


# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from compliance_engine import DicomComplianceManager


def extract_dicoms_from_zip(zip_path: str, output_dir: str) -> list:
    """
    Extract and identify DICOM files from a ZIP archive.
    
    This mirrors the logic used in app.py for ZIP handling.
    
    Args:
        zip_path: Path to the ZIP file
        output_dir: Directory to extract files to
        
    Returns:
        list: List of paths to extracted DICOM files
    """
    dicom_files = []
    
    # Extensions to skip (non-DICOM files)
    skip_extensions = (
        '.html', '.htm', '.css', '.js', '.txt', '.md', 
        '.json', '.xml', '.pdf', '.doc', '.docx'
    )
    
    with zipfile.ZipFile(zip_path, 'r') as zf:
        zf.extractall(output_dir)
    
    # Walk through extracted files and identify DICOMs
    for root, dirs, files in os.walk(output_dir):
        for file in files:
            # Skip hidden files and known non-DICOM extensions
            if file.startswith('.') or file.startswith('__'):
                continue
            if file.lower().endswith(skip_extensions):
                continue
            
            file_path = os.path.join(root, file)
            
            # Check for DICOM magic bytes
            try:
                with open(file_path, 'rb') as f:
                    header = f.read(132)
                    if len(header) >= 132 and header[128:132] == b'DICM':
                        dicom_files.append(file_path)
            except Exception:
                pass
    
    return dicom_files


def process_dicom_files(dicom_paths: list, profile: str = 'us_research_safe_harbor') -> list:
    """
    Process a list of DICOM files through the compliance engine.
    
    Args:
        dicom_paths: List of paths to DICOM files
        profile: Compliance profile to use
        
    Returns:
        list: List of (processed_dataset, info) tuples
    """
    results = []
    manager = DicomComplianceManager()
    
    for path in dicom_paths:
        ds = pydicom.dcmread(path, force=True)
        
        # Add fallback for missing TransferSyntaxUID
        if not hasattr(ds, 'file_meta') or not hasattr(ds.file_meta, 'TransferSyntaxUID'):
            if not hasattr(ds, 'file_meta'):
                ds.file_meta = pydicom.Dataset()
            ds.file_meta.TransferSyntaxUID = pydicom.uid.ImplicitVRLittleEndian
        
        processed_ds, info = manager.process_dataset(ds, profile)
        results.append((processed_ds, info))
    
    return results


class TestZipExtraction:
    """Tests for ZIP file extraction and DICOM detection."""
    
    def test_zip_extracts_all_files(self, nested_zip_structure):
        """
        Assert: All files in the ZIP are extracted.
        """
        zip_info = nested_zip_structure
        
        with tempfile.TemporaryDirectory() as extract_dir:
            with zipfile.ZipFile(zip_info['zip_path'], 'r') as zf:
                zf.extractall(extract_dir)
            
            # Check folder structure exists
            assert os.path.exists(os.path.join(extract_dir, 'folder_a'))
            assert os.path.exists(os.path.join(extract_dir, 'folder_b', 'subfolder'))
            
            # Check files exist
            assert os.path.exists(os.path.join(extract_dir, 'folder_a', 'image1.dcm'))
            assert os.path.exists(os.path.join(extract_dir, 'folder_b', 'subfolder', 'image2.dcm'))
            assert os.path.exists(os.path.join(extract_dir, 'random_file.txt'))
    
    def test_dicom_detection_finds_all_dicoms(self, nested_zip_structure):
        """
        Assert: All DICOM files are detected and non-DICOM files are ignored.
        """
        zip_info = nested_zip_structure
        
        with tempfile.TemporaryDirectory() as extract_dir:
            dicom_files = extract_dicoms_from_zip(zip_info['zip_path'], extract_dir)
            
            # Should find exactly 2 DICOM files
            assert len(dicom_files) == 2, \
                f"Expected 2 DICOM files, found {len(dicom_files)}"
            
            # Verify they are the expected files
            filenames = [os.path.basename(f) for f in dicom_files]
            assert 'image1.dcm' in filenames
            assert 'image2.dcm' in filenames
    
    def test_text_files_ignored(self, nested_zip_structure):
        """
        Assert: Text files are not included in DICOM extraction.
        """
        zip_info = nested_zip_structure
        
        with tempfile.TemporaryDirectory() as extract_dir:
            dicom_files = extract_dicoms_from_zip(zip_info['zip_path'], extract_dir)
            
            # No text files should be in the results
            for dicom_path in dicom_files:
                assert not dicom_path.endswith('.txt'), \
                    f"Text file incorrectly included: {dicom_path}"
    
    def test_dicom_magic_bytes_validation(self, nested_zip_structure):
        """
        Assert: Files are validated by DICOM magic bytes, not just extension.
        """
        zip_info = nested_zip_structure
        
        with tempfile.TemporaryDirectory() as extract_dir:
            dicom_files = extract_dicoms_from_zip(zip_info['zip_path'], extract_dir)
            
            # Each detected file should have valid DICOM magic bytes
            for dicom_path in dicom_files:
                with open(dicom_path, 'rb') as f:
                    header = f.read(132)
                    assert header[128:132] == b'DICM', \
                        f"File {dicom_path} lacks DICOM magic bytes"


class TestZipProcessing:
    """Tests for processing DICOMs extracted from ZIPs."""
    
    def test_all_extracted_dicoms_can_be_processed(self, nested_zip_structure):
        """
        Assert: All extracted DICOMs can be successfully processed.
        """
        zip_info = nested_zip_structure
        
        with tempfile.TemporaryDirectory() as extract_dir:
            dicom_files = extract_dicoms_from_zip(zip_info['zip_path'], extract_dir)
            
            # Should not raise any exceptions
            results = process_dicom_files(dicom_files)
            
            assert len(results) == 2, \
                f"Expected 2 processed results, got {len(results)}"
            
            # Each result should have a processed dataset
            for processed_ds, info in results:
                assert processed_ds is not None
                assert info['profile'] == 'us_research_safe_harbor'
    
    def test_processed_dicoms_are_anonymized(self, nested_zip_structure):
        """
        Assert: PatientName is removed from all processed DICOMs.
        """
        zip_info = nested_zip_structure
        
        with tempfile.TemporaryDirectory() as extract_dir:
            dicom_files = extract_dicoms_from_zip(zip_info['zip_path'], extract_dir)
            results = process_dicom_files(dicom_files)
            
            for processed_ds, info in results:
                # PatientName should be removed or anonymized
                if hasattr(processed_ds, 'PatientName'):
                    name = str(processed_ds.PatientName)
                    assert name not in ['Patient^One', 'Patient^Two'], \
                        f"Original patient name should be removed: {name}"
    
    def test_processed_dicoms_have_shifted_dates(self, nested_zip_structure):
        """
        Assert: StudyDate is shifted in all processed DICOMs.
        """
        zip_info = nested_zip_structure
        
        with tempfile.TemporaryDirectory() as extract_dir:
            dicom_files = extract_dicoms_from_zip(zip_info['zip_path'], extract_dir)
            
            # Read original dates before processing
            original_dates = {}
            for path in dicom_files:
                ds = pydicom.dcmread(path)
                original_dates[path] = str(ds.StudyDate)
            
            results = process_dicom_files(dicom_files)
            
            # Verify dates were shifted
            for i, (processed_ds, info) in enumerate(results):
                original_date = original_dates[dicom_files[i]]
                processed_date = str(processed_ds.StudyDate)
                
                assert processed_date != original_date, \
                    f"Date should be shifted: {original_date} -> {processed_date}"
                
                # Verify shift is recorded
                assert info['date_shift_days'] is not None
                assert info['date_shift_days'] < 0
    
    def test_processed_dicoms_have_compliance_flags(self, nested_zip_structure):
        """
        Assert: All processed DICOMs have PatientIdentityRemoved set.
        """
        zip_info = nested_zip_structure
        
        with tempfile.TemporaryDirectory() as extract_dir:
            dicom_files = extract_dicoms_from_zip(zip_info['zip_path'], extract_dir)
            results = process_dicom_files(dicom_files)
            
            for processed_ds, info in results:
                assert hasattr(processed_ds, 'PatientIdentityRemoved')
                assert str(processed_ds.PatientIdentityRemoved) == 'YES'
                
                assert hasattr(processed_ds, 'DeidentificationMethod')
                method = str(processed_ds.DeidentificationMethod)
                assert 'HIPAA' in method or 'VOXELMASK' in method


class TestNestedFolderStructure:
    """Tests for handling deeply nested folder structures."""
    
    def test_subfolder_dicoms_are_found(self, nested_zip_structure):
        """
        Assert: DICOMs in nested subfolders are correctly discovered.
        """
        zip_info = nested_zip_structure
        
        with tempfile.TemporaryDirectory() as extract_dir:
            dicom_files = extract_dicoms_from_zip(zip_info['zip_path'], extract_dir)
            
            # Check that image2.dcm from subfolder is found
            paths_str = ' '.join(dicom_files)
            assert 'subfolder' in paths_str, \
                "DICOM from nested subfolder should be found"
    
    def test_folder_structure_preserved_in_extraction(self, nested_zip_structure):
        """
        Assert: Original folder structure is preserved during extraction.
        """
        zip_info = nested_zip_structure
        
        with tempfile.TemporaryDirectory() as extract_dir:
            with zipfile.ZipFile(zip_info['zip_path'], 'r') as zf:
                zf.extractall(extract_dir)
            
            # Original structure should be preserved
            expected_path = os.path.join(extract_dir, 'folder_b', 'subfolder', 'image2.dcm')
            assert os.path.exists(expected_path), \
                f"Nested path should exist: {expected_path}"
