"""
Unit tests for evidence_capture.py (Phase 8, Item 4.4)

Tests:
- Receipt building reads started_at from run_status.json
- Receipt writing creates JSON file
- PHI-sterile by default
- PHI guardrail catches bad keys
"""

import json
import tempfile
from pathlib import Path
import sys
import os

import pytest

# Match existing test file pattern
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from evidence_capture import build_run_receipt, write_run_receipt, assert_phi_sterile, RECEIPT_FILENAME


class DummyScope:
    """Minimal mock of SelectionScope for testing."""
    images = True
    documents = False
    include_images = True
    include_documents = False


class DummyPreflightResult:
    """Minimal mock of PreflightResult for testing."""
    ok = True
    warnings = ("Some warning",)


class TestBuildRunReceipt:
    """Tests for receipt building."""
    
    def test_reads_started_at_from_run_status(self):
        """Receipt should read started_at from run_status.json."""
        with tempfile.TemporaryDirectory() as tmp:
            run_root = Path(tmp) / "run"
            run_root.mkdir(parents=True, exist_ok=True)
            (run_root / "run_status.json").write_text(
                json.dumps({"run_id": "VM_RUN_x", "started_at": "2025-01-01T00:00:00+00:00", "status": "in_progress"}),
                encoding="utf-8",
            )

            receipt = build_run_receipt(
                run_id="VM_RUN_x",
                run_root=run_root,
                processing_mode="pilot",
                gateway_profile="internal_repair",
                selection_scope=DummyScope(),
                build_info="build=test",
                git_sha="abc123",
                preflight_result=None,
            )

            assert receipt["run_id"] == "VM_RUN_x"
            assert receipt["started_at"] == "2025-01-01T00:00:00+00:00"
            assert receipt["processing_mode"] == "pilot"
            assert receipt["gateway_profile"] == "internal_repair"
    
    def test_captures_selection_scope_summary(self):
        """Receipt should capture selection scope boolean flags."""
        with tempfile.TemporaryDirectory() as tmp:
            run_root = Path(tmp) / "run"
            run_root.mkdir(parents=True, exist_ok=True)

            receipt = build_run_receipt(
                run_id="VM_RUN_x",
                run_root=run_root,
                processing_mode="pilot",
                gateway_profile="internal_repair",
                selection_scope=DummyScope(),
                build_info=None,
                git_sha=None,
            )

            scope = receipt["selection_scope"]
            assert scope.get("images") == True
            assert scope.get("documents") == False
    
    def test_captures_preflight_summary(self):
        """Receipt should capture preflight ok and warnings."""
        with tempfile.TemporaryDirectory() as tmp:
            run_root = Path(tmp) / "run"
            run_root.mkdir(parents=True, exist_ok=True)

            receipt = build_run_receipt(
                run_id="VM_RUN_x",
                run_root=run_root,
                processing_mode="pilot",
                gateway_profile="internal_repair",
                selection_scope=None,
                preflight_result=DummyPreflightResult(),
            )

            assert receipt["preflight"]["ok"] == True
            assert "Some warning" in receipt["preflight"]["warnings"]
    
    def test_strips_none_values(self):
        """Receipt should not include None values."""
        with tempfile.TemporaryDirectory() as tmp:
            run_root = Path(tmp) / "run"
            run_root.mkdir(parents=True, exist_ok=True)

            receipt = build_run_receipt(
                run_id="VM_RUN_x",
                run_root=run_root,
                processing_mode=None,
                gateway_profile=None,
                selection_scope=None,
            )

            assert "processing_mode" not in receipt
            assert "gateway_profile" not in receipt


class TestWriteRunReceipt:
    """Tests for receipt writing."""
    
    def test_writes_json_file(self):
        """write_run_receipt should create a JSON file."""
        with tempfile.TemporaryDirectory() as tmp:
            receipts_dir = Path(tmp) / "receipts"
            receipt = {"run_id": "VM_RUN_test", "phase": "phase8", "item": "4.4"}

            out = write_run_receipt(receipts_dir, receipt)
            
            assert out.name == RECEIPT_FILENAME
            assert out.exists()

            loaded = json.loads(out.read_text(encoding="utf-8"))
            assert loaded["run_id"] == "VM_RUN_test"
    
    def test_creates_receipts_directory(self):
        """write_run_receipt should create the receipts directory if missing."""
        with tempfile.TemporaryDirectory() as tmp:
            receipts_dir = Path(tmp) / "new_receipts"
            
            assert not receipts_dir.exists()
            
            write_run_receipt(receipts_dir, {"run_id": "test"})
            
            assert receipts_dir.exists()


class TestPhiSterileGuard:
    """Tests for PHI-sterile guardrail."""
    
    def test_receipt_is_phi_sterile_by_default(self):
        """Default receipt should pass PHI-sterile check."""
        with tempfile.TemporaryDirectory() as tmp:
            run_root = Path(tmp) / "run"
            run_root.mkdir(parents=True, exist_ok=True)

            receipt = build_run_receipt(
                run_id="VM_RUN_x",
                run_root=run_root,
                processing_mode="pilot",
                gateway_profile="internal_repair",
                selection_scope=DummyScope(),
                build_info="build=test",
                git_sha="unknown",
                preflight_result=None,
            )

            # Should not raise
            assert_phi_sterile(receipt)
    
    def test_raises_on_patient_name_key(self):
        """PHI guardrail should catch patient_name key."""
        bad = {"patient_name": "nope"}
        with pytest.raises(AssertionError, match="patient"):
            assert_phi_sterile(bad)
    
    def test_raises_on_nested_phi_key(self):
        """PHI guardrail should catch nested PHI keys."""
        bad = {"outer": {"accession_number": "ACC123"}}
        with pytest.raises(AssertionError, match="accession"):
            assert_phi_sterile(bad)
    
    def test_allows_safe_keys(self):
        """PHI guardrail should allow safe keys."""
        safe = {
            "run_id": "VM_RUN_x",
            "processing_mode": "pilot",
            "selection_scope": {"images": True},
        }
        assert_phi_sterile(safe)  # Should not raise
