"""
Pixel Invariant Enforcement Module
===================================
Phase 3: Behavior Hardening for PACS-Compliant UID-Only Mode

This module enforces a critical invariant: when pixel_action == NOT_APPLIED,
the PixelData bytes in the output MUST equal the input bytes exactly.

Key components:
- PixelAction enum: Single source of truth for pixel modification decision
- sha256_bytes(): Cryptographic hash for pixel data comparison
- enforce_pixel_passthrough_invariant(): Hard-fail guard if pixels mutate

Design Principles:
1. Boring + Deterministic: Simple hash comparison, no magic
2. Fail-Fast: Raises RuntimeError immediately on violation
3. Auditable: Provides clear audit trail fields for logging
4. Zero-Decode Guarantee: Never touches pixel_array in NOT_APPLIED mode

Usage:
    from pixel_invariant import PixelAction, decide_pixel_action, enforce_pixel_passthrough_invariant
    
    pixel_action = decide_pixel_action(options)
    if pixel_action == PixelAction.NOT_APPLIED:
        enforce_pixel_passthrough_invariant(input_ds, output_ds, enabled=True, why="UID-only mode")
"""

import hashlib
from enum import Enum
from typing import Optional, NamedTuple
import pydicom


# ═══════════════════════════════════════════════════════════════════════════════
# PIXEL ACTION ENUM - Single Source of Truth
# ═══════════════════════════════════════════════════════════════════════════════

class PixelAction(str, Enum):
    """
    Defines whether pixel data should be modified during processing.
    
    This is the authoritative decision point for all pixel-related operations.
    Once set, this value MUST NOT be ignored or overridden downstream.
    
    Values:
        NOT_APPLIED: Pixels MUST pass through unchanged (UID-only mode)
        MASK_APPLIED: Pixels will be modified (masking, overlay, etc.)
    """
    NOT_APPLIED = "NOT_APPLIED"
    MASK_APPLIED = "MASK_APPLIED"


class PixelInvariantResult(NamedTuple):
    """
    Result of pixel invariant check for audit logging.
    
    Attributes:
        passed: True if invariant held, False if violated
        status: Human-readable status (PASS/FAIL/N_A)
        input_hash: SHA-256 of input PixelData (hex)
        output_hash: SHA-256 of output PixelData (hex)
        input_length: Length of input PixelData in bytes
        output_length: Length of output PixelData in bytes
        error_message: Description of violation if failed
    """
    passed: bool
    status: str  # "PASS", "FAIL", "N/A"
    input_hash: Optional[str] = None
    output_hash: Optional[str] = None
    input_length: Optional[int] = None
    output_length: Optional[int] = None
    error_message: Optional[str] = None


# ═══════════════════════════════════════════════════════════════════════════════
# HASH UTILITIES
# ═══════════════════════════════════════════════════════════════════════════════

def sha256_bytes(data: bytes) -> str:
    """
    Compute SHA-256 hash of raw bytes.
    
    Args:
        data: Raw bytes to hash
        
    Returns:
        Hexadecimal string representation of SHA-256 hash
    """
    return hashlib.sha256(data).hexdigest()


def get_pixel_data_safe(ds: pydicom.Dataset) -> Optional[bytes]:
    """
    Safely extract PixelData bytes without triggering decode.
    
    CRITICAL: Uses getattr() to avoid any property accessors that might
    trigger decompression or pixel pipeline transforms.
    
    Args:
        ds: pydicom Dataset
        
    Returns:
        Raw PixelData bytes if present, None otherwise
    """
    # Use getattr to avoid triggering any lazy loading or decoding
    pixel_data = getattr(ds, 'PixelData', None)
    if pixel_data is None:
        return None
    
    # pydicom may return the raw bytes or a bytes-like object
    # Ensure we have actual bytes for hashing
    if isinstance(pixel_data, bytes):
        return pixel_data
    elif hasattr(pixel_data, 'tobytes'):
        # Could be a numpy array or memoryview
        return pixel_data.tobytes()
    else:
        # Try bytes conversion as last resort
        return bytes(pixel_data)


# ═══════════════════════════════════════════════════════════════════════════════
# DECISION FUNCTION
# ═══════════════════════════════════════════════════════════════════════════════

def decide_pixel_action(
    clinical_context: Optional[dict] = None,
    apply_mask: bool = False,
    mask_list: Optional[list] = None,
    manual_box: Optional[tuple] = None
) -> PixelAction:
    """
    Determine whether pixels should be modified based on processing options.
    
    This is the SINGLE authoritative decision point for pixel modification.
    All downstream code MUST respect this decision.
    
    Args:
        clinical_context: Clinical correction context dict (may contain uid_only_mode)
        apply_mask: Explicit flag for mask application
        mask_list: List of mask regions (if non-empty, implies masking)
        manual_box: Manual mask box tuple (if set, implies masking)
        
    Returns:
        PixelAction.NOT_APPLIED if pixels must pass through unchanged
        PixelAction.MASK_APPLIED if pixels will be modified
    """
    # Check for UID-only mode in clinical context
    if clinical_context:
        uid_only_mode = clinical_context.get('uid_only_mode', False)
        if uid_only_mode:
            return PixelAction.NOT_APPLIED
    
    # Check for explicit masking requests
    if apply_mask:
        return PixelAction.MASK_APPLIED
    
    if mask_list and len(mask_list) > 0:
        return PixelAction.MASK_APPLIED
    
    if manual_box is not None:
        return PixelAction.MASK_APPLIED
    
    # Default: No pixel modification
    return PixelAction.NOT_APPLIED


# ═══════════════════════════════════════════════════════════════════════════════
# INVARIANT ENFORCEMENT
# ═══════════════════════════════════════════════════════════════════════════════

def enforce_pixel_passthrough_invariant(
    input_ds: pydicom.Dataset,
    output_ds: pydicom.Dataset,
    enabled: bool,
    why: str
) -> PixelInvariantResult:
    """
    Enforce that PixelData bytes are identical between input and output.
    
    This function HARD-FAILS (raises RuntimeError) if the invariant is violated.
    Use this as a guardrail in UID-only mode to catch any accidental pixel
    mutations from decode/encode cycles, normalization, or transcoding.
    
    Args:
        input_ds: Original DICOM dataset (source of truth)
        output_ds: Processed DICOM dataset (must have identical PixelData)
        enabled: If False, skips check and returns N/A result
        why: Human-readable reason for this check (for error messages)
        
    Returns:
        PixelInvariantResult with check details for audit logging
        
    Raises:
        RuntimeError: If enabled=True and PixelData differs between input/output
    """
    if not enabled:
        return PixelInvariantResult(
            passed=True,
            status="N/A",
            error_message="Check disabled"
        )
    
    # Extract PixelData safely without decoding
    in_pd = get_pixel_data_safe(input_ds)
    out_pd = get_pixel_data_safe(output_ds)
    
    # Handle missing PixelData cases
    if in_pd is None and out_pd is None:
        # Both missing - invariant not applicable (e.g., structured report)
        return PixelInvariantResult(
            passed=True,
            status="N/A",
            error_message="No PixelData in input or output"
        )
    
    if in_pd is None and out_pd is not None:
        # PixelData was added - this is a violation in NOT_APPLIED mode
        raise RuntimeError(
            f"Pixel invariant violated ({why}): PixelData was added to output "
            f"when input had none. This is forbidden in UID-only mode."
        )
    
    if in_pd is not None and out_pd is None:
        # PixelData was removed - this is a violation in NOT_APPLIED mode
        raise RuntimeError(
            f"Pixel invariant violated ({why}): PixelData was removed from output "
            f"when input had {len(in_pd)} bytes. This is forbidden in UID-only mode."
        )
    
    # Both present - compute hashes and compare
    in_hash = sha256_bytes(in_pd)
    out_hash = sha256_bytes(out_pd)
    in_len = len(in_pd)
    out_len = len(out_pd)
    
    if in_len != out_len:
        raise RuntimeError(
            f"Pixel invariant violated ({why}): PixelData length changed from "
            f"{in_len} to {out_len} bytes. This is forbidden in UID-only mode."
        )
    
    if in_hash != out_hash:
        raise RuntimeError(
            f"Pixel invariant violated ({why}): PixelData content differs. "
            f"Input hash: {in_hash[:16]}..., Output hash: {out_hash[:16]}... "
            f"This is forbidden in UID-only mode."
        )
    
    # Invariant passed
    return PixelInvariantResult(
        passed=True,
        status="PASS",
        input_hash=in_hash,
        output_hash=out_hash,
        input_length=in_len,
        output_length=out_len
    )


def check_transfer_syntax_preserved(
    input_ds: pydicom.Dataset,
    output_ds: pydicom.Dataset,
    enabled: bool,
    why: str
) -> bool:
    """
    Check that Transfer Syntax UID is preserved between input and output.
    
    In UID-only mode, transcoding is forbidden as it forces pixel re-encoding.
    This check catches accidental JPEG->Uncompressed or similar conversions.
    
    Args:
        input_ds: Original DICOM dataset
        output_ds: Processed DICOM dataset
        enabled: If False, skips check and returns True
        why: Human-readable reason for this check
        
    Returns:
        True if preserved or check disabled
        
    Raises:
        RuntimeError: If enabled=True and TransferSyntaxUID changed
    """
    if not enabled:
        return True
    
    # Get Transfer Syntax from file_meta
    in_tsuid = None
    out_tsuid = None
    
    if hasattr(input_ds, 'file_meta') and hasattr(input_ds.file_meta, 'TransferSyntaxUID'):
        in_tsuid = str(input_ds.file_meta.TransferSyntaxUID)
    
    if hasattr(output_ds, 'file_meta') and hasattr(output_ds.file_meta, 'TransferSyntaxUID'):
        out_tsuid = str(output_ds.file_meta.TransferSyntaxUID)
    
    if in_tsuid is None or out_tsuid is None:
        # Cannot compare - skip check
        return True
    
    if in_tsuid != out_tsuid:
        raise RuntimeError(
            f"Transfer Syntax invariant violated ({why}): Changed from "
            f"{in_tsuid} to {out_tsuid}. Transcoding is forbidden in UID-only mode."
        )
    
    return True


# ═══════════════════════════════════════════════════════════════════════════════
# CONVENIENCE WRAPPER
# ═══════════════════════════════════════════════════════════════════════════════

def validate_uid_only_output(
    input_ds: pydicom.Dataset,
    output_ds: pydicom.Dataset,
    pixel_action: PixelAction,
    audit_dict: Optional[dict] = None
) -> PixelInvariantResult:
    """
    Full validation for UID-only mode output.
    
    Combines pixel invariant check and transfer syntax check.
    Updates audit_dict with results if provided.
    
    Args:
        input_ds: Original DICOM dataset
        output_ds: Processed DICOM dataset
        pixel_action: The authoritative pixel action decision
        audit_dict: Optional dict to update with audit fields
        
    Returns:
        PixelInvariantResult with full details
        
    Raises:
        RuntimeError: If pixel_action is NOT_APPLIED and invariants are violated
    """
    is_uid_only = pixel_action == PixelAction.NOT_APPLIED
    
    # Check transfer syntax first (fails fast if transcoded)
    check_transfer_syntax_preserved(
        input_ds, output_ds,
        enabled=is_uid_only,
        why="UID-only clinical correction"
    )
    
    # Check pixel data integrity
    result = enforce_pixel_passthrough_invariant(
        input_ds, output_ds,
        enabled=is_uid_only,
        why="UID-only clinical correction"
    )
    
    # Update audit dict if provided
    if audit_dict is not None:
        audit_dict['pixel_action'] = pixel_action.value
        audit_dict['pixel_invariant'] = result.status
        if result.input_hash:
            audit_dict['pixel_sha_in'] = result.input_hash
        if result.output_hash:
            audit_dict['pixel_sha_out'] = result.output_hash
    
    return result
