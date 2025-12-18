"""
VoxelMask Run Status Helpers (Phase 8, Item 4.5)

Purpose:
- Deterministic, PHI-sterile run status updates
- Atomic writes (temp file + rename)
- Safe if file missing or partially corrupt
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Optional
import json
import os
from datetime import datetime, timezone


STATUS_FILENAME = "run_status.json"


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def load_run_status(run_root: Path) -> Dict[str, Any]:
    """Load existing run_status.json, returning empty dict if missing or corrupt."""
    path = run_root / STATUS_FILENAME
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def update_run_status(
    run_root: Path,
    *,
    status: str,
    timestamp_field: Optional[str] = None,
    failure_reason: Optional[str] = None,
) -> Path:
    """
    Update run_status.json atomically.

    Args:
        run_root: run root directory
        status: one of in_progress | preflight_failed | completed | failed
        timestamp_field: optional field name to set to now (e.g., completed_at, failed_at)
        failure_reason: short, non-PHI reason string (optional)

    Returns:
        Path to updated run_status.json
    """
    run_root.mkdir(parents=True, exist_ok=True)
    path = run_root / STATUS_FILENAME
    tmp = run_root / f".{STATUS_FILENAME}.tmp"

    data = load_run_status(run_root)
    data["status"] = status

    if timestamp_field:
        data[timestamp_field] = _utc_now_iso()

    if failure_reason:
        data["failure_reason"] = str(failure_reason)

    tmp.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    os.replace(tmp, path)
    return path
