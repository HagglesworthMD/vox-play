import pytest
import sys
import os
from typing import Any, Dict

# Ensure src is in path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src")))

from session_state import reset_run_state, RUN_ID_KEY

def test_reset_bumps_run_id_and_clears_run_scoped_keys():
    """
    Unit test for reset_run_state that validates:
    1. RUN_ID is changed
    2. Run-scoped keys are removed
    3. Non-run-scoped keys (preferences) are preserved
    4. UI defaults are initialized
    """
    ss: Dict[str, Any] = {
        RUN_ID_KEY: "old_run_123",
        "viewer_state": {"zoom": 1.5, "series": "1.2.3"},
        "phi_review_session": "ReviewSessionObject",
        "uploaded_dicom_files": ["file1.dcm", "file2.dcm"],
        "gateway_profile": "Standard De-ID",  # Should be preserved
        "selection_scope": {"include_images": True},  # Should be preserved
        "other_ui_pref": True,  # Should be preserved
    }
    
    prev_id = reset_run_state(ss, reason="test_reset")

    # 1. RUN_ID is changed
    assert ss[RUN_ID_KEY] != "old_run_123"
    assert len(ss[RUN_ID_KEY]) >= 32  # hex uuid length
    assert prev_id == "old_run_123"

    # 2. Run-scoped keys are removed or reset to safe defaults
    assert "viewer_state" not in ss
    assert ss.get("phi_review_session") is None
    assert ss.get("uploaded_dicom_files") == []

    # 3. Non-run-scoped keys (preferences) are preserved
    assert ss.get("gateway_profile") == "Standard De-ID"
    assert ss.get("selection_scope") == {"include_images": True}
    assert ss.get("other_ui_pref") is True

    # 4. UI defaults are initialized
    assert ss.get("selected_instance_idx") == 0
    assert ss.get("selected_series_uid") is None

def test_reset_handles_empty_state():
    """Validates it works even if session state is empty."""
    ss: Dict[str, Any] = {}
    reset_run_state(ss)
    
    assert RUN_ID_KEY in ss
    assert ss["selected_instance_idx"] == 0

def test_reset_is_deterministic_in_clearing():
    """Validates that keys NOT in the scoped list are definitely safe."""
    SAFE_KEY = "user_email_persist"
    ss = {
        SAFE_KEY: "user@example.com",
        "run_id": "current"
    }
    reset_run_state(ss)
    assert ss[SAFE_KEY] == "user@example.com"
