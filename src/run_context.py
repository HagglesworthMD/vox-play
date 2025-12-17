"""
VoxelMask Run Context — Deterministic Run Identity + Path Layout

Phase 8 Operational Hardening (4.2)

This module provides:
- Unique run ID generation (UUIDv4)
- Canonical directory layout for run artefacts
- Directory creation helpers

No de-identification logic. No semantic changes.
"""

import uuid
from dataclasses import dataclass
from pathlib import Path


def generate_run_id() -> str:
    """
    Generate a unique run identifier.
    
    Uses UUIDv4 for guaranteed uniqueness without timing assumptions.
    Format: VM_RUN_<uuid4_hex_prefix>
    
    Returns:
        Unique run ID string
    """
    return f"VM_RUN_{uuid.uuid4().hex[:12]}"


@dataclass(frozen=True)
class RunPaths:
    """
    Canonical directory paths for a single VoxelMask run.
    
    All artefacts for a run should be written under these paths.
    Immutable after creation.
    """
    run_id: str
    root: Path
    bundle_dir: Path
    logs_dir: Path
    receipts_dir: Path
    tmp_dir: Path


def build_run_paths(output_root: Path, run_id: str) -> RunPaths:
    """
    Build canonical directory paths for a run.
    
    Layout:
        <output_root>/voxelmask_runs/<run_id>/
            bundle/
            logs/
            receipts/
            tmp/
    
    Args:
        output_root: Base output directory
        run_id: Unique run identifier
        
    Returns:
        RunPaths with all canonical directories
    """
    run_root = output_root / "voxelmask_runs" / run_id
    return RunPaths(
        run_id=run_id,
        root=run_root,
        bundle_dir=run_root / "bundle",
        logs_dir=run_root / "logs",
        receipts_dir=run_root / "receipts",
        tmp_dir=run_root / "tmp",
    )


def ensure_run_dirs(run_paths: RunPaths) -> None:
    """
    Create all directories in the run layout.
    
    Safe to call multiple times (idempotent).
    
    Args:
        run_paths: RunPaths to create
        
    Raises:
        OSError: If directory creation fails
    """
    run_paths.root.mkdir(parents=True, exist_ok=True)
    run_paths.bundle_dir.mkdir(exist_ok=True)
    run_paths.logs_dir.mkdir(exist_ok=True)
    run_paths.receipts_dir.mkdir(exist_ok=True)
    run_paths.tmp_dir.mkdir(exist_ok=True)
