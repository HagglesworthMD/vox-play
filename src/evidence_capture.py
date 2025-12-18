"""
VoxelMask Evidence/Config Capture (Phase 8, Item 4.4)

Purpose:
- Write a PHI-sterile run receipt into the run directory (receipts/)
- Capture version/build + selected mode/profile + selection scope summary
- Additive only; no processing / de-id semantics changes
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Optional, Tuple, List
import json
from datetime import datetime, timezone


RECEIPT_FILENAME = "run_receipt.json"


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _safe_read_json(path: Path) -> Dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _selection_scope_summary(selection_scope: Any) -> Dict[str, Any]:
    """
    Return a PHI-sterile summary of SelectionScope.

    We only capture boolean switches that impact inclusion semantics at a high level.
    No filenames, IDs, UIDs, counts, or paths.
    """
    if selection_scope is None:
        return {}

    # Try common patterns without coupling hard to class implementation.
    summary: Dict[str, Any] = {}
    for key in ("images", "documents", "dicom", "non_dicom", "include_images", "include_documents"):
        if hasattr(selection_scope, key):
            val = getattr(selection_scope, key)
            if isinstance(val, bool):
                summary[key] = val
    return summary


def _preflight_summary(preflight_result: Any) -> Dict[str, Any]:
    """
    Return a PHI-sterile preflight summary.

    - ok boolean
    - warnings only (errors are handled elsewhere on failure)
    """
    if preflight_result is None:
        return {}

    # Works with our PreflightResult dataclass but stays defensive.
    ok = getattr(preflight_result, "ok", None)
    warnings = getattr(preflight_result, "warnings", ())
    if warnings is None:
        warnings = ()

    # Force to tuple of strings.
    warnings_out: List[str] = []
    for w in warnings:
        try:
            warnings_out.append(str(w))
        except Exception:
            pass

    out: Dict[str, Any] = {}
    if isinstance(ok, bool):
        out["ok"] = ok
    if warnings_out:
        out["warnings"] = tuple(warnings_out)
    return out


def build_run_receipt(
    *,
    run_id: str,
    run_root: Path,
    processing_mode: Optional[str],
    gateway_profile: Optional[str],
    selection_scope: Any,
    build_info: Optional[str] = None,
    git_sha: Optional[str] = None,
    preflight_result: Any = None,
) -> Dict[str, Any]:
    """
    Build a PHI-sterile run receipt dict.

    Reads started_at from run_status.json if present.
    """
    run_status = _safe_read_json(run_root / "run_status.json")
    started_at = run_status.get("started_at")

    receipt: Dict[str, Any] = {
        "run_id": run_id,
        "started_at": started_at,
        "receipt_written_at": _utc_now_iso(),
        "processing_mode": processing_mode,
        "gateway_profile": gateway_profile,
        "selection_scope": _selection_scope_summary(selection_scope),
        "build_info": build_info,
        "git_sha": git_sha or "unknown",
        "preflight": _preflight_summary(preflight_result),
        # Phase 12: Canonical viewer path for FOI/support defensibility
        # Path is deterministic from run_id; actual creation happens at export.
        "viewer_path": f"downloads/voxelmask_runs/{run_id}/viewer/viewer.html",
        "phase": "phase12",  # Updated from phase8
        "item": "viewer_consolidation",
    }

    # Strip None values for cleanliness.
    return {k: v for k, v in receipt.items() if v is not None}


def write_run_receipt(receipts_dir: Path, receipt: Dict[str, Any]) -> Path:
    """
    Write the receipt JSON to receipts_dir/run_receipt.json
    """
    receipts_dir.mkdir(parents=True, exist_ok=True)
    out_path = receipts_dir / RECEIPT_FILENAME
    out_path.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    return out_path


def assert_phi_sterile(receipt: Dict[str, Any]) -> None:
    """
    Guardrail: ensure receipt contains no obvious PHI-bearing keys.

    This is intentionally conservative and keyword-based.
    """
    banned_key_fragments = (
        "patient",
        "name",
        "dob",
        "mrn",
        "accession",
        "study",
        "series",
        "instance",
        "uid",
        "filename",
        "file_path",
        "filepath",
    )

    def walk(obj: Any) -> None:
        if isinstance(obj, dict):
            for k, v in obj.items():
                ks = str(k).lower()
                for frag in banned_key_fragments:
                    if frag in ks:
                        raise AssertionError(f"Receipt not PHI-sterile: key contains '{frag}': {k}")
                walk(v)
        elif isinstance(obj, (list, tuple)):
            for item in obj:
                walk(item)

    walk(receipt)
