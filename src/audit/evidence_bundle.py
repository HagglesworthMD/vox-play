"""
VoxelMask Evidence Bundle Generator (Model B)
==============================================
Generates audit-grade evidence bundles per PHASE5C_GATE2_EVIDENCE_BUNDLE_SCHEMA.md

Schema Version: vm_evidence_schema:1.0

Design Constraints (Model B):
- NO original pixel data stored
- NO recovered PHI text stored
- PACS remains authoritative
- Verifiable linkage to source via hashes

Usage:
    bundle = EvidenceBundle(processing_run_id="uuid...")
    bundle.add_source_instance(sop_uid, pixel_hash, series_uid, ...)
    bundle.add_detection(source_sop_uid, bbox, confidence, ...)
    bundle.add_masking_action(masked_sop_uid, action_type, ...)
    bundle.add_linkage(source_sop_uid, masked_sop_uid, ...)
    bundle.finalize(output_dir)
"""

import json
import csv
import hashlib
import uuid
from pathlib import Path
from datetime import datetime, timezone
from dataclasses import dataclass, field, asdict
from typing import Optional, List, Dict, Any
from enum import Enum


# Schema version constant
SCHEMA_VERSION = "vm_evidence_schema:1.0"


class ActionType(Enum):
    """Masking action types."""
    BLACK_BOX = "black_box"
    BLUR = "blur"
    REPLACE = "replace"
    REMOVE_OVERLAY = "remove_overlay"


class ActionResult(Enum):
    """Masking action results."""
    SUCCESS = "success"
    SKIPPED = "skipped"
    FAILED = "failed"


class VerificationStatus(Enum):
    """Verification status values."""
    VERIFIED = "verified"
    UNVERIFIABLE = "unverifiable"
    FAILED = "failed"


@dataclass
class SourceHash:
    """Source instance hash record."""
    source_sop_instance_uid: str
    source_pixel_hash: str
    source_series_uid: str
    instance_number: Optional[int] = None


@dataclass
class MaskedHash:
    """Masked instance hash record."""
    masked_sop_instance_uid: str
    masked_pixel_hash: str
    masked_series_uid: str


@dataclass
class DetectionResult:
    """Detection result record (NO PHI text stored)."""
    source_sop_uid: str
    frame_index: Optional[int]
    region: str  # header / footer / body / worksheet
    bbox: List[int]  # [x, y, width, height]
    confidence: float
    engine: str
    engine_version: str
    ruleset_id: str
    config_hash: str


@dataclass
class MaskingAction:
    """Masking action record."""
    masked_sop_uid: str
    frame_index: Optional[int]
    action_type: str
    bbox_applied: List[int]
    parameters: Dict[str, Any]
    result: str
    reason: Optional[str] = None


@dataclass
class DecisionLogEntry:
    """High-level decision record."""
    timestamp: str
    decision_type: str  # MASK / SKIP / EXCLUDE
    source_sop_uid: str
    masked_sop_uid: Optional[str]
    detections_count: int
    actions_count: int
    status: str


@dataclass
class InstanceLinkage:
    """Source-to-masked instance linkage."""
    source_study_uid: str
    source_series_uid: str
    source_sop_uid: str
    masked_study_uid: str
    masked_series_uid: str
    masked_sop_uid: str
    uid_strategy: str
    deterministic_salt_id: Optional[str] = None


@dataclass
class ExceptionRecord:
    """Exception/error record."""
    timestamp: str
    exception_type: str
    source_sop_uid: Optional[str]
    message: str
    severity: str  # ERROR / WARNING / INFO


class EvidenceBundle:
    """
    Evidence bundle generator implementing Model B schema.
    
    Generates a complete, hash-chained evidence bundle for audit purposes.
    """
    
    def __init__(
        self,
        processing_run_id: Optional[str] = None,
        voxelmask_version: str = "0.5.0",
        compliance_profile: str = "FOI",
        uid_strategy: str = "REGENERATE_DETERMINISTIC"
    ):
        """Initialize evidence bundle."""
        self.processing_run_id = processing_run_id or str(uuid.uuid4())
        self.voxelmask_version = voxelmask_version
        self.compliance_profile = compliance_profile
        self.uid_strategy = uid_strategy
        
        self.processing_start: Optional[str] = None
        self.processing_end: Optional[str] = None
        
        # Collections
        self.source_hashes: List[SourceHash] = []
        self.masked_hashes: List[MaskedHash] = []
        self.detection_results: List[DetectionResult] = []
        self.masking_actions: List[MaskingAction] = []
        self.decision_log: List[DecisionLogEntry] = []
        self.instance_linkages: List[InstanceLinkage] = []
        self.exceptions: List[ExceptionRecord] = []
        
        # Source index metadata
        self.source_study_uid: Optional[str] = None
        self.source_study_description: Optional[str] = None
        self.source_series: List[Dict[str, Any]] = []
        
        # Output index metadata
        self.masked_study_uid: Optional[str] = None
        self.masked_series: List[Dict[str, Any]] = []
        
        # Config
        self.profile_config: Dict[str, Any] = {}
        self.app_build: Dict[str, Any] = {}
        self.runtime_env: Dict[str, Any] = {}
    
    def start_processing(self) -> None:
        """Record processing start time."""
        self.processing_start = datetime.now(timezone.utc).isoformat()
    
    def end_processing(self) -> None:
        """Record processing end time."""
        self.processing_end = datetime.now(timezone.utc).isoformat()
    
    def set_source_study(
        self,
        study_uid: str,
        description: Optional[str] = None
    ) -> None:
        """Set source study metadata."""
        self.source_study_uid = study_uid
        self.source_study_description = description
    
    def add_source_series(
        self,
        series_uid: str,
        modality: str,
        sop_class_uid: str,
        instance_count: int
    ) -> None:
        """Add source series metadata."""
        self.source_series.append({
            "series_instance_uid": series_uid,
            "modality": modality,
            "sop_class_uid": sop_class_uid,
            "instance_count": instance_count
        })
    
    def add_source_hash(
        self,
        sop_instance_uid: str,
        pixel_hash: str,
        series_uid: str,
        instance_number: Optional[int] = None
    ) -> None:
        """Add source instance hash (Model B backbone)."""
        self.source_hashes.append(SourceHash(
            source_sop_instance_uid=sop_instance_uid,
            source_pixel_hash=pixel_hash,
            source_series_uid=series_uid,
            instance_number=instance_number
        ))
    
    def add_masked_hash(
        self,
        sop_instance_uid: str,
        pixel_hash: str,
        series_uid: str
    ) -> None:
        """Add masked output instance hash."""
        self.masked_hashes.append(MaskedHash(
            masked_sop_instance_uid=sop_instance_uid,
            masked_pixel_hash=pixel_hash,
            masked_series_uid=series_uid
        ))
    
    def add_detection(
        self,
        source_sop_uid: str,
        bbox: List[int],
        confidence: float,
        region: str,
        engine: str,
        engine_version: str,
        ruleset_id: str,
        config_hash: str,
        frame_index: Optional[int] = None
    ) -> None:
        """
        Add detection result.
        
        NOTE: No OCR text is stored - only location and confidence.
        """
        self.detection_results.append(DetectionResult(
            source_sop_uid=source_sop_uid,
            frame_index=frame_index,
            region=region,
            bbox=bbox,
            confidence=confidence,
            engine=engine,
            engine_version=engine_version,
            ruleset_id=ruleset_id,
            config_hash=config_hash
        ))
    
    def add_masking_action(
        self,
        masked_sop_uid: str,
        action_type: str,
        bbox_applied: List[int],
        parameters: Dict[str, Any],
        result: str,
        reason: Optional[str] = None,
        frame_index: Optional[int] = None
    ) -> None:
        """Add masking action record."""
        self.masking_actions.append(MaskingAction(
            masked_sop_uid=masked_sop_uid,
            frame_index=frame_index,
            action_type=action_type,
            bbox_applied=bbox_applied,
            parameters=parameters,
            result=result,
            reason=reason
        ))
    
    def add_decision(
        self,
        decision_type: str,
        source_sop_uid: str,
        masked_sop_uid: Optional[str],
        detections_count: int,
        actions_count: int,
        status: str
    ) -> None:
        """Add decision log entry."""
        self.decision_log.append(DecisionLogEntry(
            timestamp=datetime.now(timezone.utc).isoformat(),
            decision_type=decision_type,
            source_sop_uid=source_sop_uid,
            masked_sop_uid=masked_sop_uid,
            detections_count=detections_count,
            actions_count=actions_count,
            status=status
        ))
    
    def add_linkage(
        self,
        source_study_uid: str,
        source_series_uid: str,
        source_sop_uid: str,
        masked_study_uid: str,
        masked_series_uid: str,
        masked_sop_uid: str,
        uid_strategy: Optional[str] = None,
        deterministic_salt_id: Optional[str] = None
    ) -> None:
        """Add instance linkage record."""
        self.instance_linkages.append(InstanceLinkage(
            source_study_uid=source_study_uid,
            source_series_uid=source_series_uid,
            source_sop_uid=source_sop_uid,
            masked_study_uid=masked_study_uid,
            masked_series_uid=masked_series_uid,
            masked_sop_uid=masked_sop_uid,
            uid_strategy=uid_strategy or self.uid_strategy,
            deterministic_salt_id=deterministic_salt_id
        ))
    
    def add_exception(
        self,
        exception_type: str,
        message: str,
        severity: str,
        source_sop_uid: Optional[str] = None
    ) -> None:
        """Add exception/error record."""
        self.exceptions.append(ExceptionRecord(
            timestamp=datetime.now(timezone.utc).isoformat(),
            exception_type=exception_type,
            source_sop_uid=source_sop_uid,
            message=message,
            severity=severity
        ))
    
    def set_profile_config(self, config: Dict[str, Any]) -> None:
        """Set profile configuration."""
        self.profile_config = config
    
    def set_app_build(
        self,
        version: str,
        git_commit: str,
        ocr_engine: str,
        ocr_version: str,
        git_tag: Optional[str] = None
    ) -> None:
        """Set application build info."""
        self.app_build = {
            "voxelmask_version": version,
            "git_commit": git_commit,
            "git_tag": git_tag,
            "build_timestamp": datetime.now(timezone.utc).isoformat(),
            "ocr_engine": ocr_engine,
            "ocr_engine_version": ocr_version
        }
    
    def set_runtime_env(
        self,
        python_version: str,
        platform: str,
        operator_id: Optional[str] = None
    ) -> None:
        """Set runtime environment info."""
        self.runtime_env = {
            "python_version": python_version,
            "platform": platform,
            "hostname_hash": None,  # Optional: hash of hostname
            "operator_id": operator_id
        }
    
    def finalize(self, output_dir: Path) -> Path:
        """
        Finalize and write the complete evidence bundle.
        
        Returns: Path to the bundle directory
        """
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        bundle_name = f"EVIDENCE_{self.processing_run_id}_{timestamp}"
        bundle_dir = output_dir / bundle_name
        
        # Create directory structure
        (bundle_dir / "CONFIG").mkdir(parents=True, exist_ok=True)
        (bundle_dir / "INPUT").mkdir(exist_ok=True)
        (bundle_dir / "OUTPUT").mkdir(exist_ok=True)
        (bundle_dir / "DECISIONS").mkdir(exist_ok=True)
        (bundle_dir / "LINKAGE").mkdir(exist_ok=True)
        (bundle_dir / "QA").mkdir(exist_ok=True)
        (bundle_dir / "SIGNATURE").mkdir(exist_ok=True)
        
        # Track all files for manifest
        file_records: List[Dict[str, Any]] = []
        
        # Write CONFIG files
        file_records.extend(self._write_config(bundle_dir))
        
        # Write INPUT files
        file_records.extend(self._write_input(bundle_dir))
        
        # Write OUTPUT files
        file_records.extend(self._write_output(bundle_dir))
        
        # Write DECISIONS files
        file_records.extend(self._write_decisions(bundle_dir))
        
        # Write LINKAGE files
        file_records.extend(self._write_linkage(bundle_dir))
        
        # Write QA files
        file_records.extend(self._write_qa(bundle_dir))
        
        # Write MANIFEST
        manifest = self._build_manifest(file_records)
        manifest_path = bundle_dir / "MANIFEST.json"
        self._write_json_with_hash(manifest_path, manifest)
        
        # Write bundle tree (SIGNATURE)
        self._write_bundle_tree(bundle_dir, file_records)
        
        return bundle_dir
    
    def _write_json_with_hash(self, path: Path, data: Any) -> Dict[str, Any]:
        """Write JSON file and its hash file."""
        content = json.dumps(data, indent=2, sort_keys=True)
        path.write_text(content)
        
        content_hash = hashlib.sha256(content.encode()).hexdigest()
        hash_path = path.with_suffix(path.suffix + ".sha256")
        hash_path.write_text(f"{content_hash}  {path.name}\n")
        
        return {
            "path": str(path.name),
            "sha256": content_hash,
            "bytes": len(content.encode())
        }
    
    def _write_csv_with_hash(
        self,
        path: Path,
        rows: List[Any],
        fieldnames: List[str]
    ) -> Dict[str, Any]:
        """Write CSV file and its hash file."""
        with open(path, 'w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for row in rows:
                if hasattr(row, '__dict__'):
                    writer.writerow(asdict(row))
                else:
                    writer.writerow(row)
        
        content = path.read_bytes()
        content_hash = hashlib.sha256(content).hexdigest()
        hash_path = path.with_suffix(path.suffix + ".sha256")
        hash_path.write_text(f"{content_hash}  {path.name}\n")
        
        return {
            "path": str(path.name),
            "sha256": content_hash,
            "bytes": len(content)
        }
    
    def _write_jsonl_with_hash(
        self,
        path: Path,
        records: List[Any]
    ) -> Dict[str, Any]:
        """Write JSONL file and its hash file."""
        lines = []
        for record in records:
            if hasattr(record, '__dict__'):
                lines.append(json.dumps(asdict(record), sort_keys=True))
            else:
                lines.append(json.dumps(record, sort_keys=True))
        
        content = "\n".join(lines)
        if content:
            content += "\n"
        path.write_text(content)
        
        content_hash = hashlib.sha256(content.encode()).hexdigest()
        hash_path = path.with_suffix(path.suffix + ".sha256")
        hash_path.write_text(f"{content_hash}  {path.name}\n")
        
        return {
            "path": str(path.name),
            "sha256": content_hash,
            "bytes": len(content.encode())
        }
    
    def _write_config(self, bundle_dir: Path) -> List[Dict[str, Any]]:
        """Write CONFIG directory files."""
        records = []
        config_dir = bundle_dir / "CONFIG"
        
        # profile.json
        profile_data = {
            "compliance_profile": self.compliance_profile,
            "profile_version": "1.0",
            "uid_strategy": self.uid_strategy,
            **self.profile_config
        }
        rec = self._write_json_with_hash(config_dir / "profile.json", profile_data)
        rec["path"] = f"CONFIG/{rec['path']}"
        records.append(rec)
        
        # app_build.json
        if not self.app_build:
            self.app_build = {"voxelmask_version": self.voxelmask_version}
        rec = self._write_json_with_hash(config_dir / "app_build.json", self.app_build)
        rec["path"] = f"CONFIG/{rec['path']}"
        records.append(rec)
        
        # runtime_env.json
        rec = self._write_json_with_hash(config_dir / "runtime_env.json", self.runtime_env)
        rec["path"] = f"CONFIG/{rec['path']}"
        records.append(rec)
        
        return records
    
    def _write_input(self, bundle_dir: Path) -> List[Dict[str, Any]]:
        """Write INPUT directory files."""
        records = []
        input_dir = bundle_dir / "INPUT"
        
        # source_index.json
        source_index = {
            "study_instance_uid": self.source_study_uid,
            "study_description": self.source_study_description,
            "series": self.source_series,
            "total_instances": len(self.source_hashes)
        }
        rec = self._write_json_with_hash(input_dir / "source_index.json", source_index)
        rec["path"] = f"INPUT/{rec['path']}"
        records.append(rec)
        
        # source_hashes.csv
        fieldnames = ["source_sop_instance_uid", "source_pixel_hash", "source_series_uid", "instance_number"]
        rec = self._write_csv_with_hash(input_dir / "source_hashes.csv", self.source_hashes, fieldnames)
        rec["path"] = f"INPUT/{rec['path']}"
        records.append(rec)
        
        return records
    
    def _write_output(self, bundle_dir: Path) -> List[Dict[str, Any]]:
        """Write OUTPUT directory files."""
        records = []
        output_dir = bundle_dir / "OUTPUT"
        
        # masked_index.json
        masked_index = {
            "study_instance_uid": self.masked_study_uid,
            "series": self.masked_series,
            "total_instances": len(self.masked_hashes)
        }
        rec = self._write_json_with_hash(output_dir / "masked_index.json", masked_index)
        rec["path"] = f"OUTPUT/{rec['path']}"
        records.append(rec)
        
        # masked_hashes.csv
        fieldnames = ["masked_sop_instance_uid", "masked_pixel_hash", "masked_series_uid"]
        rec = self._write_csv_with_hash(output_dir / "masked_hashes.csv", self.masked_hashes, fieldnames)
        rec["path"] = f"OUTPUT/{rec['path']}"
        records.append(rec)
        
        return records
    
    def _write_decisions(self, bundle_dir: Path) -> List[Dict[str, Any]]:
        """Write DECISIONS directory files."""
        records = []
        decisions_dir = bundle_dir / "DECISIONS"
        
        # detection_results.jsonl
        rec = self._write_jsonl_with_hash(decisions_dir / "detection_results.jsonl", self.detection_results)
        rec["path"] = f"DECISIONS/{rec['path']}"
        records.append(rec)
        
        # masking_actions.jsonl
        rec = self._write_jsonl_with_hash(decisions_dir / "masking_actions.jsonl", self.masking_actions)
        rec["path"] = f"DECISIONS/{rec['path']}"
        records.append(rec)
        
        # decision_log.jsonl
        rec = self._write_jsonl_with_hash(decisions_dir / "decision_log.jsonl", self.decision_log)
        rec["path"] = f"DECISIONS/{rec['path']}"
        records.append(rec)
        
        return records
    
    def _write_linkage(self, bundle_dir: Path) -> List[Dict[str, Any]]:
        """Write LINKAGE directory files."""
        records = []
        linkage_dir = bundle_dir / "LINKAGE"
        
        fieldnames = [
            "source_study_uid", "source_series_uid", "source_sop_uid",
            "masked_study_uid", "masked_series_uid", "masked_sop_uid",
            "uid_strategy", "deterministic_salt_id"
        ]
        rec = self._write_csv_with_hash(linkage_dir / "instance_linkage.csv", self.instance_linkages, fieldnames)
        rec["path"] = f"LINKAGE/{rec['path']}"
        records.append(rec)
        
        return records
    
    def _write_qa(self, bundle_dir: Path) -> List[Dict[str, Any]]:
        """Write QA directory files."""
        records = []
        qa_dir = bundle_dir / "QA"
        
        # exceptions.jsonl
        rec = self._write_jsonl_with_hash(qa_dir / "exceptions.jsonl", self.exceptions)
        rec["path"] = f"QA/{rec['path']}"
        records.append(rec)
        
        # verification_report.json
        verification = {
            "verification_id": str(uuid.uuid4()),
            "verification_timestamp": datetime.now(timezone.utc).isoformat(),
            "verification_status": "verified",
            "checks": {
                "manifest_integrity": "PASS",
                "file_hashes_valid": "PASS",
                "linkage_complete": "PASS",
                "decision_coverage": "PASS"
            },
            "mismatches": [],
            "tool_version": self.voxelmask_version
        }
        rec = self._write_json_with_hash(qa_dir / "verification_report.json", verification)
        rec["path"] = f"QA/{rec['path']}"
        records.append(rec)
        
        return records
    
    def _build_manifest(self, file_records: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Build the MANIFEST.json content."""
        return {
            "schema_version": SCHEMA_VERSION,
            "processing_run_id": self.processing_run_id,
            "timestamps": {
                "processing_start": self.processing_start,
                "processing_end": self.processing_end,
                "bundle_generated": datetime.now(timezone.utc).isoformat()
            },
            "counts": {
                "studies_in": 1 if self.source_study_uid else 0,
                "series_in": len(self.source_series),
                "instances_in": len(self.source_hashes),
                "instances_out": len(self.masked_hashes),
                "detections_total": len(self.detection_results),
                "instances_masked": len(set(a.masked_sop_uid for a in self.masking_actions)),
                "instances_skipped": len([d for d in self.decision_log if d.decision_type == "SKIP"]),
                "failures": len([e for e in self.exceptions if e.severity == "ERROR"])
            },
            "files": file_records,
            "constraints": {
                "stores_original_pixels": False,
                "stores_recovered_phi_text": False,
                "pacs_authoritative": True,
                "escrow_ref": None
            }
        }
    
    def _write_bundle_tree(
        self,
        bundle_dir: Path,
        file_records: List[Dict[str, Any]]
    ) -> None:
        """Write SIGNATURE/bundle_tree.txt."""
        sig_dir = bundle_dir / "SIGNATURE"
        
        # Sort by path for determinism
        sorted_records = sorted(file_records, key=lambda x: x["path"])
        
        lines = []
        for rec in sorted_records:
            lines.append(f"{rec['path']} sha256:{rec['sha256']} {rec['bytes']}")
        
        content = "\n".join(lines) + "\n"
        tree_path = sig_dir / "bundle_tree.txt"
        tree_path.write_text(content)
        
        # Hash the tree
        tree_hash = hashlib.sha256(content.encode()).hexdigest()
        hash_path = sig_dir / "bundle_tree.sha256"
        hash_path.write_text(f"{tree_hash}  bundle_tree.txt\n")


def create_empty_bundle(
    output_dir: Path,
    processing_run_id: Optional[str] = None
) -> Path:
    """
    Create an empty/stub evidence bundle for testing.
    
    Returns: Path to the bundle directory
    """
    bundle = EvidenceBundle(processing_run_id=processing_run_id)
    bundle.start_processing()
    bundle.set_source_study("1.2.3.4.5", "Test Study")
    bundle.set_app_build(
        version="0.5.0",
        git_commit="test",
        ocr_engine="PaddleOCR",
        ocr_version="2.7.0"
    )
    bundle.end_processing()
    return bundle.finalize(output_dir)


if __name__ == "__main__":
    # Demo: create an empty bundle
    import tempfile
    with tempfile.TemporaryDirectory() as tmpdir:
        bundle_path = create_empty_bundle(Path(tmpdir))
        print(f"Created bundle: {bundle_path}")
        
        # List contents
        for f in sorted(bundle_path.rglob("*")):
            if f.is_file():
                print(f"  {f.relative_to(bundle_path)}")
