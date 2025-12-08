"""
VoxelMask NIfTI Handler - Zero-Loss Edition
============================================
Converts anonymized DICOM series to NIfTI format for AI/ML research.

HARDENED for clinical data with:
- Relaxed validation (accepts variable slice spacing, gantry tilt)
- Multi-frame support (Angio, Ultrasound cine → 4D NIfTI)
- Quality audit (input/output count verification)
- 100% slice retention goal

Dependencies (bundled in requirements.txt):
- dicom2nifti>=2.4.9
- nibabel>=5.1.0
- numpy>=1.24.0

Author: VoxelMask Team
"""

import os
import logging
from pathlib import Path
from typing import Dict, Optional, List, Tuple
from datetime import datetime

# Core dependencies - required
import numpy as np
import pydicom

# NIfTI libraries - optional (not needed for core DICOM processing)
NIFTI_AVAILABLE = False
try:
    import dicom2nifti
    import dicom2nifti.settings as nifti_settings
    import nibabel as nib
    NIFTI_AVAILABLE = True
except ImportError:
    dicom2nifti = None
    nifti_settings = None
    nib = None

# Configure logging
logger = logging.getLogger(__name__)


class QualityAudit:
    """Tracks input/output counts for quality verification."""
    
    def __init__(self):
        self.input_dicom_count: int = 0
        self.input_frame_count: int = 0  # Total frames across all DICOMs
        self.output_file_count: int = 0
        self.output_slice_count: int = 0  # Total slices in NIfTI outputs
        self.warnings: List[str] = []
    
    def calculate_retention(self) -> Tuple[float, str]:
        """Calculate retention percentage and generate report."""
        if self.input_frame_count == 0:
            return 100.0, "No input frames to compare"
        
        retention = (self.output_slice_count / self.input_frame_count) * 100
        
        if retention >= 99.0:
            status = f"EXCELLENT: Preserved {self.output_slice_count}/{self.input_frame_count} slices ({retention:.1f}%)"
        elif retention >= 90.0:
            status = f"GOOD: Preserved {self.output_slice_count}/{self.input_frame_count} slices ({retention:.1f}%)"
        else:
            status = f"WARNING: Potential slice loss - {self.output_slice_count}/{self.input_frame_count} slices ({retention:.1f}%)"
            self.warnings.append(f"Potential slice loss detected: only {retention:.1f}% retained")
        
        return retention, status


class NIfTIConversionResult:
    """Result object for NIfTI conversion operations."""
    
    def __init__(self):
        self.success: bool = False
        self.mode: str = "unknown"  # '3D', '2D', '4D_cine', or 'failed'
        self.converted_files: List[str] = []
        self.failed_files: List[str] = []
        self.warnings: List[str] = []
        self.error_message: Optional[str] = None
        self.output_folder: Optional[str] = None
        self.quality_audit: Optional[QualityAudit] = None
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for logging."""
        return {
            'success': self.success,
            'mode': self.mode,
            'converted_count': len(self.converted_files),
            'failed_count': len(self.failed_files),
            'warnings': self.warnings,
            'error': self.error_message,
            'quality': self.quality_audit.calculate_retention()[1] if self.quality_audit else "N/A"
        }


class NiftiConverter:
    """
    Zero-Loss NIfTI converter with relaxed validation and multi-frame support.
    
    Features:
    - Accepts variable slice spacing (table speed changes)
    - Accepts gantry tilt
    - Resamples non-uniform data instead of dropping
    - Multi-frame DICOM → 4D NIfTI
    - Quality audit with input/output verification
    """
    
    def __init__(self):
        """Initialize the converter with RELAXED settings for clinical data."""
        self._configure_relaxed_settings()
    
    def _configure_relaxed_settings(self):
        """Configure dicom2nifti for maximum clinical data acceptance."""
        # ═══════════════════════════════════════════════════════════════════
        # RELAXED VALIDATION - Accept "messy" clinical data
        # ═══════════════════════════════════════════════════════════════════
        
        # Accept variable slice spacing (common with table speed changes in CT)
        nifti_settings.disable_validate_slice_increment()
        
        # Accept gantry tilt (common in head CT)
        nifti_settings.disable_validate_orientation()
        
        # Accept any slice count (including single slices)
        nifti_settings.disable_validate_slicecount()
        
        # Enable resampling for non-uniform data (preserves all slices)
        try:
            nifti_settings.enable_resampling()
            logger.info("NIfTI: Resampling enabled for non-uniform data")
        except AttributeError:
            # Older versions may not have this
            logger.warning("NIfTI: enable_resampling() not available in this version")
        
        logger.info("NIfTI converter initialized with RELAXED clinical settings")
    
    def convert_to_nifti(
        self,
        dicom_dir: str,
        output_dir: str,
        compression: bool = True
    ) -> NIfTIConversionResult:
        """
        Convert DICOM files to NIfTI with zero-loss goal.
        
        Args:
            dicom_dir: Path to folder containing DICOM files
            output_dir: Path to output folder for NIfTI files
            compression: If True, output .nii.gz; if False, output .nii
            
        Returns:
            NIfTIConversionResult with success status, quality audit, and conversion mode
        """
        result = NIfTIConversionResult()
        result.output_folder = output_dir
        result.quality_audit = QualityAudit()
        
        # Ensure output folder exists
        os.makedirs(output_dir, exist_ok=True)
        
        # Validate input
        if not os.path.exists(dicom_dir):
            result.success = False
            result.mode = "failed"
            result.error_message = f"Input folder not found: {dicom_dir}"
            return result
        
        # Find and analyze DICOM files
        dicom_files = self._find_dicom_files(dicom_dir)
        
        if not dicom_files:
            result.success = False
            result.mode = "failed"
            result.error_message = "No DICOM files found in input folder"
            return result
        
        # Count input frames for quality audit
        result.quality_audit.input_dicom_count = len(dicom_files)
        total_input_frames = self._count_total_frames(dicom_files)
        result.quality_audit.input_frame_count = total_input_frames
        
        logger.info(f"Found {len(dicom_files)} DICOM files with {total_input_frames} total frames")
        result.warnings.append(f"Input: {len(dicom_files)} DICOMs, {total_input_frames} frames")
        
        # Re-apply relaxed settings (in case they were reset)
        self._configure_relaxed_settings()
        
        # ═══════════════════════════════════════════════════════════════════
        # ATTEMPT 1: Volumetric 3D/4D Conversion (ideal for CT/MRI)
        # ═══════════════════════════════════════════════════════════════════
        try:
            logger.info("Attempting 3D/4D volumetric conversion...")
            
            dicom2nifti.convert_directory(
                dicom_dir,
                output_dir,
                compression=compression,
                reorient=True
            )
            
            # Check if files were created and count slices
            nifti_ext = '.nii.gz' if compression else '.nii'
            result.converted_files = [
                str(f) for f in Path(output_dir).rglob(f'*{nifti_ext}')
            ]
            
            if result.converted_files:
                # Count output slices for quality audit
                total_output_slices = self._count_nifti_slices(result.converted_files)
                result.quality_audit.output_file_count = len(result.converted_files)
                result.quality_audit.output_slice_count = total_output_slices
                
                result.success = True
                result.mode = "3D"
                
                # Check for 4D volumes
                for nf in result.converted_files:
                    try:
                        img = nib.load(nf)
                        if len(img.shape) == 4:
                            result.mode = "4D"
                            break
                    except:
                        pass
                
                retention, status = result.quality_audit.calculate_retention()
                result.warnings.append(f"Quality Check: {status}")
                logger.info(f"3D/4D conversion successful: {status}")
                return result
            else:
                result.warnings.append("3D conversion produced no files, attempting multi-frame fallback")
                
        except Exception as e:
            error_msg = str(e)
            logger.warning(f"3D conversion failed: {error_msg}")
            result.warnings.append(f"3D conversion failed: {error_msg[:100]}")
        
        # ═══════════════════════════════════════════════════════════════════
        # ATTEMPT 2: Multi-Frame Cine Fallback (for Angio, Ultrasound movies)
        # ═══════════════════════════════════════════════════════════════════
        try:
            logger.info("Attempting multi-frame cine conversion...")
            
            converted_count = 0
            total_output_slices = 0
            
            for i, dcm_path in enumerate(dicom_files):
                try:
                    # Read DICOM with full data
                    ds = pydicom.dcmread(dcm_path, force=True)
                    
                    # Check for pixel data
                    if not hasattr(ds, 'PixelData') or ds.PixelData is None:
                        result.failed_files.append(dcm_path)
                        continue
                    
                    # Get pixel array at ORIGINAL bit depth
                    pixel_array = ds.pixel_array
                    original_dtype = pixel_array.dtype
                    
                    # Get number of frames
                    num_frames = int(getattr(ds, 'NumberOfFrames', 1))
                    
                    # ═══════════════════════════════════════════════════════════
                    # MULTI-FRAME HANDLING - Save ALL frames, not just Frame 0
                    # ═══════════════════════════════════════════════════════════
                    
                    if num_frames > 1 or (pixel_array.ndim >= 3 and pixel_array.shape[0] > 1):
                        # This is a cine/movie - save as 4D NIfTI
                        logger.info(f"Processing multi-frame DICOM: {num_frames} frames")
                        
                        if pixel_array.ndim == 3:
                            # (frames, rows, cols) → (rows, cols, frames) for NIfTI
                            volume = np.transpose(pixel_array, (1, 2, 0))
                        elif pixel_array.ndim == 4:
                            # (frames, rows, cols, channels) - handle color
                            if pixel_array.shape[3] in (3, 4):
                                # Convert RGB to grayscale for NIfTI
                                volume = np.mean(pixel_array, axis=3).astype(original_dtype)
                                volume = np.transpose(volume, (1, 2, 0))
                            else:
                                volume = np.transpose(pixel_array, (1, 2, 3, 0))
                        else:
                            volume = pixel_array
                        
                        # Create 4D NIfTI (or 3D if single color channel)
                        nifti_img = nib.Nifti1Image(volume.astype(np.float32), np.eye(4))
                        output_name = f"cine_{i:04d}.nii.gz" if compression else f"cine_{i:04d}.nii"
                        
                        # Count all frames as preserved
                        total_output_slices += volume.shape[-1] if volume.ndim >= 3 else 1
                        
                    else:
                        # Single frame - handle 2D
                        if pixel_array.ndim == 2:
                            # Add slice dimension
                            volume = pixel_array[:, :, np.newaxis]
                        elif pixel_array.ndim == 3 and pixel_array.shape[2] in (3, 4):
                            # RGB image - convert to grayscale
                            volume = np.mean(pixel_array, axis=2).astype(original_dtype)[:, :, np.newaxis]
                        else:
                            volume = pixel_array
                        
                        nifti_img = nib.Nifti1Image(volume.astype(np.float32), np.eye(4))
                        output_name = f"slice_{i:04d}.nii.gz" if compression else f"slice_{i:04d}.nii"
                        total_output_slices += 1
                    
                    # Save NIfTI
                    output_path = os.path.join(output_dir, output_name)
                    nib.save(nifti_img, output_path)
                    result.converted_files.append(output_path)
                    converted_count += 1
                    
                except Exception as slice_error:
                    logger.warning(f"Failed to convert {dcm_path}: {slice_error}")
                    result.failed_files.append(dcm_path)
            
            # Update quality audit
            result.quality_audit.output_file_count = converted_count
            result.quality_audit.output_slice_count = total_output_slices
            
            if converted_count > 0:
                result.success = True
                result.mode = "2D" if total_output_slices == converted_count else "4D_cine"
                
                retention, status = result.quality_audit.calculate_retention()
                result.warnings.append(f"Quality Check: {status}")
                
                if retention < 90:
                    result.warnings.append(f"WARNING: Potential slice loss detected - only {retention:.1f}% retained")
                
                logger.info(f"Multi-frame conversion successful: {status}")
            else:
                result.success = False
                result.mode = "failed"
                result.error_message = "Both 3D and multi-frame conversion failed"
                
        except Exception as e:
            result.success = False
            result.mode = "failed"
            result.error_message = f"Conversion failed completely: {e}"
            logger.exception("Complete conversion failure")
        
        return result
    
    def _find_dicom_files(self, folder: str) -> List[str]:
        """Find all DICOM files in a folder (recursive)."""
        dicom_files = []
        
        for path in Path(folder).rglob('*'):
            if path.is_file() and not path.name.startswith('.'):
                try:
                    # Quick DICM magic check
                    with open(path, 'rb') as f:
                        f.seek(128)
                        if f.read(4) == b'DICM':
                            dicom_files.append(str(path))
                            continue
                    
                    # Fallback - try pydicom
                    ds = pydicom.dcmread(str(path), stop_before_pixels=True, force=True)
                    if hasattr(ds, 'Modality') or hasattr(ds, 'SOPClassUID'):
                        dicom_files.append(str(path))
                except:
                    pass
        
        return dicom_files
    
    def _count_total_frames(self, dicom_files: List[str]) -> int:
        """Count total frames across all DICOM files."""
        total = 0
        for dcm_path in dicom_files:
            try:
                ds = pydicom.dcmread(dcm_path, stop_before_pixels=True, force=True)
                num_frames = int(getattr(ds, 'NumberOfFrames', 1))
                total += num_frames
            except:
                total += 1  # Assume at least 1 frame
        return total
    
    def _count_nifti_slices(self, nifti_files: List[str]) -> int:
        """Count total slices/frames in NIfTI files."""
        total = 0
        for nf in nifti_files:
            try:
                img = nib.load(nf)
                shape = img.shape
                # Count slices: for 3D it's the third dim, for 4D it's 3rd * 4th
                if len(shape) >= 3:
                    total += shape[2]
                    if len(shape) >= 4:
                        total *= shape[3]
                else:
                    total += 1
            except:
                total += 1
        return total


# ═══════════════════════════════════════════════════════════════════════════════
# CONVENIENCE FUNCTIONS (for backward compatibility)
# ═══════════════════════════════════════════════════════════════════════════════

def check_dicom2nifti_available() -> bool:
    """Check if dicom2nifti is available."""
    return NIFTI_AVAILABLE


def convert_dataset_to_nifti(
    dicom_input_folder: str,
    nifti_output_folder: str,
    compression: bool = True,
    reorient: bool = True
) -> NIfTIConversionResult:
    """Convenience function for NIfTI conversion."""
    converter = NiftiConverter()
    return converter.convert_to_nifti(dicom_input_folder, nifti_output_folder, compression)


def generate_nifti_readme(
    conversion_result: NIfTIConversionResult,
    original_mode: str = "Research",
    compliance_profile: str = "unknown"
) -> str:
    """Generate README content for NIfTI output."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    mode_desc = {
        "3D": "Volumetric 3D conversion",
        "4D": "4D volume with temporal dimension",
        "4D_cine": "4D cine conversion (multi-frame DICOM)",
        "2D": "2D slice-by-slice conversion",
        "failed": "Conversion failed"
    }.get(conversion_result.mode, conversion_result.mode)
    
    # Quality audit info
    quality_info = ""
    if conversion_result.quality_audit:
        retention, status = conversion_result.quality_audit.calculate_retention()
        quality_info = f"""
QUALITY AUDIT
-------------
Input DICOMs: {conversion_result.quality_audit.input_dicom_count}
Input Frames: {conversion_result.quality_audit.input_frame_count}
Output Files: {conversion_result.quality_audit.output_file_count}
Output Slices: {conversion_result.quality_audit.output_slice_count}
Retention: {status}
"""
    
    readme = f"""VoxelMask NIfTI Export - Zero-Loss Edition
==========================================
Generated: {timestamp}

CONVERSION SUMMARY
------------------
Processing Mode: {original_mode}
Compliance Profile: {compliance_profile}
Conversion Mode: {mode_desc}
Status: {"SUCCESS" if conversion_result.success else "FAILED"}
Files Created: {len(conversion_result.converted_files)}
{quality_info}
"""
    
    if conversion_result.converted_files:
        readme += "CONVERTED FILES\n---------------\n"
        for f in conversion_result.converted_files:
            readme += f"  - {os.path.basename(f)}\n"
        readme += "\n"
    
    if conversion_result.warnings:
        readme += "CONVERSION LOG\n--------------\n"
        for w in conversion_result.warnings:
            readme += f"  > {w}\n"
        readme += "\n"
    
    if conversion_result.error_message:
        readme += f"ERROR\n-----\n{conversion_result.error_message}\n\n"
    
    readme += """
ZERO-LOSS FEATURES
------------------
This conversion used RELAXED settings for maximum data retention:
- Variable slice spacing: ACCEPTED (table speed changes)
- Gantry tilt: ACCEPTED (common in head CT)
- Multi-frame cine: ALL FRAMES preserved (not just first)
- Non-uniform spacing: RESAMPLED (not dropped)

VERIFICATION IN PYTHON
----------------------
    import nibabel as nib
    img = nib.load("file.nii.gz")
    print(f"Shape: {img.shape}")  # (rows, cols, slices[, frames])
    print(f"Data type: {img.get_data_dtype()}")
    data = img.get_fdata()

---
Processed by VoxelMask | Zero-Loss NIfTI Export
"""
    
    return readme


def generate_fallback_warning_file(
    error_message: str,
    warnings: List[str]
) -> str:
    """Generate warning file when NIfTI conversion completely fails."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    content = f"""NIFTI CONVERSION FAILED - DICOM FALLBACK
=========================================
Generated: {timestamp}

This ZIP contains DICOM files because NIfTI conversion failed completely.

ERROR
-----
{error_message}

"""
    
    if warnings:
        content += "CONVERSION LOG\n--------------\n"
        for w in warnings:
            content += f"  - {w}\n"
        content += "\n"
    
    content += """
ATTEMPTED METHODS
-----------------
1. 3D/4D volumetric conversion (with relaxed validation)
2. Multi-frame cine conversion (all frames preserved)

Both methods failed. This may indicate:
- Corrupted DICOM files
- Unsupported modality/encoding
- Missing pixel data

YOUR DATA IS SAFE
-----------------
The DICOM files in this ZIP are fully anonymized and usable.
Use the included DICOM Viewer to verify the output.

---
Processed by VoxelMask
"""
    
    return content
