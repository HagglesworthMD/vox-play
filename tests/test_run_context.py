"""
Unit tests for run_context.py (Phase 8, Item 4.2)

Tests:
- Run ID uniqueness
- RunPaths structure
- Directory creation
"""

import pytest
import tempfile
from pathlib import Path

# Match existing test file pattern
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from run_context import generate_run_id, build_run_paths, ensure_run_dirs, RunPaths


class TestGenerateRunId:
    """Tests for run ID generation."""
    
    def test_format_has_prefix(self):
        """Run ID should start with VM_RUN_ prefix."""
        run_id = generate_run_id()
        assert run_id.startswith("VM_RUN_")
    
    def test_two_ids_are_different(self):
        """Two generated run IDs should never collide."""
        id1 = generate_run_id()
        id2 = generate_run_id()
        assert id1 != id2
    
    def test_id_is_filesystem_safe(self):
        """Run ID should not contain filesystem-unsafe characters."""
        run_id = generate_run_id()
        unsafe_chars = ['/', '\\', ':', '*', '?', '"', '<', '>', '|', ' ']
        for char in unsafe_chars:
            assert char not in run_id
    
    def test_id_has_reasonable_length(self):
        """Run ID should be reasonably short for filesystem use."""
        run_id = generate_run_id()
        # VM_RUN_ (7) + 12 hex chars = 19 chars
        assert len(run_id) == 19


class TestBuildRunPaths:
    """Tests for run paths structure."""
    
    def test_layout_structure(self):
        """Paths should follow canonical layout."""
        output_root = Path("/tmp/test_output")
        run_id = "VM_RUN_abc123def456"
        
        paths = build_run_paths(output_root, run_id)
        
        assert paths.run_id == run_id
        assert paths.root == output_root / "voxelmask_runs" / run_id
        assert paths.bundle_dir == paths.root / "bundle"
        assert paths.logs_dir == paths.root / "logs"
        assert paths.receipts_dir == paths.root / "receipts"
        assert paths.tmp_dir == paths.root / "tmp"
        # Phase 12: viewer_cache for run-scoped viewer input files
        assert paths.viewer_cache == paths.root / "viewer_cache"
    
    def test_paths_are_immutable(self):
        """RunPaths should be frozen (immutable)."""
        paths = build_run_paths(Path("/tmp"), "VM_RUN_test123456")
        with pytest.raises(AttributeError):
            paths.run_id = "changed"
    
    def test_paths_under_voxelmask_runs(self):
        """All paths should be under voxelmask_runs subdirectory."""
        output_root = Path("/data/exports")
        run_id = generate_run_id()
        
        paths = build_run_paths(output_root, run_id)
        
        assert "voxelmask_runs" in str(paths.root)
        assert paths.root.parent.name == "voxelmask_runs"


class TestEnsureRunDirs:
    """Tests for directory creation."""
    
    def test_creates_all_directories(self):
        """ensure_run_dirs should create all subdirectories."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_root = Path(tmpdir)
            run_id = generate_run_id()
            paths = build_run_paths(output_root, run_id)
            
            ensure_run_dirs(paths)
            
            assert paths.root.is_dir()
            assert paths.bundle_dir.is_dir()
            assert paths.logs_dir.is_dir()
            assert paths.receipts_dir.is_dir()
            assert paths.tmp_dir.is_dir()
            # Phase 12: viewer_cache for run-scoped viewer input files
            assert paths.viewer_cache.is_dir()
    
    def test_idempotent(self):
        """ensure_run_dirs should be safe to call multiple times."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_root = Path(tmpdir)
            paths = build_run_paths(output_root, "VM_RUN_idempotent1")
            
            ensure_run_dirs(paths)
            ensure_run_dirs(paths)  # Second call should not raise
            
            assert paths.root.is_dir()
    
    def test_collision_resistant(self):
        """Two runs should create separate directories."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_root = Path(tmpdir)
            
            paths1 = build_run_paths(output_root, generate_run_id())
            paths2 = build_run_paths(output_root, generate_run_id())
            
            ensure_run_dirs(paths1)
            ensure_run_dirs(paths2)
            
            assert paths1.root != paths2.root
            assert paths1.root.is_dir()
            assert paths2.root.is_dir()
    
    def test_nested_parent_creation(self):
        """ensure_run_dirs should create parent directories if needed."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Deep nesting that doesn't exist yet
            output_root = Path(tmpdir) / "deep" / "nested" / "path"
            run_id = generate_run_id()
            paths = build_run_paths(output_root, run_id)
            
            ensure_run_dirs(paths)
            
            assert paths.root.is_dir()
