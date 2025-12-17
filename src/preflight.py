"""
VoxelMask Preflight Gate — Startup Checks (Phase 8, Item 4.1)

Purpose:
- Fail early on unsafe runtime conditions (permissions, disk space, dependencies)
- PHI-sterile (no filenames, patient identifiers, DICOM content)
- Semantics-neutral (does not alter de-id logic; only blocks execution when unsafe)
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import importlib
import shutil
from typing import Tuple, List, Optional


class PreflightError(RuntimeError):
    """Raised when preflight checks fail."""


@dataclass(frozen=True)
class PreflightResult:
    ok: bool
    errors: Tuple[str, ...] = ()
    warnings: Tuple[str, ...] = ()


def _check_dir_exists_or_create(path: Path, errors: List[str]) -> None:
    try:
        path.mkdir(parents=True, exist_ok=True)
    except OSError as e:
        errors.append(f"Cannot create directory: {path} ({e.__class__.__name__})")


def _check_dir_writable(path: Path, errors: List[str]) -> None:
    # Use a write test file rather than os.access (more reliable with ACLs).
    probe = path / ".vm_write_probe"
    try:
        probe.write_text("ok\n", encoding="utf-8")
        probe.unlink(missing_ok=True)
    except OSError as e:
        errors.append(f"Directory not writable: {path} ({e.__class__.__name__})")


def _check_free_space(path: Path, min_free_bytes: int, errors: List[str], warnings: List[str]) -> None:
    try:
        usage = shutil.disk_usage(str(path))
    except OSError as e:
        warnings.append(f"Could not determine free disk space for: {path} ({e.__class__.__name__})")
        return

    if usage.free < min_free_bytes:
        errors.append(
            f"Insufficient free space at {path}: free={usage.free}B required>={min_free_bytes}B"
        )


def _check_importable(module_name: str, errors: List[str]) -> None:
    try:
        importlib.import_module(module_name)
    except Exception as e:  # noqa: BLE001 - we want any import failure reason
        errors.append(f"Missing dependency: {module_name} ({e.__class__.__name__})")


def run_preflight(
    *,
    downloads_dir: Path,
    run_root: Path,
    processing_mode: Optional[str],
    min_free_bytes: int = 250 * 1024 * 1024,  # 250MB conservative default
    required_modules: Tuple[str, ...] = ("pydicom",),
) -> PreflightResult:
    """
    Run Phase 8 preflight checks.

    Args:
        downloads_dir: base downloads directory (expected to exist or be creatable)
        run_root: run root directory (expected to exist or be creatable)
        processing_mode: selected mode string (Pilot/Research/etc). Must be explicit.
        min_free_bytes: conservative minimum free disk requirement
        required_modules: modules that must be importable

    Returns:
        PreflightResult
    """
    errors: List[str] = []
    warnings: List[str] = []

    if processing_mode is None or str(processing_mode).strip() == "":
        errors.append("Processing mode is not set (must be explicit).")

    # Directory checks
    _check_dir_exists_or_create(downloads_dir, errors)
    if downloads_dir.exists():
        _check_dir_writable(downloads_dir, errors)

    _check_dir_exists_or_create(run_root, errors)
    if run_root.exists():
        _check_dir_writable(run_root, errors)

    # Disk space check on downloads_dir (or run_root if downloads fails)
    target = downloads_dir if downloads_dir.exists() else run_root
    _check_free_space(target, min_free_bytes, errors, warnings)

    # Dependency checks
    for mod in required_modules:
        _check_importable(mod, errors)

    return PreflightResult(ok=(len(errors) == 0), errors=tuple(errors), warnings=tuple(warnings))


def raise_if_failed(result: PreflightResult) -> None:
    """Raise PreflightError if preflight failed."""
    if not result.ok:
        msg = "Preflight failed:\n- " + "\n- ".join(result.errors)
        raise PreflightError(msg)
