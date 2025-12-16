"""
Gate 3 — Evidence Bundle Schema Validation Tests
=================================================
Validates that evidence bundles conform to PHASE5C_GATE2_EVIDENCE_BUNDLE_SCHEMA.md

These tests ensure:
- Bundle structure matches canonical schema
- All required files are present
- All hashes validate
- Model B constraints are enforced (no pixel data, no PHI text)
- Counts are consistent across manifests

Gate 3 "Audit Completeness" uses these checks to verify bundles.
"""

import json
import csv
import hashlib
import pytest
import tempfile
from pathlib import Path
from typing import Dict, Any, List, Set

# Import the evidence bundle generator
import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from audit.evidence_bundle import EvidenceBundle, create_empty_bundle, SCHEMA_VERSION


# =============================================================================
# Schema Definition (from PHASE5C_GATE2_EVIDENCE_BUNDLE_SCHEMA.md)
# =============================================================================

REQUIRED_DIRECTORIES = [
    "CONFIG",
    "INPUT",
    "OUTPUT",
    "DECISIONS",
    "LINKAGE",
    "QA",
    "SIGNATURE",
]

REQUIRED_FILES = {
    "MANIFEST.json": True,
    "CONFIG/profile.json": True,
    "CONFIG/app_build.json": True,
    "CONFIG/runtime_env.json": True,
    "INPUT/source_index.json": True,
    "INPUT/source_hashes.csv": True,
    "OUTPUT/masked_index.json": True,
    "OUTPUT/masked_hashes.csv": True,
    "DECISIONS/detection_results.jsonl": True,
    "DECISIONS/masking_actions.jsonl": True,
    "DECISIONS/decision_log.jsonl": True,
    "LINKAGE/instance_linkage.csv": True,
    "QA/exceptions.jsonl": True,
    "QA/verification_report.json": True,
    "SIGNATURE/bundle_tree.txt": True,
}

MANIFEST_REQUIRED_FIELDS = [
    "schema_version",
    "processing_run_id",
    "timestamps",
    "counts",
    "files",
    "constraints",
]

MANIFEST_CONSTRAINT_FIELDS = [
    "stores_original_pixels",
    "stores_recovered_phi_text",
    "pacs_authoritative",
]


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def empty_bundle() -> Path:
    """Create an empty evidence bundle for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        bundle_path = create_empty_bundle(Path(tmpdir))
        yield bundle_path


@pytest.fixture
def populated_bundle() -> Path:
    """Create a populated evidence bundle for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        bundle = EvidenceBundle(
            processing_run_id="test-run-001",
            voxelmask_version="0.5.0",
            compliance_profile="FOI"
        )
        
        # Add source metadata
        bundle.start_processing()
        bundle.set_source_study("1.2.840.113564.test.study", "Test Study")
        bundle.add_source_series(
            series_uid="1.2.840.113564.test.series.1",
            modality="US",
            sop_class_uid="1.2.840.10008.5.1.4.1.1.6.1",
            instance_count=3
        )
        
        # Add source hashes
        for i in range(1, 4):
            bundle.add_source_hash(
                sop_instance_uid=f"1.2.840.113564.test.instance.{i}",
                pixel_hash=f"sha256:{'a' * 64}",
                series_uid="1.2.840.113564.test.series.1",
                instance_number=i
            )
        
        # Add detections (NO PHI text stored)
        bundle.add_detection(
            source_sop_uid="1.2.840.113564.test.instance.1",
            bbox=[10, 5, 200, 30],
            confidence=0.92,
            region="header",
            engine="PaddleOCR",
            engine_version="2.7.0",
            ruleset_id="US_HEADER",
            config_hash="sha256:config123"
        )
        
        # Add masking actions
        bundle.add_masking_action(
            masked_sop_uid="2.25.masked.1",
            action_type="black_box",
            bbox_applied=[10, 5, 200, 30],
            parameters={"color": [0, 0, 0], "padding": 2},
            result="success"
        )
        
        # Add masked outputs
        bundle.add_masked_hash(
            sop_instance_uid="2.25.masked.1",
            pixel_hash="sha256:masked123",
            series_uid="2.25.masked.series.1"
        )
        
        # Add linkage
        bundle.add_linkage(
            source_study_uid="1.2.840.113564.test.study",
            source_series_uid="1.2.840.113564.test.series.1",
            source_sop_uid="1.2.840.113564.test.instance.1",
            masked_study_uid="2.25.masked.study",
            masked_series_uid="2.25.masked.series.1",
            masked_sop_uid="2.25.masked.1"
        )
        
        # Add decision
        bundle.add_decision(
            decision_type="MASK",
            source_sop_uid="1.2.840.113564.test.instance.1",
            masked_sop_uid="2.25.masked.1",
            detections_count=1,
            actions_count=1,
            status="complete"
        )
        
        # Set config
        bundle.set_app_build(
            version="0.5.0",
            git_commit="abc123",
            ocr_engine="PaddleOCR",
            ocr_version="2.7.0"
        )
        bundle.set_runtime_env(
            python_version="3.12.0",
            platform="Linux"
        )
        
        bundle.end_processing()
        bundle_path = bundle.finalize(Path(tmpdir))
        yield bundle_path


# =============================================================================
# Structure Validation Tests
# =============================================================================

class TestBundleStructure:
    """Tests for bundle directory structure."""
    
    def test_bundle_directory_exists(self, empty_bundle: Path):
        """Bundle root directory should exist."""
        assert empty_bundle.exists()
        assert empty_bundle.is_dir()
    
    def test_bundle_name_format(self, empty_bundle: Path):
        """Bundle name should follow EVIDENCE_<run_id>_<timestamp> format."""
        name = empty_bundle.name
        assert name.startswith("EVIDENCE_")
        parts = name.split("_")
        assert len(parts) >= 3
        # Last part should be timestamp-like (ends with Z)
        assert parts[-1].endswith("Z")
    
    def test_required_directories_exist(self, empty_bundle: Path):
        """All required subdirectories should exist."""
        for dir_name in REQUIRED_DIRECTORIES:
            dir_path = empty_bundle / dir_name
            assert dir_path.exists(), f"Missing directory: {dir_name}"
            assert dir_path.is_dir(), f"Not a directory: {dir_name}"
    
    def test_required_files_exist(self, empty_bundle: Path):
        """All required files should exist."""
        for file_path, required in REQUIRED_FILES.items():
            if required:
                full_path = empty_bundle / file_path
                assert full_path.exists(), f"Missing required file: {file_path}"
    
    def test_hash_files_exist(self, empty_bundle: Path):
        """Every substantive file should have a .sha256 companion."""
        for file_path in REQUIRED_FILES.keys():
            if file_path.endswith(".json") or file_path.endswith(".csv") or file_path.endswith(".jsonl"):
                full_path = empty_bundle / file_path
                hash_path = full_path.with_suffix(full_path.suffix + ".sha256")
                assert hash_path.exists(), f"Missing hash file for: {file_path}"


# =============================================================================
# Manifest Validation Tests
# =============================================================================

class TestManifestValidation:
    """Tests for MANIFEST.json structure and content."""
    
    def test_manifest_is_valid_json(self, empty_bundle: Path):
        """MANIFEST.json should be valid JSON."""
        manifest_path = empty_bundle / "MANIFEST.json"
        content = manifest_path.read_text()
        manifest = json.loads(content)  # Should not raise
        assert isinstance(manifest, dict)
    
    def test_manifest_schema_version(self, empty_bundle: Path):
        """MANIFEST should have correct schema version."""
        manifest = json.loads((empty_bundle / "MANIFEST.json").read_text())
        assert manifest["schema_version"] == SCHEMA_VERSION
    
    def test_manifest_required_fields(self, empty_bundle: Path):
        """MANIFEST should have all required fields."""
        manifest = json.loads((empty_bundle / "MANIFEST.json").read_text())
        for field in MANIFEST_REQUIRED_FIELDS:
            assert field in manifest, f"Missing required field: {field}"
    
    def test_manifest_constraints_model_b(self, empty_bundle: Path):
        """MANIFEST constraints should enforce Model B."""
        manifest = json.loads((empty_bundle / "MANIFEST.json").read_text())
        constraints = manifest["constraints"]
        
        # Model B constraint: no original pixels stored
        assert constraints["stores_original_pixels"] == False
        
        # Model B constraint: no PHI text stored
        assert constraints["stores_recovered_phi_text"] == False
        
        # Model B constraint: PACS is authoritative
        assert constraints["pacs_authoritative"] == True
    
    def test_manifest_file_list_complete(self, empty_bundle: Path):
        """MANIFEST files list should include all bundle files."""
        manifest = json.loads((empty_bundle / "MANIFEST.json").read_text())
        listed_files = {f["path"] for f in manifest["files"]}
        
        # Check that key files are listed
        expected_files = [
            "CONFIG/profile.json",
            "CONFIG/app_build.json",
            "INPUT/source_index.json",
            "INPUT/source_hashes.csv",
        ]
        for expected in expected_files:
            assert expected in listed_files, f"File not in manifest: {expected}"


# =============================================================================
# Hash Integrity Tests
# =============================================================================

class TestHashIntegrity:
    """Tests for hash file integrity."""
    
    def test_manifest_hash_valid(self, empty_bundle: Path):
        """MANIFEST.json hash should validate."""
        manifest_path = empty_bundle / "MANIFEST.json"
        hash_path = empty_bundle / "MANIFEST.json.sha256"
        
        content = manifest_path.read_bytes()
        actual_hash = hashlib.sha256(content).hexdigest()
        
        recorded_hash = hash_path.read_text().split()[0]
        assert actual_hash == recorded_hash
    
    def test_all_file_hashes_valid(self, populated_bundle: Path):
        """All file hashes should validate."""
        errors = []
        
        for hash_file in populated_bundle.rglob("*.sha256"):
            # Get the file this hash is for
            target_name = hash_file.name.replace(".sha256", "")
            if target_name.endswith(".json"):
                target_path = hash_file.parent / target_name.replace(".json.sha256", ".json")
            else:
                target_path = hash_file.parent / target_name
            
            # Handle compound extensions
            if ".jsonl" in str(hash_file):
                target_path = hash_file.with_name(hash_file.name.replace(".sha256", ""))
            elif ".csv" in str(hash_file):
                target_path = hash_file.with_name(hash_file.name.replace(".sha256", ""))
            elif ".json" in str(hash_file) and not str(hash_file).endswith(".jsonl.sha256"):
                target_path = hash_file.with_name(hash_file.name.replace(".sha256", ""))
            elif ".txt" in str(hash_file):
                target_path = hash_file.with_name(hash_file.name.replace(".sha256", ""))
            
            if target_path.exists():
                content = target_path.read_bytes()
                actual_hash = hashlib.sha256(content).hexdigest()
                recorded_hash = hash_file.read_text().split()[0]
                
                if actual_hash != recorded_hash:
                    errors.append(f"{target_path.name}: expected {recorded_hash}, got {actual_hash}")
        
        assert len(errors) == 0, f"Hash validation errors: {errors}"


# =============================================================================
# Model B Constraint Enforcement Tests
# =============================================================================

class TestModelBConstraints:
    """Tests that Model B constraints are enforced."""
    
    def test_no_pixel_data_stored(self, populated_bundle: Path):
        """Bundle should not contain any pixel data files."""
        pixel_extensions = [".dcm", ".nii", ".nii.gz", ".raw", ".img"]
        
        for ext in pixel_extensions:
            matches = list(populated_bundle.rglob(f"*{ext}"))
            assert len(matches) == 0, f"Found pixel data files: {matches}"
    
    def test_detection_results_no_phi_text(self, populated_bundle: Path):
        """Detection results should not contain recovered PHI text."""
        detection_path = populated_bundle / "DECISIONS" / "detection_results.jsonl"
        
        if detection_path.stat().st_size > 0:
            content = detection_path.read_text()
            for line in content.strip().split("\n"):
                if line:
                    record = json.loads(line)
                    # Should NOT have a "text" field
                    assert "text" not in record, "Detection result contains PHI text!"
                    assert "ocr_text" not in record, "Detection result contains PHI text!"
                    assert "extracted_text" not in record, "Detection result contains PHI text!"
    
    def test_source_hashes_present(self, populated_bundle: Path):
        """Source hashes should be present (Model B backbone)."""
        hashes_path = populated_bundle / "INPUT" / "source_hashes.csv"
        assert hashes_path.exists()
        
        content = hashes_path.read_text()
        assert "source_pixel_hash" in content or "sha256" in content


# =============================================================================
# Completeness Tests (Gate 3 Core)
# =============================================================================

class TestAuditCompleteness:
    """Gate 3 completeness checks."""
    
    def test_coverage_completeness(self, populated_bundle: Path):
        """Counts in MANIFEST should match actual file contents."""
        manifest = json.loads((populated_bundle / "MANIFEST.json").read_text())
        counts = manifest["counts"]
        
        # Count source hashes
        source_hashes_path = populated_bundle / "INPUT" / "source_hashes.csv"
        with open(source_hashes_path) as f:
            reader = csv.DictReader(f)
            source_count = sum(1 for _ in reader)
        
        assert counts["instances_in"] == source_count
    
    def test_decision_completeness(self, populated_bundle: Path):
        """Every processed instance should have a decision record."""
        # Load decision log
        decision_path = populated_bundle / "DECISIONS" / "decision_log.jsonl"
        decisions = []
        content = decision_path.read_text().strip()
        if content:
            for line in content.split("\n"):
                if line:
                    decisions.append(json.loads(line))
        
        # Each decision should have source_sop_uid
        for decision in decisions:
            assert "source_sop_uid" in decision
            assert "decision_type" in decision
    
    def test_linkage_completeness(self, populated_bundle: Path):
        """Instance linkage should map source to masked."""
        linkage_path = populated_bundle / "LINKAGE" / "instance_linkage.csv"
        
        with open(linkage_path) as f:
            reader = csv.DictReader(f)
            for row in reader:
                assert row.get("source_sop_uid") or row.get("source_study_uid")
                # masked_sop_uid may be None for skipped instances
    
    def test_config_completeness(self, populated_bundle: Path):
        """Config files should exist and have required fields."""
        # profile.json
        profile = json.loads((populated_bundle / "CONFIG" / "profile.json").read_text())
        assert "compliance_profile" in profile
        
        # app_build.json
        build = json.loads((populated_bundle / "CONFIG" / "app_build.json").read_text())
        assert "voxelmask_version" in build


# =============================================================================
# Bundle Tree Validation
# =============================================================================

class TestBundleTree:
    """Tests for SIGNATURE/bundle_tree.txt."""
    
    def test_bundle_tree_exists(self, empty_bundle: Path):
        """bundle_tree.txt should exist."""
        tree_path = empty_bundle / "SIGNATURE" / "bundle_tree.txt"
        assert tree_path.exists()
    
    def test_bundle_tree_sorted(self, empty_bundle: Path):
        """bundle_tree.txt should be sorted by path."""
        tree_path = empty_bundle / "SIGNATURE" / "bundle_tree.txt"
        content = tree_path.read_text().strip()
        lines = content.split("\n")
        
        paths = [line.split()[0] for line in lines if line]
        assert paths == sorted(paths), "bundle_tree.txt is not sorted"


# =============================================================================
# Run Tests
# =============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
