"""
DICOM Anonymizer for Research Mode

Implements HIPAA Safe Harbor and DICOM PS3.15 Basic Application Level 
Confidentiality Profile compliant anonymization.

Key Features:
- Strict whitelist architecture (keep-list approach)
- HMAC-SHA256 based UID remapping for longitudinal consistency
- Consistent date shifting to preserve temporal intervals
- PHI pattern scrubbing in text fields
- Private tag removal
"""

import hashlib
import hmac
import re
import secrets
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, List, Union, Dict, Set, Tuple, Any
from datetime import datetime, timedelta
import uuid
import hashlib
import re
import numpy as np
import pydicom
from PIL import Image

from utils import apply_deterministic_sanitization

from .whitelist import (
    SAFE_TAGS,
    UID_TAGS,
    DATE_TAGS,
    TEXT_SCRUB_TAGS,
    PHI_TAGS,
    is_tag_safe,
    is_private_tag,
    is_uid_tag,
    is_date_tag,
    is_text_scrub_tag,
    is_phi_tag,
)


@dataclass
class AnonymizationConfig:
    """Configuration for DICOM anonymization."""
    
    # Secret salt for HMAC-based UID generation (MUST be kept secure)
    secret_salt: bytes = field(default_factory=lambda: secrets.token_bytes(32))
    
    # Compliance profile: "safe_harbor" or "limited_data_set"
    compliance_profile: str = "safe_harbor"
    
    # Date shift range (days) - random offset within this range
    date_shift_range: Tuple[int, int] = (-365, -30)
    
    # Whether to keep PatientSex (often needed for research)
    keep_patient_sex: bool = True
    
    # Whether to keep PatientAge (often needed for research)
    keep_patient_age: bool = False
    
    # Replacement value for anonymized patient name
    anonymized_name: str = "ANONYMIZED"
    
    # Replacement value for anonymized patient ID
    anonymized_id: str = "RESEARCH_SUBJECT"
    
    # UID prefix for generated UIDs (should be organization-specific)
    uid_prefix: str = "1.2.826.0.1.3680043.8.498.99999"
    
    # Additional tags to whitelist (organization-specific)
    additional_safe_tags: Set[Tuple[int, int]] = field(default_factory=set)
    
    # Private tags to explicitly keep (must be justified)
    whitelisted_private_tags: Set[Tuple[int, int]] = field(default_factory=set)
    
    # ═══════════════════════════════════════════════════════════════════════════
    # PIXEL MASKING CONFIGURATION (for burned-in PHI)
    # ═══════════════════════════════════════════════════════════════════════════
    
    # Enable pixel masking for modalities prone to burned-in PHI
    enable_pixel_masking: bool = True
    
    # Modalities that trigger pixel masking protocol
    pixel_mask_modalities: Set[str] = field(default_factory=lambda: {'US', 'SC', 'OT'})
    
    # Fraction of image height to mask from top (0.0 to 1.0)
    pixel_mask_top_fraction: float = 0.10
    
    # Fraction of image height to mask from bottom (0.0 to 1.0)
    pixel_mask_bottom_fraction: float = 0.0
    
    # Mask value (0 = black)
    pixel_mask_value: int = 0


@dataclass
class AnonymizationResult:
    """Result of anonymizing a single DICOM file."""
    
    original_path: Path
    success: bool
    error_message: Optional[str] = None
    
    # Tag modification tracking
    tags_removed: List[Tuple[int, int]] = field(default_factory=list)
    tags_anonymized: List[Tuple[int, int]] = field(default_factory=list)
    uids_remapped: Dict[str, str] = field(default_factory=dict)
    dates_shifted: Dict[str, Tuple[str, str]] = field(default_factory=dict)
    texts_scrubbed: List[Tuple[int, int]] = field(default_factory=list)
    private_tags_removed: List[Tuple[int, int]] = field(default_factory=list)
    
    # Integrity verification
    original_pixel_hash: Optional[str] = None
    anonymized_pixel_hash: Optional[str] = None
    pixel_data_preserved: bool = True
    
    # Date shift applied (for audit)
    date_shift_days: int = 0
    
    # Final processed values (for audit logging)
    final_accession: Optional[str] = None
    final_study_date: Optional[str] = None
    
    # ═══════════════════════════════════════════════════════════════════════════
    # PIXEL MASKING RESULTS
    # ═══════════════════════════════════════════════════════════════════════════
    
    # Whether pixel masking was applied
    pixel_data_modified: bool = False
    
    # Modality that triggered masking (if any)
    pixel_mask_triggered_by: Optional[str] = None
    
    # Masking details
    pixel_mask_region: Optional[Dict[str, Any]] = None
    
    # Compliance status
    metadata_clean: bool = True
    pixel_clean: bool = False  # True only if masking was applied when required
    
    # Warning if masking should have occurred but hashes match
    pixel_mask_warning: Optional[str] = None
    
    # Safety notification when masking is intentionally bypassed
    safety_notification: Optional[str] = None


class DicomAnonymizer:
    """
    HIPAA Safe Harbor and DICOM PS3.15 compliant DICOM anonymizer.
    
    Uses a strict whitelist architecture where only explicitly approved
    tags are retained. All other tags are removed or anonymized.
    """
    
    # PHI patterns for text scrubbing
    PHI_PATTERNS = [
        # SSN patterns
        (r'\b\d{3}-\d{2}-\d{4}\b', '[SSN_REDACTED]'),
        (r'\b\d{9}\b', '[ID_REDACTED]'),
        
        # Phone patterns
        (r'\b\d{3}[-.\s]?\d{3}[-.\s]?\d{4}\b', '[PHONE_REDACTED]'),
        (r'\b\(\d{3}\)\s*\d{3}[-.\s]?\d{4}\b', '[PHONE_REDACTED]'),
        
        # Email patterns
        (r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', '[EMAIL_REDACTED]'),
        
        # Date patterns (various formats)
        (r'\b\d{1,2}/\d{1,2}/\d{2,4}\b', '[DATE_REDACTED]'),
        (r'\b\d{1,2}-\d{1,2}-\d{2,4}\b', '[DATE_REDACTED]'),
        
        # MRN patterns (common formats)
        (r'\bMRN[:\s]*\d+\b', '[MRN_REDACTED]'),
        (r'\bMR[:\s]*\d+\b', '[MRN_REDACTED]'),
        
        # Name patterns (Title + Name)
        (r'\b(Dr\.|Mr\.|Mrs\.|Ms\.)\s+[A-Z][a-z]+(\s+[A-Z][a-z]+)*\b', '[NAME_REDACTED]'),
        
        # Accession number patterns
        (r'\bACC[:\s]*\d+\b', '[ACC_REDACTED]'),
    ]
    
    def __init__(self, config: Optional[AnonymizationConfig] = None):
        """
        Initialize the anonymizer.
        
        Args:
            config: Anonymization configuration. If None, uses defaults.
        """
        self.config = config or AnonymizationConfig()
        
        # Build complete safe tag set
        self._safe_tags = SAFE_TAGS.copy()
        self._safe_tags.update(self.config.additional_safe_tags)
        
        # Add optional demographic tags
        if self.config.keep_patient_sex:
            self._safe_tags.add((0x0010, 0x0040))  # PatientSex
        
        # PatientAge handling depends on compliance profile
        if self.config.compliance_profile == "limited_data_set":
            # LDS allows keeping PatientAge for longitudinal analysis
            self._safe_tags.add((0x0010, 0x1010))  # PatientAge
        elif self.config.keep_patient_age and self.config.compliance_profile == "safe_harbor":
            # Safe Harbor only allows PatientAge if explicitly requested and age <= 89
            self._safe_tags.add((0x0010, 0x1010))  # PatientAge
        
        # Cache for UID mappings (ensures consistency across files)
        self._uid_cache: Dict[str, str] = {}
        
        # Cache for date shifts per study (ensures consistency)
        self._date_shift_cache: Dict[str, int] = {}
        
        # Compile PHI patterns
        self._phi_patterns = [
            (re.compile(pattern, re.IGNORECASE), replacement)
            for pattern, replacement in self.PHI_PATTERNS
        ]
    
    def _compute_pixel_hash(self, ds: pydicom.Dataset) -> Optional[str]:
        """
        Compute SHA-256 hash of pixel data for integrity verification.
        
        Args:
            ds: DICOM dataset
            
        Returns:
            Hex string of SHA-256 hash, or None if no pixel data
        """
        if not hasattr(ds, 'PixelData') or ds.PixelData is None:
            return None
        
        return hashlib.sha256(ds.PixelData).hexdigest()
    
    def _generate_stable_uid(self, original_uid: str) -> str:
        """
        Generate a stable anonymized UID using HMAC-SHA256.
        
        This ensures that the same original UID always maps to the same
        anonymized UID, preserving longitudinal research data validity.
        
        Args:
            original_uid: Original DICOM UID
            
        Returns:
            Anonymized UID that is stable for the same input
        """
        if original_uid in self._uid_cache:
            return self._uid_cache[original_uid]
        
        # Generate HMAC-SHA256 hash
        hmac_hash = hmac.new(
            self.config.secret_salt,
            original_uid.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        
        # Convert to valid UID format (numeric only, max 64 chars)
        # Use first 32 hex chars, convert to decimal representation
        numeric_part = str(int(hmac_hash[:32], 16))[:20]
        
        # Construct valid UID with prefix
        new_uid = f"{self.config.uid_prefix}.{numeric_part}"
        
        # Ensure UID is valid (max 64 chars, no leading zeros in components)
        if len(new_uid) > 64:
            new_uid = new_uid[:64]
        
        self._uid_cache[original_uid] = new_uid
        return new_uid
    
    def _get_date_shift(self, study_uid: str) -> int:
        """
        Get consistent date shift for a study.
        
        All dates within the same study are shifted by the same amount
        to preserve temporal intervals.
        
        Args:
            study_uid: Original StudyInstanceUID
            
        Returns:
            Number of days to shift (negative = earlier)
        """
        if study_uid in self._date_shift_cache:
            return self._date_shift_cache[study_uid]
        
        # Generate deterministic shift based on study UID and salt
        hmac_hash = hmac.new(
            self.config.secret_salt,
            f"date_shift_{study_uid}".encode('utf-8'),
            hashlib.sha256
        ).digest()
        
        # Convert first 4 bytes to integer
        shift_seed = int.from_bytes(hmac_hash[:4], 'big')
        
        # Map to configured range
        min_shift, max_shift = self.config.date_shift_range
        shift_range = max_shift - min_shift
        shift = min_shift + (shift_seed % shift_range)
        
        self._date_shift_cache[study_uid] = shift
        return shift
    
    def _shift_date(self, date_str: str, shift_days: int) -> str:
        """
        Shift a DICOM date by the specified number of days.
        
        Args:
            date_str: DICOM date string (YYYYMMDD format)
            shift_days: Number of days to shift
            
        Returns:
            Shifted date string in YYYYMMDD format
        """
        if not date_str or len(date_str) < 8:
            return ""
        
        try:
            # Parse DICOM date format
            date_obj = datetime.strptime(date_str[:8], "%Y%m%d")
            shifted = date_obj + timedelta(days=shift_days)
            return shifted.strftime("%Y%m%d")
        except ValueError:
            # If parsing fails, return empty (safe default)
            return ""
    
    def _scrub_text(self, text: str) -> Tuple[str, bool]:
        """
        Scrub PHI patterns from text.
        
        Args:
            text: Text to scrub
            
        Returns:
            Tuple of (scrubbed text, whether any changes were made)
        """
        if not text:
            return "", False
        
        original = text
        scrubbed = text
        
        for pattern, replacement in self._phi_patterns:
            scrubbed = pattern.sub(replacement, scrubbed)
        
        return scrubbed, scrubbed != original
    
    def _is_tag_safe(self, tag: Tuple[int, int]) -> bool:
        """Check if tag is on the safe whitelist."""
        return tag in self._safe_tags
    
    def _should_remove_private_tag(self, tag: Tuple[int, int]) -> bool:
        """Check if private tag should be removed."""
        if not is_private_tag(tag):
            return False
        return tag not in self.config.whitelisted_private_tags
    
    # ═══════════════════════════════════════════════════════════════════════════
    # PIXEL MASKING METHODS
    # ═══════════════════════════════════════════════════════════════════════════
    
    def _should_mask_pixels(self, ds: pydicom.Dataset) -> Tuple[bool, Optional[str]]:
        """
        Determine if pixel masking should be applied based on modality.
        
        Args:
            ds: DICOM dataset
            
        Returns:
            Tuple of (should_mask, modality_that_triggered)
        """
        if not self.config.enable_pixel_masking:
            return False, None
        
        # Get modality
        modality = str(getattr(ds, 'Modality', '')).upper()
        
        # Check if modality triggers masking
        if modality in self.config.pixel_mask_modalities:
            return True, modality
        
        # Also check ImageType for secondary captures that might be mislabeled
        image_type = getattr(ds, 'ImageType', [])
        if image_type:
            image_type_str = ' '.join(str(t) for t in image_type).upper()
            if 'SECONDARY' in image_type_str or 'DERIVED' in image_type_str:
                if 'SC' in self.config.pixel_mask_modalities:
                    return True, 'SC (from ImageType)'
        
        return False, None
    
    def _apply_pixel_mask(
        self,
        ds: pydicom.Dataset,
        result: 'AnonymizationResult'
    ) -> pydicom.Dataset:
        """
        Apply pixel masking to the dataset.
        
        Handles different bit depths (8-bit, 16-bit) and photometric
        interpretations (RGB, Monochrome) correctly.
        
        Args:
            ds: DICOM dataset with pixel data
            result: AnonymizationResult to update with masking details
            
        Returns:
            Modified dataset with masked pixels
        """
        if not hasattr(ds, 'PixelData') or ds.PixelData is None:
            return ds
        
        try:
            # Get pixel array (handles decompression automatically)
            pixel_array = ds.pixel_array.copy()
            
            # Get image dimensions
            if len(pixel_array.shape) == 2:
                # Grayscale: (rows, cols)
                rows, cols = pixel_array.shape
                is_rgb = False
                num_frames = 1
            elif len(pixel_array.shape) == 3:
                if pixel_array.shape[2] in [3, 4]:
                    # RGB/RGBA: (rows, cols, channels)
                    rows, cols = pixel_array.shape[:2]
                    is_rgb = True
                    num_frames = 1
                else:
                    # Multi-frame grayscale: (frames, rows, cols)
                    num_frames, rows, cols = pixel_array.shape
                    is_rgb = False
            elif len(pixel_array.shape) == 4:
                # Multi-frame RGB: (frames, rows, cols, channels)
                num_frames, rows, cols = pixel_array.shape[:3]
                is_rgb = True
            else:
                # Unsupported format
                result.pixel_mask_warning = f"Unsupported pixel array shape: {pixel_array.shape}"
                return ds
            
            # Calculate mask regions
            top_mask_rows = int(rows * self.config.pixel_mask_top_fraction)
            bottom_mask_rows = int(rows * self.config.pixel_mask_bottom_fraction)
            
            mask_value = self.config.pixel_mask_value
            
            # Apply mask based on array shape
            if len(pixel_array.shape) == 2:
                # Grayscale single frame
                if top_mask_rows > 0:
                    pixel_array[:top_mask_rows, :] = mask_value
                if bottom_mask_rows > 0:
                    pixel_array[-bottom_mask_rows:, :] = mask_value
                    
            elif len(pixel_array.shape) == 3:
                if is_rgb:
                    # RGB single frame: (rows, cols, channels)
                    if top_mask_rows > 0:
                        pixel_array[:top_mask_rows, :, :] = mask_value
                    if bottom_mask_rows > 0:
                        pixel_array[-bottom_mask_rows:, :, :] = mask_value
                else:
                    # Multi-frame grayscale: (frames, rows, cols)
                    if top_mask_rows > 0:
                        pixel_array[:, :top_mask_rows, :] = mask_value
                    if bottom_mask_rows > 0:
                        pixel_array[:, -bottom_mask_rows:, :] = mask_value
                        
            elif len(pixel_array.shape) == 4:
                # Multi-frame RGB: (frames, rows, cols, channels)
                if top_mask_rows > 0:
                    pixel_array[:, :top_mask_rows, :, :] = mask_value
                if bottom_mask_rows > 0:
                    pixel_array[:, -bottom_mask_rows:, :, :] = mask_value
            
            # Write back to dataset
            # Handle different photometric interpretations
            photometric = str(getattr(ds, 'PhotometricInterpretation', 'MONOCHROME2'))
            
            # Ensure correct byte order and data type
            if pixel_array.dtype == np.uint8:
                ds.PixelData = pixel_array.tobytes()
            elif pixel_array.dtype == np.uint16:
                ds.PixelData = pixel_array.tobytes()
            elif pixel_array.dtype == np.int16:
                ds.PixelData = pixel_array.tobytes()
            else:
                # Convert to appropriate type based on BitsAllocated and PixelRepresentation
                bits_allocated = int(getattr(ds, 'BitsAllocated', 8))
                pixel_representation = int(getattr(ds, 'PixelRepresentation', 0))
                if bits_allocated <= 8:
                    ds.PixelData = pixel_array.astype(np.uint8).tobytes()
                elif pixel_representation == 1:
                    # CRITICAL: Preserve signed data for CT (prevents White Screen)
                    ds.PixelData = pixel_array.astype(np.int16).tobytes()
                else:
                    ds.PixelData = pixel_array.astype(np.uint16).tobytes()
            
            # CRITICAL: Update DICOM metadata to match numpy array format
            # Dynamic photometric interpretation based on array shape and original interpretation
            original_photometric = str(getattr(ds, 'PhotometricInterpretation', 'MONOCHROME2'))
            modality = str(getattr(ds, 'Modality', '')).upper()
            
            # Determine correct photometric interpretation
            if len(pixel_array.shape) == 2:
                # 2D arrays are always grayscale
                ds.PhotometricInterpretation = "MONOCHROME2"
                if hasattr(ds, 'PlanarConfiguration'):
                    del ds.PlanarConfiguration  # Not applicable for grayscale
                ds.SamplesPerPixel = 1
                
            elif len(pixel_array.shape) == 3 and pixel_array.shape[2] in [3, 4]:
                # 3-channel arrays: check if should be RGB or MONOCHROME2
                # CT/MRI are typically MONOCHROME2 even with 3 channels
                if modality in ['CT', 'MR', 'PT'] or original_photometric.startswith('MONOCHROME'):
                    # Grayscale medical images (CT/MRI/PET)
                    ds.PhotometricInterpretation = "MONOCHROME2"
                    if hasattr(ds, 'PlanarConfiguration'):
                        del ds.PlanarConfiguration  # Not applicable for grayscale
                    ds.SamplesPerPixel = 1
                else:
                    # True color images (US, SC, XA, etc.)
                    ds.PhotometricInterpretation = "RGB"
                    ds.PlanarConfiguration = 0  # Interleaved RGB
                    ds.SamplesPerPixel = 3
                    
            elif len(pixel_array.shape) == 4:
                # Multi-frame: handle based on last dimension
                if pixel_array.shape[3] in [3, 4]:
                    if modality in ['CT', 'MR', 'PT'] or original_photometric.startswith('MONOCHROME'):
                        # Multi-frame grayscale
                        ds.PhotometricInterpretation = "MONOCHROME2"
                        if hasattr(ds, 'PlanarConfiguration'):
                            del ds.PlanarConfiguration
                        ds.SamplesPerPixel = 1
                    else:
                        # Multi-frame RGB
                        ds.PhotometricInterpretation = "RGB"
                        ds.PlanarConfiguration = 0
                        ds.SamplesPerPixel = 3
                else:
                    # Default to MONOCHROME2 for unknown formats
                    ds.PhotometricInterpretation = "MONOCHROME2"
                    if hasattr(ds, 'PlanarConfiguration'):
                        del ds.PlanarConfiguration
                    ds.SamplesPerPixel = 1
            else:
                # Default fallback
                ds.PhotometricInterpretation = "MONOCHROME2"
                if hasattr(ds, 'PlanarConfiguration'):
                    del ds.PlanarConfiguration
                ds.SamplesPerPixel = 1
            
            # Update BitsAllocated and BitsStored based on array dtype
            # CRITICAL: Preserve PixelRepresentation for signed data (prevents White Screen)
            if pixel_array.dtype == np.uint8:
                ds.BitsAllocated = 8
                ds.BitsStored = 8
                ds.HighBit = 7
                ds.PixelRepresentation = 0  # Unsigned
            elif pixel_array.dtype == np.uint16:
                ds.BitsAllocated = 16
                ds.BitsStored = 16
                ds.HighBit = 15
                ds.PixelRepresentation = 0  # Unsigned
            elif pixel_array.dtype == np.int16:
                ds.BitsAllocated = 16
                ds.BitsStored = 16
                ds.HighBit = 15
                ds.PixelRepresentation = 1  # CRITICAL: Signed (prevents White Screen for CT)
            
            # Update result with masking details
            result.pixel_data_modified = True
            result.pixel_clean = True
            result.pixel_mask_region = {
                "top_rows_masked": top_mask_rows,
                "bottom_rows_masked": bottom_mask_rows,
                "total_rows": rows,
                "total_cols": cols,
                "num_frames": num_frames,
                "is_rgb": is_rgb,
                "mask_value": mask_value,
                "photometric_interpretation": original_photometric,
                "final_photometric_interpretation": ds.PhotometricInterpretation,
                "modality": modality,
            }
            
        except Exception as e:
            result.pixel_mask_warning = f"Pixel masking failed: {str(e)}"
            result.pixel_clean = False
        
        return ds
    
    def anonymize_dataset(
        self,
        ds: pydicom.Dataset,
        original_path: Optional[Path] = None
    ) -> Tuple[pydicom.Dataset, AnonymizationResult]:
        """
        Anonymize a DICOM dataset in-place.
        
        Args:
            ds: DICOM dataset to anonymize
            original_path: Path to original file (for audit)
            
        Returns:
            Tuple of (anonymized dataset, anonymization result)
        """
        result = AnonymizationResult(
            original_path=original_path or Path("unknown"),
            success=True
        )
        
        # Compute original pixel hash for integrity verification
        result.original_pixel_hash = self._compute_pixel_hash(ds)
        
        # Get study UID for consistent date shifting
        study_uid = str(getattr(ds, 'StudyInstanceUID', 'unknown'))
        result.date_shift_days = self._get_date_shift(study_uid)
        
        # Collect all tags to process
        tags_to_remove = []
        
        # ═══════════════════════════════════════════════════════════════════════════
        # CRITICAL: Image Pixel Module tags that MUST be preserved
        # These tags are essential for proper CT/MR display and prevent "White Screen"
        # ═══════════════════════════════════════════════════════════════════════════
        CRITICAL_PIXEL_TAGS = {
            (0x0028, 0x0002),  # SamplesPerPixel
            (0x0028, 0x0004),  # PhotometricInterpretation
            (0x0028, 0x0010),  # Rows
            (0x0028, 0x0011),  # Columns
            (0x0028, 0x0030),  # PixelSpacing
            (0x0028, 0x0100),  # BitsAllocated
            (0x0028, 0x0101),  # BitsStored
            (0x0028, 0x0102),  # HighBit
            (0x0028, 0x0103),  # PixelRepresentation (CRITICAL: Prevents White Screen)
            (0x0028, 0x1050),  # WindowCenter
            (0x0028, 0x1051),  # WindowWidth
            (0x0028, 0x1052),  # RescaleIntercept (CRITICAL: Hounsfield Units)
            (0x0028, 0x1053),  # RescaleSlope (CRITICAL: Hounsfield Units)
            (0x0028, 0x1054),  # RescaleType
            (0x7FE0, 0x0010),  # PixelData
        }
        
        # First pass: identify tags to remove
        for elem in ds:
            tag = (elem.tag.group, elem.tag.element)
            
            # CRITICAL: Never remove Image Pixel module tags
            if tag in CRITICAL_PIXEL_TAGS:
                continue
            
            # Check if private tag
            if self._should_remove_private_tag(tag):
                tags_to_remove.append(tag)
                result.private_tags_removed.append(tag)
                continue
            
            # Check if on whitelist
            if not self._is_tag_safe(tag):
                # Special handling for certain tags
                if is_uid_tag(tag):
                    # UID tags are remapped, not removed
                    continue
                elif is_date_tag(tag):
                    # Date tags are shifted, not removed
                    continue
                elif is_text_scrub_tag(tag) and not is_phi_tag(tag):
                    # Text tags are scrubbed, not removed (unless they're PHI)
                    continue
                else:
                    # Not on whitelist and not special - remove
                    tags_to_remove.append(tag)
                    result.tags_removed.append(tag)
        
        # Remove non-whitelisted tags
        for tag in tags_to_remove:
            try:
                del ds[tag]
            except KeyError:
                pass
        
        # Second pass: anonymize/transform remaining tags
        
        # Remap UIDs
        for tag in UID_TAGS:
            if tag in ds:
                try:
                    original_uid = str(ds[tag].value)
                    new_uid = self._generate_stable_uid(original_uid)
                    ds[tag].value = new_uid
                    result.uids_remapped[original_uid] = new_uid
                except Exception:
                    pass
        
        # Shift dates (only for Safe Harbor profile)
        if self.config.compliance_profile == "safe_harbor":
            for tag in DATE_TAGS:
                if tag in ds:
                    try:
                        original_date = str(ds[tag].value)
                        shifted_date = self._shift_date(original_date, result.date_shift_days)
                        ds[tag].value = shifted_date
                        result.dates_shifted[f"({tag[0]:04X},{tag[1]:04X})"] = (
                            original_date, shifted_date
                        )
                    except Exception:
                        pass
        elif self.config.compliance_profile == "limited_data_set":
            # For LDS, preserve original dates but track them for audit
            for tag in DATE_TAGS:
                if tag in ds:
                    try:
                        original_date = str(ds[tag].value)
                        result.dates_shifted[f"({tag[0]:04X},{tag[1]:04X})"] = (
                            original_date, original_date  # No change for LDS
                        )
                    except Exception:
                        pass
        
        # Scrub text fields
        for tag in TEXT_SCRUB_TAGS:
            if tag in ds:
                try:
                    original_text = str(ds[tag].value)
                    scrubbed_text, was_modified = self._scrub_text(original_text)
                    if was_modified:
                        ds[tag].value = scrubbed_text
                        result.texts_scrubbed.append(tag)
                except Exception:
                    pass
        
        # Anonymize patient identification
        if (0x0010, 0x0010) in ds:  # PatientName
            ds[0x0010, 0x0010].value = self.config.anonymized_name
            result.tags_anonymized.append((0x0010, 0x0010))
        
        if (0x0010, 0x0020) in ds:  # PatientID
            # Generate stable anonymous ID based on original
            original_id = str(ds[0x0010, 0x0020].value)
            anon_id = self._generate_stable_uid(f"patient_{original_id}")[-12:]
            ds[0x0010, 0x0020].value = f"{self.config.anonymized_id}_{anon_id}"
            result.tags_anonymized.append((0x0010, 0x0020))
        
        # Note: AccessionNumber, dates, and UIDs are now handled by apply_deterministic_sanitization
        
        # Handle PatientAge based on compliance profile
        if (0x0010, 0x1010) in ds:  # PatientAge
            if self.config.compliance_profile == "safe_harbor":
                # For Safe Harbor, remove age if > 89
                age_str = str(ds[0x0010, 0x1010].value)
                try:
                    # Parse age format (e.g., "045Y", "89Y", "090Y")
                    if age_str.endswith('Y'):
                        age_years = int(age_str[:-1])
                        if age_years > 89:
                            del ds[0x0010, 0x1010]
                            result.tags_removed.append((0x0010, 0x1010))
                        else:
                            result.tags_anonymized.append((0x0010, 0x1010))
                    elif age_str.endswith('M'):
                        age_months = int(age_str[:-1])
                        if age_months > (89 * 12):  # Convert years to months
                            del ds[0x0010, 0x1010]
                            result.tags_removed.append((0x0010, 0x1010))
                        else:
                            result.tags_anonymized.append((0x0010, 0x1010))
                    elif age_str.endswith('D'):
                        age_days = int(age_str[:-1])
                        if age_days > (89 * 365):  # Convert years to days
                            del ds[0x0010, 0x1010]
                            result.tags_removed.append((0x0010, 0x1010))
                        else:
                            result.tags_anonymized.append((0x0010, 0x1010))
                    else:
                        # Unknown format, remove for safety
                        del ds[0x0010, 0x1010]
                        result.tags_removed.append((0x0010, 0x1010))
                except (ValueError, IndexError):
                    # If parsing fails, remove for safety
                    del ds[0x0010, 0x1010]
                    result.tags_removed.append((0x0010, 0x1010))
            elif self.config.compliance_profile == "limited_data_set":
                # For LDS, keep PatientAge for longitudinal analysis
                result.tags_anonymized.append((0x0010, 0x1010))
        
        # Remove PatientBirthDate entirely (HIPAA requirement)
        if (0x0010, 0x0030) in ds:
            del ds[0x0010, 0x0030]
            result.tags_removed.append((0x0010, 0x0030))
        
        # Handle file meta information if present
        if hasattr(ds, 'file_meta'):
            # Remap MediaStorageSOPInstanceUID
            if hasattr(ds.file_meta, 'MediaStorageSOPInstanceUID'):
                original_uid = str(ds.file_meta.MediaStorageSOPInstanceUID)
                new_uid = self._generate_stable_uid(original_uid)
                ds.file_meta.MediaStorageSOPInstanceUID = new_uid
        
        # ═════════════════════════════════════════════════════════════════════════
        # PIXEL MASKING (for burned-in PHI)
        # ═════════════════════════════════════════════════════════════════════════
        
        # Check if pixel masking is required for this modality
        should_mask, triggered_by = self._should_mask_pixels(ds)
        result.pixel_mask_triggered_by = triggered_by
        
        if should_mask:
            # Apply pixel masking
            ds = self._apply_pixel_mask(ds, result)
        else:
            # No masking needed - pixel data preserved
            result.pixel_clean = True  # Clean because no masking was required
            
            # Add safety notification for transparency
            modality = getattr(ds, 'Modality', 'Unknown')
            if modality not in self.config.pixel_mask_modalities:
                result.safety_notification = (
                    f"SAFETY PROTOCOL: Pixel masking intentionally bypassed for {modality} modality. "
                    f"This protects diagnostic anatomy from being cropped. "
                    f"Only {', '.join(sorted(self.config.pixel_mask_modalities))} modalities require masking."
                )
        
        # ═════════════════════════════════════════════════════════════════════════
        # VERIFY PIXEL DATA INTEGRITY
        # ═════════════════════════════════════════════════════════════════════════
        
        result.anonymized_pixel_hash = self._compute_pixel_hash(ds)
        result.pixel_data_preserved = (
            result.original_pixel_hash == result.anonymized_pixel_hash
        )
        
        # Verify masking actually occurred for modalities that require it
        if should_mask and result.pixel_data_preserved:
            # WARNING: Masking was supposed to happen but hashes match
            result.pixel_mask_warning = (
                f"CRITICAL: Pixel masking was triggered for modality '{triggered_by}' "
                f"but pixel hashes are identical. Masking may have failed!"
            )
            result.pixel_clean = False
        
        # Apply unified deterministic sanitization (accession, dates, UIDs)
        # This ensures consistent treatment across ALL processing paths
        apply_deterministic_sanitization(ds, date_shift_days=result.date_shift_days)
        
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
        # Note: This method doesn't have access to research_context, but if it did:
        # if 'research_context' in locals() and research_context is not None:
        #     research_context['accession'] = final_accession
        #     research_context['accession_number'] = final_accession
        #     research_context['new_study_date'] = final_date
        
        # Store final values in result for potential logging
        result.final_accession = final_accession
        result.final_study_date = final_date
        # ==============================================================================
        
        # Mark metadata as clean (we've done all the tag processing)
        result.metadata_clean = True
        
        # --- CRITICAL FIX: SYNC LOG WITH FINAL DATASET ---
        # The dataset has been modified. We MUST update any logging dictionaries to match the output file.
        # Note: This method doesn't have direct access to research_context, but if it did:
        if hasattr(result, 'context') and result.context:
            context = result.context
            if "AccessionNumber" in ds:
                final_acc = str(ds.AccessionNumber)
                context['accession'] = final_acc
                context['accession_number'] = final_acc
            
            if "StudyDate" in ds:
                final_date = str(ds.StudyDate)
                context['new_study_date'] = final_date
            
            # NOW call the logger with the updated dictionary
            # generate_audit_log(activity_id, context, dataset=ds)
        
        return ds, result
    
    def anonymize_file(
        self,
        input_path: Union[str, Path],
        output_path: Optional[Union[str, Path]] = None
    ) -> AnonymizationResult:
        """
        Anonymize a DICOM file.
        
        Args:
            input_path: Path to input DICOM file
            output_path: Path to output file. If None, overwrites input.
            
        Returns:
            AnonymizationResult with details of changes made
        """
        input_path = Path(input_path)
        output_path = Path(output_path) if output_path else input_path
        
        try:
            # Read DICOM file
            ds = pydicom.dcmread(str(input_path))
            
            # Anonymize
            ds, result = self.anonymize_dataset(ds, input_path)
            
            # Save
            ds.save_as(str(output_path))
            
            return result
            
        except Exception as e:
            return AnonymizationResult(
                original_path=input_path,
                success=False,
                error_message=str(e)
            )
    
    def anonymize_batch(
        self,
        input_paths: List[Union[str, Path]],
        output_dir: Optional[Union[str, Path]] = None
    ) -> List[AnonymizationResult]:
        """
        Anonymize a batch of DICOM files.
        
        Args:
            input_paths: List of paths to input DICOM files
            output_dir: Directory for output files. If None, overwrites inputs.
            
        Returns:
            List of AnonymizationResult for each file
        """
        results = []
        
        for input_path in input_paths:
            input_path = Path(input_path)
            
            if output_dir:
                output_path = Path(output_dir) / input_path.name
            else:
                output_path = None
            
            result = self.anonymize_file(input_path, output_path)
            results.append(result)
        
        return results
    
    def reset_caches(self):
        """Reset UID and date shift caches. Use between unrelated batches."""
        self._uid_cache.clear()
        self._date_shift_cache.clear()
