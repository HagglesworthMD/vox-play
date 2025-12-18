"""
Phase 6: Viewer-Only State Management
=====================================

GOVERNANCE BOUNDARY:
This module is PRESENTATION-ONLY. It does NOT affect:
- Audit logs
- Evidence bundles
- Export ordering (uses Gate 1 manifests at export time)
- Series/instance structure on disk
- Processing behavior

All ordering here is for UI display only. Export paths MUST NOT
reference these structures.

Ordering Sources (in priority order):
1. ordered_series_manifest.json → ordered_index (when available)
2. InstanceNumber (0020,0013)
3. AcquisitionTime / ContentTime
4. Filename (last resort, logs warning)

Series Order:
1. First occurrence in baseline_order_manifest.json (when available)
2. Discovery order from file loading

Author: VoxelMask Engineering
Phase: 6 — Viewer UX Hardening
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple
from enum import Enum
import logging

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════════════
# ORDERING PROVENANCE
# ═══════════════════════════════════════════════════════════════════════════════

class ViewerOrderingMethod(Enum):
    """
    Provenance tracking for viewer display order.
    
    Displayed in UI for transparency. Helps reviewers understand
    why images appear in a particular order.
    """
    ORDERED_MANIFEST = "ORDERED_MANIFEST"  # Gate 1 ordered_series_manifest
    INSTANCE_NUMBER = "INSTANCE_NUMBER"    # DICOM (0020,0013)
    ACQUISITION_TIME = "ACQUISITION_TIME"  # DICOM AcquisitionTime/ContentTime
    FILENAME = "FILENAME"                  # Last resort (warning logged)


class SeriesOrderingMethod(Enum):
    """Provenance tracking for series list order."""
    BASELINE_MANIFEST = "BASELINE_MANIFEST"  # Gate 1 baseline first occurrence
    DISCOVERY_ORDER = "DISCOVERY_ORDER"      # Order files were loaded


# ═══════════════════════════════════════════════════════════════════════════════
# VIEWER INSTANCE (Single image in stack)
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class ViewerInstance:
    """
    Single displayable instance in the viewer stack.
    
    Presentation-only wrapper. The underlying file and all
    processing metadata remain unchanged.
    
    Note: temp_path points to run-scoped viewer_cache (Phase 12),
    NOT to ephemeral /tmp files. This ensures paths survive the
    entire review session.
    """
    
    # Pointer to source (read-only)
    file_index: int        # Index into preview_files list
    filename: str
    temp_path: str         # Run-scoped path in viewer_cache/ (survives session)
    
    # DICOM identifiers (read-only)
    sop_instance_uid: str
    series_instance_uid: str
    
    # DICOM ordering keys (read-only)
    instance_number: Optional[int]    # (0020,0013)
    acquisition_time: Optional[str]   # AcquisitionTime or ContentTime
    
    # Display metadata (read-only)
    modality: str
    series_description: str
    
    # Gate 1 ordering (if manifest available)
    ordered_index: Optional[int] = None  # From ordered_series_manifest
    
    # Display position (1-indexed for UI, set after sorting)
    stack_position: int = 0


# ═══════════════════════════════════════════════════════════════════════════════
# VIEWER SERIES (Group of instances)
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass  
class ViewerSeries:
    """
    Grouped instances for a single DICOM series.
    
    Presentation-only. SeriesInstanceUID is the grouping key.
    Instances are ordered by Gate 1 ordered_index when available,
    otherwise by instance_number.
    """
    series_instance_uid: str
    modality: str
    series_description: str
    series_number: Optional[int] = None  # (0020,0011) for PACS-style labels
    
    # Ordered instances (sorted by ordered_index or instance_number)
    instances: List[ViewerInstance] = field(default_factory=list)
    
    # First occurrence in baseline manifest (for series ordering)
    baseline_first_seen: Optional[int] = None
    
    # Ordering provenance
    ordering_method: ViewerOrderingMethod = ViewerOrderingMethod.INSTANCE_NUMBER
    
    @property
    def count(self) -> int:
        return len(self.instances)
    
    @property
    def display_label(self) -> str:
        """
        Human-readable label for series browser.
        
        Format: S{num} • {icon} {desc} ({count})
        Example: S001 • 🔊 Obstetric (45)
        """
        mod_icon = {
            'US': '🔊',
            'CT': '🩻',
            'MR': '🧲',
            'SC': '📋',
            'OT': '📄',
            'DX': '📷',
            'CR': '📷',
            'MG': '🔬',
            'XA': '💓',
            'RF': '📺',
            'NM': '☢️',
            'PT': '☢️',
        }.get(self.modality, '🖼')
        
        # Series number prefix
        if self.series_number is not None:
            series_prefix = f"S{str(self.series_number).zfill(3)}"
        else:
            series_prefix = "S???"
        
        # Truncate long descriptions
        desc = self.series_description or 'Unknown'
        if len(desc) > 20:
            desc = desc[:17] + '...'
        
        return f"{series_prefix} • {mod_icon} {desc} ({self.count})"
    
    @property
    def is_image_modality(self) -> bool:
        """
        Check if this series contains imaging modality (vs documents).
        
        Used for default filtering in viewer.
        """
        return self.modality in {'US', 'CT', 'MR', 'DX', 'CR', 'MG', 'XA', 'RF', 'NM', 'PT'}


# ═══════════════════════════════════════════════════════════════════════════════
# VIEWER STUDY STATE (Top-level navigation)
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class ViewerStudyState:
    """
    Top-level viewer navigation state.
    
    Stored in st.session_state.viewer_state
    """
    series_list: List[ViewerSeries] = field(default_factory=list)
    
    # Navigation state
    selected_series_idx: int = 0
    selected_instance_idx: int = 0
    
    # Filter state
    show_non_image_objects: bool = False  # Default: hide OT/SC
    
    # Ordering provenance
    series_ordering_method: SeriesOrderingMethod = SeriesOrderingMethod.DISCOVERY_ORDER
    
    @property
    def filtered_series_list(self) -> List[ViewerSeries]:
        """
        Get series list with current filter applied.
        
        Default: only image modalities (US, CT, MR, etc.)
        When show_non_image_objects=True: include OT, SC, etc.
        """
        if self.show_non_image_objects:
            return self.series_list
        return [s for s in self.series_list if s.is_image_modality]
    
    @property
    def selected_series(self) -> Optional[ViewerSeries]:
        """Get currently selected series."""
        filtered = self.filtered_series_list
        if 0 <= self.selected_series_idx < len(filtered):
            return filtered[self.selected_series_idx]
        return None
    
    @property
    def selected_instance(self) -> Optional[ViewerInstance]:
        """Get currently selected instance."""
        series = self.selected_series
        if series and 0 <= self.selected_instance_idx < len(series.instances):
            return series.instances[self.selected_instance_idx]
        return None
    
    def select_series(self, idx: int) -> None:
        """Select series and reset instance to first."""
        filtered = self.filtered_series_list
        if 0 <= idx < len(filtered):
            self.selected_series_idx = idx
            self.selected_instance_idx = 0
    
    def next_instance(self) -> bool:
        """Move to next instance. Returns True if moved."""
        series = self.selected_series
        if series and self.selected_instance_idx < len(series.instances) - 1:
            self.selected_instance_idx += 1
            return True
        return False
    
    def prev_instance(self) -> bool:
        """Move to previous instance. Returns True if moved."""
        if self.selected_instance_idx > 0:
            self.selected_instance_idx -= 1
            return True
        return False
    
    def goto_instance(self, idx: int) -> None:
        """Jump to specific instance (0-indexed)."""
        series = self.selected_series
        if series and 0 <= idx < len(series.instances):
            self.selected_instance_idx = idx
    
    def toggle_non_image_filter(self) -> None:
        """Toggle showing non-image objects (OT/SC)."""
        self.show_non_image_objects = not self.show_non_image_objects
        # Reset selection to avoid out-of-bounds
        self.selected_series_idx = 0
        self.selected_instance_idx = 0
    
    def get_summary(self) -> Dict[str, int]:
        """Get summary counts for display."""
        all_series = self.series_list
        filtered = self.filtered_series_list
        
        total_instances = sum(s.count for s in all_series)
        filtered_instances = sum(s.count for s in filtered)
        
        return {
            'total_series': len(all_series),
            'filtered_series': len(filtered),
            'total_instances': total_instances,
            'filtered_instances': filtered_instances,
            'hidden_series': len(all_series) - len(filtered),
        }


# ═══════════════════════════════════════════════════════════════════════════════
# MANIFEST PARSING
# ═══════════════════════════════════════════════════════════════════════════════

def parse_ordered_series_manifest(manifest: Dict) -> Dict[Tuple[str, str], int]:
    """
    Parse ordered_series_manifest.json into lookup table.
    
    Args:
        manifest: Parsed JSON from ordered_series_manifest.json
        
    Returns:
        Dict mapping (series_instance_uid, sop_instance_uid) → ordered_index
    """
    lookup = {}
    
    entries = manifest.get('entries', [])
    for entry in entries:
        series_uid = entry.get('series_instance_uid', '')
        sop_uid = entry.get('sop_instance_uid', '')
        ordered_idx = entry.get('ordered_index')
        
        if series_uid and sop_uid and ordered_idx is not None:
            lookup[(series_uid, sop_uid)] = ordered_idx
    
    return lookup


def parse_baseline_manifest_series_order(manifest: Dict) -> Dict[str, int]:
    """
    Parse baseline_order_manifest.json to get series first occurrence.
    
    Args:
        manifest: Parsed JSON from baseline_order_manifest.json
        
    Returns:
        Dict mapping series_instance_uid → first_seen_file_index
    """
    first_seen = {}
    
    entries = manifest.get('entries', [])
    for entry in entries:
        series_uid = entry.get('series_instance_uid', '')
        file_idx = entry.get('file_index')
        
        if series_uid and file_idx is not None:
            if series_uid not in first_seen:
                first_seen[series_uid] = file_idx
    
    return first_seen


# ═══════════════════════════════════════════════════════════════════════════════
# BUILDER FUNCTION
# ═══════════════════════════════════════════════════════════════════════════════

def build_viewer_state(
    preview_files: List,  # File buffers from app.py
    file_info_cache: Dict[str, Dict],  # Metadata cache from preflight
    ordered_series_manifest: Optional[Dict] = None,  # Gate 1 ordered manifest
    baseline_order_manifest: Optional[Dict] = None,  # Gate 1 baseline manifest
) -> ViewerStudyState:
    """
    Build ViewerStudyState from loaded files.
    
    Groups by SeriesInstanceUID, sorts instances by ordered_index (Gate 1)
    or instance_number (fallback).
    
    GOVERNANCE: This is presentation-only. Export uses Gate 1 manifests directly.
    
    Args:
        preview_files: List of file buffers to display
        file_info_cache: Dict mapping filename → metadata dict
        ordered_series_manifest: Optional parsed Gate 1 ordered manifest
        baseline_order_manifest: Optional parsed Gate 1 baseline manifest
        
    Returns:
        ViewerStudyState ready for navigation
    """
    from collections import OrderedDict
    
    # Parse manifests if provided
    ordered_lookup: Dict[Tuple[str, str], int] = {}
    series_first_seen: Dict[str, int] = {}
    
    if ordered_series_manifest:
        ordered_lookup = parse_ordered_series_manifest(ordered_series_manifest)
        logger.info(f"Loaded ordered_series_manifest with {len(ordered_lookup)} entries")
    
    if baseline_order_manifest:
        series_first_seen = parse_baseline_manifest_series_order(baseline_order_manifest)
        logger.info(f"Loaded baseline manifest with {len(series_first_seen)} series")
    
    # Group files by series
    series_map: OrderedDict[str, List[ViewerInstance]] = OrderedDict()
    series_meta: Dict[str, Dict] = {}
    
    for idx, f in enumerate(preview_files):
        info = file_info_cache.get(f.name, {})
        
        series_uid = info.get('series_instance_uid', 'UNKNOWN')
        sop_uid = info.get('sop_instance_uid', 'UNKNOWN')
        
        if series_uid not in series_map:
            series_map[series_uid] = []
            series_meta[series_uid] = {
                'modality': info.get('modality', 'UNK'),
                'series_desc': info.get('series_desc', 'Unknown'),
                'series_number': info.get('series_number'),
            }
        
        # Check for ordered_index from manifest
        ordered_idx = ordered_lookup.get((series_uid, sop_uid))
        
        instance = ViewerInstance(
            file_index=idx,
            filename=f.name,
            temp_path=info.get('temp_path', ''),
            sop_instance_uid=sop_uid,
            series_instance_uid=series_uid,
            instance_number=info.get('instance_number'),
            acquisition_time=info.get('acquisition_time'),
            modality=info.get('modality', 'UNK'),
            series_description=info.get('series_desc', 'Unknown'),
            ordered_index=ordered_idx,
            stack_position=0,  # Will be set after sorting
        )
        series_map[series_uid].append(instance)
    
    # Build series list with sorted instances
    series_list: List[ViewerSeries] = []
    
    for series_uid, instances in series_map.items():
        meta = series_meta[series_uid]
        
        # Determine ordering method and sort
        ordering_method, sorted_instances = _sort_instances(instances)
        
        # Assign stack positions (1-indexed for UI)
        for pos, inst in enumerate(sorted_instances, start=1):
            inst.stack_position = pos
        
        # Get baseline first-seen for series ordering
        baseline_first = series_first_seen.get(series_uid)
        
        series = ViewerSeries(
            series_instance_uid=series_uid,
            modality=meta['modality'],
            series_description=meta['series_desc'],
            series_number=meta.get('series_number'),
            instances=sorted_instances,
            baseline_first_seen=baseline_first,
            ordering_method=ordering_method,
        )
        series_list.append(series)
    
    # Sort series list
    series_ordering_method, sorted_series = _sort_series(series_list, series_first_seen)
    
    return ViewerStudyState(
        series_list=sorted_series,
        series_ordering_method=series_ordering_method,
    )


def _sort_instances(instances: List[ViewerInstance]) -> Tuple[ViewerOrderingMethod, List[ViewerInstance]]:
    """
    Sort instances using best available ordering key.
    
    Priority:
    1. ordered_index from Gate 1 manifest
    2. instance_number from DICOM
    3. acquisition_time from DICOM
    4. filename (last resort, logged)
    
    Returns:
        Tuple of (ordering_method, sorted_instances)
    """
    if not instances:
        return ViewerOrderingMethod.INSTANCE_NUMBER, []
    
    # Priority 1: ordered_index from Gate 1 manifest
    has_ordered_index = all(i.ordered_index is not None for i in instances)
    if has_ordered_index:
        sorted_instances = sorted(instances, key=lambda i: i.ordered_index)
        return ViewerOrderingMethod.ORDERED_MANIFEST, sorted_instances
    
    # Priority 2: instance_number
    has_instance_numbers = all(i.instance_number is not None for i in instances)
    if has_instance_numbers:
        sorted_instances = sorted(instances, key=lambda i: i.instance_number)
        return ViewerOrderingMethod.INSTANCE_NUMBER, sorted_instances
    
    # Priority 3: acquisition_time
    has_acquisition_times = all(i.acquisition_time is not None for i in instances)
    if has_acquisition_times:
        sorted_instances = sorted(instances, key=lambda i: i.acquisition_time)
        return ViewerOrderingMethod.ACQUISITION_TIME, sorted_instances
    
    # Priority 4: filename (last resort)
    logger.warning(
        f"Falling back to filename ordering for series with {len(instances)} instances. "
        "This may not be consistent across systems."
    )
    sorted_instances = sorted(instances, key=lambda i: i.filename)
    return ViewerOrderingMethod.FILENAME, sorted_instances


def _sort_series(
    series_list: List[ViewerSeries],
    series_first_seen: Dict[str, int],
) -> Tuple[SeriesOrderingMethod, List[ViewerSeries]]:
    """
    Sort series list using best available ordering.
    
    Priority:
    1. baseline_first_seen from Gate 1 manifest
    2. Discovery order (preserve current list order)
    
    Returns:
        Tuple of (ordering_method, sorted_series)
    """
    if not series_list:
        return SeriesOrderingMethod.DISCOVERY_ORDER, []
    
    # Check if we have baseline ordering for all series
    has_baseline = all(s.baseline_first_seen is not None for s in series_list)
    
    if has_baseline:
        sorted_series = sorted(series_list, key=lambda s: s.baseline_first_seen)
        return SeriesOrderingMethod.BASELINE_MANIFEST, sorted_series
    
    # Fall back to discovery order (already in OrderedDict order)
    # Sort by series_number if available, otherwise maintain order
    def sort_key(s: ViewerSeries):
        if s.series_number is not None:
            return (0, s.series_number, s.series_instance_uid)
        return (1, 0, s.series_instance_uid)
    
    sorted_series = sorted(series_list, key=sort_key)
    return SeriesOrderingMethod.DISCOVERY_ORDER, sorted_series


# ═══════════════════════════════════════════════════════════════════════════════
# PROVENANCE DISPLAY HELPERS
# ═══════════════════════════════════════════════════════════════════════════════

def get_instance_ordering_label(method: ViewerOrderingMethod) -> Tuple[str, str]:
    """
    Get human-readable label and icon for instance ordering method.
    
    Returns:
        Tuple of (icon, description)
    """
    labels = {
        ViewerOrderingMethod.ORDERED_MANIFEST: ("✅", "Order: Gate 1 manifest"),
        ViewerOrderingMethod.INSTANCE_NUMBER: ("✅", "Order: instance number"),
        ViewerOrderingMethod.ACQUISITION_TIME: ("ℹ️", "Order: acquisition time"),
        ViewerOrderingMethod.FILENAME: ("⚠️", "Order: filename (fallback)"),
    }
    return labels.get(method, ("❓", "Order: unknown"))


def get_series_ordering_label(method: SeriesOrderingMethod) -> Tuple[str, str]:
    """
    Get human-readable label for series ordering method.
    
    Returns:
        Tuple of (icon, description)
    """
    labels = {
        SeriesOrderingMethod.BASELINE_MANIFEST: ("✅", "Series order: source manifest"),
        SeriesOrderingMethod.DISCOVERY_ORDER: ("ℹ️", "Series order: discovery"),
    }
    return labels.get(method, ("❓", "Series order: unknown"))
