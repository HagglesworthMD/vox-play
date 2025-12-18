"""
Phase 6 — Viewer Index Generator
=================================

Generates viewer_index.json for HTML export viewers.

This is a PRESENTATION-ONLY artefact. It does NOT:
- Modify exported DICOM files
- Restructure series or instance relationships
- Validate file existence on disk
- Infer multi-frame behavior

The index is a pure data transformation of ordered entries.

═══════════════════════════════════════════════════════════════════════════════
GOVERNANCE RULES — Phase 6 HTML Viewer
═══════════════════════════════════════════════════════════════════════════════

DO NOT:
- Reorder instances (use entries as-is)
- Read files from disk
- Check for PNG/JPEG existence
- Infer multi-frame behavior
- Use words: "structure", "hierarchy", "original order", "complete"

DO:
- Treat ordered_entries as authoritative
- Include ordering_source in output
- Show both instance_number (DICOM) and display_index (presentation)
- Handle missing fields gracefully with explicit defaults

═══════════════════════════════════════════════════════════════════════════════
"""

from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional, Any
from collections import OrderedDict
import json
import logging

logger = logging.getLogger(__name__)

# ═══════════════════════════════════════════════════════════════════════════════
# CONSTANTS
# ═══════════════════════════════════════════════════════════════════════════════

SCHEMA_VERSION = "1.0.0"

# Modalities considered "imaging" for filter purposes
IMAGE_MODALITIES = frozenset({
    "US", "CT", "MR", "DX", "CR", "MG", "XA", "RF", "NM", "PT",
    "OPT", "OP", "ES", "ECG", "IO", "PX", "GM", "SM", "XC",
})

# Modalities considered "documents" (hidden by default in viewer)
DOCUMENT_MODALITIES = frozenset({
    "OT", "SC", "SR", "DOC", "PR", "KO",
})


# ═══════════════════════════════════════════════════════════════════════════════
# DATA STRUCTURES
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class ViewerIndexInstance:
    """Single instance entry in viewer index."""
    
    file_path: str                    # Relative path within export
    sop_instance_uid: str             # DICOM SOPInstanceUID
    instance_number: Optional[int]    # DICOM InstanceNumber (may be None)
    display_index: int                # 1-indexed position in this series view
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "file_path": self.file_path,
            "sop_instance_uid": self.sop_instance_uid,
            "instance_number": self.instance_number,
            "display_index": self.display_index,
        }


@dataclass
class ViewerIndexSeries:
    """Series entry in viewer index."""
    
    series_uid: str
    series_number: Optional[int]
    series_description: str
    modality: str
    is_image_modality: bool
    instances: List[ViewerIndexInstance] = field(default_factory=list)
    
    @property
    def instance_count(self) -> int:
        return len(self.instances)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "series_uid": self.series_uid,
            "series_number": self.series_number,
            "series_description": self.series_description,
            "modality": self.modality,
            "is_image_modality": self.is_image_modality,
            "instance_count": self.instance_count,
            "instances": [inst.to_dict() for inst in self.instances],
        }


@dataclass
class ViewerIndex:
    """Complete viewer index structure."""
    
    schema_version: str
    generated_at: str
    study_uid: Optional[str]
    total_instances: int
    series: List[ViewerIndexSeries]
    ordering_source: str
    note: str = "Presentation-only index. Display order matches export manifest."
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "generated_at": self.generated_at,
            "study_uid": self.study_uid,
            "total_instances": self.total_instances,
            "series": [s.to_dict() for s in self.series],
            "ordering_source": self.ordering_source,
            "note": self.note,
        }
    
    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent)

    def to_js(self, indent: int = 2) -> str:
        """
        Convert to browser-compatible JavaScript global.
        Used for file:// protocol support where fetch() is restricted.
        """
        # GOVERNANCE: Use exact same JSON content, just wrapped in global assignment
        json_content = self.to_json(indent=indent)
        return f"window.VOXELMASK_VIEWER_INDEX = {json_content};"


# Type alias for entry dict (from export manifest)
ViewerIndexEntry = Dict[str, Any]


# ═══════════════════════════════════════════════════════════════════════════════
# MAIN GENERATOR
# ═══════════════════════════════════════════════════════════════════════════════

def generate_viewer_index(
    ordered_entries: List[ViewerIndexEntry],
    *,
    ordering_source: str,
    study_uid: Optional[str] = None,
    output_path: Optional[Path] = None,
) -> ViewerIndex:
    """
    Generate viewer index from ordered export entries.
    
    This is a pure data transformation. Entries are NOT validated
    against filesystem. Order is preserved as-is from input.
    
    Args:
        ordered_entries: List of entry dicts from export manifest.
            Each entry should contain:
            - file_path or relative_path (str): Path within export
            - sop_instance_uid (str): DICOM SOPInstanceUID
            - series_instance_uid (str): DICOM SeriesInstanceUID
            - series_number (int, optional): DICOM SeriesNumber
            - series_description (str, optional): DICOM SeriesDescription
            - modality (str): DICOM Modality
            - instance_number (int, optional): DICOM InstanceNumber
        
        ordering_source: Human-readable description of ordering origin.
            Examples: "export_order_manifest", "gate1_ordered_series_manifest"
        
        study_uid: Optional StudyInstanceUID for the study.
        
        output_path: Optional path to write viewer_index.json.
            If provided, writes JSON to this path.
    
    Returns:
        ViewerIndex object containing the complete index structure.
    
    Note:
        - Instance order within each series matches input order (stable)
        - Series order matches first occurrence in input (stable)
        - Missing fields are handled with explicit defaults
        - This function does NOT read from disk or validate files
    """
    if not ordered_entries:
        logger.warning("generate_viewer_index called with empty entries")
        return ViewerIndex(
            schema_version=SCHEMA_VERSION,
            generated_at=datetime.now().isoformat(),
            study_uid=study_uid,
            total_instances=0,
            series=[],
            ordering_source=ordering_source,
        )
    
    # Group entries by series, preserving order
    series_map: OrderedDict[str, ViewerIndexSeries] = OrderedDict()
    
    for entry in ordered_entries:
        series_uid = _get_required(entry, 'series_instance_uid', 'UNKNOWN_SERIES')
        
        if series_uid not in series_map:
            modality = _get_optional(entry, 'modality', 'UNK')
            series_map[series_uid] = ViewerIndexSeries(
                series_uid=series_uid,
                series_number=_get_optional_int(entry, 'series_number'),
                series_description=_get_optional(entry, 'series_description', 'Unknown Series'),
                modality=modality,
                is_image_modality=modality.upper() in IMAGE_MODALITIES,
            )
        
        # Get file path (support both naming conventions)
        file_path = entry.get('file_path') or entry.get('relative_path') or 'unknown.dcm'
        
        # Create instance entry
        instance = ViewerIndexInstance(
            file_path=file_path,
            sop_instance_uid=_get_required(entry, 'sop_instance_uid', 'UNKNOWN_SOP'),
            instance_number=_get_optional_int(entry, 'instance_number'),
            display_index=len(series_map[series_uid].instances) + 1,  # 1-indexed
        )
        
        series_map[series_uid].instances.append(instance)
    
    # Build final index
    series_list = list(series_map.values())
    total_instances = sum(s.instance_count for s in series_list)
    
    index = ViewerIndex(
        schema_version=SCHEMA_VERSION,
        generated_at=datetime.now().isoformat(),
        study_uid=study_uid,
        total_instances=total_instances,
        series=series_list,
        ordering_source=ordering_source,
    )
    
    logger.info(
        f"Generated viewer index: {len(series_list)} series, "
        f"{total_instances} instances, source={ordering_source}"
    )
    
    # Write to files if path provided
    if output_path is not None:
        out_dir = Path(output_path)
        
        # 1. Write standard JSON (for machine-readability)
        json_file = out_dir / "viewer_index.json"
        with open(json_file, 'w', encoding='utf-8') as f:
            f.write(index.to_json())
        logger.info(f"Wrote viewer index to {json_file}")
        
        # 2. Write JS Global (for file:// protocol support)
        # GOVERNANCE: viewer.html expects this exact filename
        js_file = out_dir / "viewer_index.js"
        with open(js_file, 'w', encoding='utf-8') as f:
            f.write(index.to_js())
        logger.info(f"Wrote viewer index JS to {js_file}")
    
    return index


# ═══════════════════════════════════════════════════════════════════════════════
# HELPERS
# ═══════════════════════════════════════════════════════════════════════════════

def _get_required(entry: Dict, key: str, default: str) -> str:
    """Get required string field with fallback default."""
    value = entry.get(key)
    if value is None or value == '':
        return default
    return str(value)


def _get_optional(entry: Dict, key: str, default: str) -> str:
    """Get optional string field with fallback default."""
    value = entry.get(key)
    if value is None or value == '':
        return default
    return str(value)


def _get_optional_int(entry: Dict, key: str) -> Optional[int]:
    """Get optional integer field, returning None if missing or invalid."""
    value = entry.get(key)
    if value is None:
        return None
    try:
        return int(value)
    except (ValueError, TypeError):
        return None


# ═══════════════════════════════════════════════════════════════════════════════
# VALIDATION HELPERS (for tests)
# ═══════════════════════════════════════════════════════════════════════════════

def validate_viewer_index(index: ViewerIndex) -> List[str]:
    """
    Validate viewer index structure.
    
    Returns list of validation errors (empty if valid).
    """
    errors = []
    
    # Required top-level fields
    if not index.schema_version:
        errors.append("Missing schema_version")
    if not index.generated_at:
        errors.append("Missing generated_at")
    if not index.ordering_source:
        errors.append("Missing ordering_source")
    
    # Validate series
    for i, series in enumerate(index.series):
        prefix = f"series[{i}]"
        
        if not series.series_uid:
            errors.append(f"{prefix}: Missing series_uid")
        if not series.modality:
            errors.append(f"{prefix}: Missing modality")
        
        # Validate instances within series
        for j, inst in enumerate(series.instances):
            inst_prefix = f"{prefix}.instances[{j}]"
            
            if not inst.file_path:
                errors.append(f"{inst_prefix}: Missing file_path")
            
            # GOVERNANCE: Absolute paths break relocatability
            if inst.file_path.startswith("/") or inst.file_path.startswith("\\") or (len(inst.file_path) > 1 and inst.file_path[1] == ":"):
                 errors.append(f"{inst_prefix}: Absolute path disallowed: {inst.file_path}")
            if not inst.sop_instance_uid:
                errors.append(f"{inst_prefix}: Missing sop_instance_uid")
            if inst.display_index < 1:
                errors.append(f"{inst_prefix}: Invalid display_index ({inst.display_index})")
    
    return errors
