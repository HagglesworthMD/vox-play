---
description: Phase 3 Pixel Invariant Enforcement - Behavior Hardening for UID-Only Mode
---

# Phase 3: Pixel Invariant Enforcement

## Overview

Phase 3 implements behavior hardening to prevent any pixel mutation in UID-only mode.
This is a critical safety feature for PACS-compliant workflows where only UIDs need 
to be regenerated without modifying patient image data.

## Key Components

### 1. `src/pixel_invariant.py`

Core module containing:

- **`PixelAction`** enum: `NOT_APPLIED` or `MASK_APPLIED`
- **`decide_pixel_action()`**: Single source of truth for pixel modification decision
- **`sha256_bytes()`**: Cryptographic hash for pixel data comparison
- **`enforce_pixel_passthrough_invariant()`**: Hard-fail guard if pixels mutate
- **`validate_uid_only_output()`**: Full validation wrapper for UID-only mode

### 2. Integration in `src/run_on_dicom.py`

The `process_dataset()` function now:
1. Decides pixel action at the start using `decide_pixel_action()`
2. Captures baseline PixelData hash before any processing
3. After metadata anonymization, verifies hash is unchanged (UID-only mode)
4. Populates audit_dict with `pixel_action`, `pixel_invariant`, and `pixel_sha`

## Guard Rules (UID-only mode)

When `clinical_context.uid_only_mode == True`:

1. **Never decode pixels** - No `ds.pixel_array` access
2. **Never modify Pixel Data module elements**
3. **Never rewrite with different transfer syntax**
4. **PixelData bytes in output MUST equal input bytes**

## Invariant Enforcement

Two-layer protection:

### Layer 1: Architectural Separation
- Export path uses separate dataset copy
- Preview path never touches export dataset

### Layer 2: Hash Verification
- SHA-256 computed before processing
- SHA-256 verified after processing
- RuntimeError raised on mismatch

## Usage Example

```python
from pixel_invariant import PixelAction, decide_pixel_action, validate_uid_only_output

# At export time
pixel_action = decide_pixel_action(clinical_context=clinical_context)

if pixel_action == PixelAction.NOT_APPLIED:
    # UID-only mode: validate before saving
    result = validate_uid_only_output(
        input_ds, output_ds,
        pixel_action=pixel_action,
        audit_dict=audit
    )
    # result.status == "PASS" or RuntimeError raised
```

## Audit Trail

The audit dict is populated with:
- `pixel_action`: "NOT_APPLIED" or "MASK_APPLIED"
- `pixel_invariant`: "PASS", "FAIL", or "N/A"
- `pixel_sha`: SHA-256 hash of PixelData (when applicable)

## Test Coverage

`tests/test_pixel_invariant.py` covers:
- PixelAction enum tests
- sha256_bytes helper tests
- decide_pixel_action logic tests
- enforce_pixel_passthrough_invariant (pass/fail scenarios)
- check_transfer_syntax_preserved tests
- End-to-end UID-only export simulation

`tests/test_run_on_dicom_process_dataset.py` covers:
- UID-only mode preserves PixelData
- Audit dict population
- MASK_APPLIED mode behavior

## Running Tests

```bash
# Run Phase 3 tests only
python -m pytest tests/test_pixel_invariant.py -v

# Run integration tests
python -m pytest tests/test_run_on_dicom_process_dataset.py -v

# Run full suite
python -m pytest tests/ -v
```

## Error Messages

On invariant violation:
```
RuntimeError: Pixel invariant violated (UID-only clinical correction): 
PixelData hash changed from abc123... to def456... 
This is forbidden in UID-only mode.
```
