"""
Unit tests for run_status.py (Phase 8, Item 4.5)

Tests:
- Update completed preserves existing fields
- Update failed sets reason
- Missing file is handled gracefully
"""

import json
import tempfile
from pathlib import Path
import sys
import os

# Match existing test file pattern
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from run_status import load_run_status, update_run_status, STATUS_FILENAME


class TestLoadRunStatus:
    """Tests for loading run status."""
    
    def test_loads_existing_status(self):
        """Should load existing run_status.json."""
        with tempfile.TemporaryDirectory() as tmp:
            run_root = Path(tmp)
            (run_root / STATUS_FILENAME).write_text(
                json.dumps({"run_id": "VM_RUN_x", "status": "in_progress"}),
                encoding="utf-8",
            )
            
            data = load_run_status(run_root)
            
            assert data["run_id"] == "VM_RUN_x"
            assert data["status"] == "in_progress"
    
    def test_returns_empty_dict_if_missing(self):
        """Should return empty dict if file missing."""
        with tempfile.TemporaryDirectory() as tmp:
            run_root = Path(tmp)
            
            data = load_run_status(run_root)
            
            assert data == {}
    
    def test_returns_empty_dict_if_corrupt(self):
        """Should return empty dict if file is corrupt JSON."""
        with tempfile.TemporaryDirectory() as tmp:
            run_root = Path(tmp)
            (run_root / STATUS_FILENAME).write_text("not valid json{{{", encoding="utf-8")
            
            data = load_run_status(run_root)
            
            assert data == {}


class TestUpdateRunStatus:
    """Tests for updating run status."""
    
    def test_update_completed_preserves_existing_fields(self):
        """Updating to completed should preserve run_id and started_at."""
        with tempfile.TemporaryDirectory() as tmp:
            run_root = Path(tmp)
            (run_root / STATUS_FILENAME).write_text(
                json.dumps({"run_id": "VM_RUN_x", "started_at": "2025-01-01T00:00:00+00:00", "status": "in_progress"}),
                encoding="utf-8",
            )

            update_run_status(run_root, status="completed", timestamp_field="completed_at")

            data = load_run_status(run_root)
            assert data["run_id"] == "VM_RUN_x"
            assert data["started_at"] == "2025-01-01T00:00:00+00:00"
            assert data["status"] == "completed"
            assert "completed_at" in data
    
    def test_update_failed_sets_reason(self):
        """Updating to failed should set failure_reason."""
        with tempfile.TemporaryDirectory() as tmp:
            run_root = Path(tmp)
            update_run_status(
                run_root,
                status="failed",
                timestamp_field="failed_at",
                failure_reason="processing_error",
            )

            data = load_run_status(run_root)
            assert data["status"] == "failed"
            assert data["failure_reason"] == "processing_error"
            assert "failed_at" in data
    
    def test_missing_file_is_handled(self):
        """Should handle missing file by creating new one."""
        with tempfile.TemporaryDirectory() as tmp:
            run_root = Path(tmp)
            update_run_status(run_root, status="completed", timestamp_field="completed_at")
            
            data = load_run_status(run_root)
            assert data["status"] == "completed"
    
    def test_creates_directory_if_needed(self):
        """Should create run_root directory if it doesn't exist."""
        with tempfile.TemporaryDirectory() as tmp:
            run_root = Path(tmp) / "new_run"
            
            assert not run_root.exists()
            
            update_run_status(run_root, status="completed")
            
            assert run_root.exists()
            assert (run_root / STATUS_FILENAME).exists()
    
    def test_atomic_write_uses_temp_file(self):
        """Should use temp file for atomic write (no partial writes)."""
        with tempfile.TemporaryDirectory() as tmp:
            run_root = Path(tmp)
            
            update_run_status(run_root, status="completed")
            
            # Temp file should not exist after successful write
            tmp_file = run_root / f".{STATUS_FILENAME}.tmp"
            assert not tmp_file.exists()
            
            # Main file should exist
            assert (run_root / STATUS_FILENAME).exists()
    
    def test_timestamp_is_utc_iso(self):
        """Timestamp should be UTC ISO8601 format."""
        with tempfile.TemporaryDirectory() as tmp:
            run_root = Path(tmp)
            update_run_status(run_root, status="completed", timestamp_field="completed_at")
            
            data = load_run_status(run_root)
            ts = data["completed_at"]
            
            # Should end with +00:00 or Z for UTC
            assert "+00:00" in ts or ts.endswith("Z")
