"""
Unit tests for preflight.py (Phase 8, Item 4.1)

Tests:
- Happy path with valid dirs
- Mode missing failure
- Missing dependency failure
- Low disk space failure
"""

import tempfile
from pathlib import Path
import pytest
import shutil
import sys
import os

# Match existing test file pattern
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from preflight import run_preflight, raise_if_failed, PreflightError, PreflightResult


class TestPreflightHappyPath:
    """Tests for successful preflight scenarios."""
    
    def test_preflight_ok_with_temp_dirs(self):
        """Preflight should pass with valid directories and mode set."""
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp) / "downloads"
            r = Path(tmp) / "run"
            res = run_preflight(
                downloads_dir=d,
                run_root=r,
                processing_mode="pilot",
                min_free_bytes=1,  # trivially low
                required_modules=(),  # don't require real deps in unit test
            )
            assert res.ok
            assert len(res.errors) == 0
            raise_if_failed(res)  # Should not raise
    
    def test_preflight_creates_directories(self):
        """Preflight should create directories if they don't exist."""
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp) / "new_downloads"
            r = Path(tmp) / "new_run"
            
            assert not d.exists()
            assert not r.exists()
            
            res = run_preflight(
                downloads_dir=d,
                run_root=r,
                processing_mode="research",
                min_free_bytes=1,
                required_modules=(),
            )
            
            assert res.ok
            assert d.exists()
            assert r.exists()


class TestPreflightModeChecks:
    """Tests for processing mode validation."""
    
    def test_preflight_fails_when_mode_missing(self):
        """Preflight should fail when mode is empty string."""
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp) / "downloads"
            r = Path(tmp) / "run"
            res = run_preflight(
                downloads_dir=d,
                run_root=r,
                processing_mode="",
                min_free_bytes=1,
                required_modules=(),
            )
            assert not res.ok
            assert any("mode" in e.lower() for e in res.errors)
            with pytest.raises(PreflightError):
                raise_if_failed(res)
    
    def test_preflight_fails_when_mode_none(self):
        """Preflight should fail when mode is None."""
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp) / "downloads"
            r = Path(tmp) / "run"
            res = run_preflight(
                downloads_dir=d,
                run_root=r,
                processing_mode=None,
                min_free_bytes=1,
                required_modules=(),
            )
            assert not res.ok
            with pytest.raises(PreflightError):
                raise_if_failed(res)


class TestPreflightDependencyChecks:
    """Tests for dependency validation."""
    
    def test_preflight_fails_when_dependency_missing(self):
        """Preflight should fail when a required module is not importable."""
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp) / "downloads"
            r = Path(tmp) / "run"
            res = run_preflight(
                downloads_dir=d,
                run_root=r,
                processing_mode="pilot",
                min_free_bytes=1,
                required_modules=("definitely_not_a_real_module_xyz",),
            )
            assert not res.ok
            assert any("Missing dependency" in e for e in res.errors)
    
    def test_preflight_passes_with_pydicom(self):
        """Preflight should pass when pydicom is available."""
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp) / "downloads"
            r = Path(tmp) / "run"
            res = run_preflight(
                downloads_dir=d,
                run_root=r,
                processing_mode="pilot",
                min_free_bytes=1,
                required_modules=("pydicom",),
            )
            assert res.ok


class TestPreflightDiskSpaceChecks:
    """Tests for disk space validation."""
    
    def test_preflight_fails_when_disk_space_insufficient(self, monkeypatch):
        """Preflight should fail when free disk space is below threshold."""
        class FakeUsage:
            total = 100
            used = 90
            free = 10

        def fake_disk_usage(_):
            return FakeUsage()

        monkeypatch.setattr(shutil, "disk_usage", fake_disk_usage)

        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp) / "downloads"
            r = Path(tmp) / "run"
            res = run_preflight(
                downloads_dir=d,
                run_root=r,
                processing_mode="pilot",
                min_free_bytes=9999,
                required_modules=(),
            )
            assert not res.ok
            assert any("Insufficient free space" in e for e in res.errors)
    
    def test_preflight_warns_when_disk_usage_unavailable(self, monkeypatch):
        """Preflight should warn but not fail when disk usage check fails."""
        def fake_disk_usage(_):
            raise OSError("Not supported")

        monkeypatch.setattr(shutil, "disk_usage", fake_disk_usage)

        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp) / "downloads"
            r = Path(tmp) / "run"
            res = run_preflight(
                downloads_dir=d,
                run_root=r,
                processing_mode="pilot",
                min_free_bytes=1,
                required_modules=(),
            )
            # Should still pass, but with a warning
            assert res.ok
            assert len(res.warnings) > 0


class TestPreflightResult:
    """Tests for PreflightResult dataclass."""
    
    def test_result_is_frozen(self):
        """PreflightResult should be immutable."""
        res = PreflightResult(ok=True)
        with pytest.raises(AttributeError):
            res.ok = False
    
    def test_raise_if_failed_does_nothing_on_success(self):
        """raise_if_failed should not raise when ok=True."""
        res = PreflightResult(ok=True)
        raise_if_failed(res)  # Should not raise
    
    def test_raise_if_failed_raises_on_failure(self):
        """raise_if_failed should raise PreflightError when ok=False."""
        res = PreflightResult(ok=False, errors=("Test error",))
        with pytest.raises(PreflightError) as exc_info:
            raise_if_failed(res)
        assert "Test error" in str(exc_info.value)
