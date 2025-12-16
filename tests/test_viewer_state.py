"""
Tests for Phase 6 Viewer State Module
=====================================

Tests ordering logic and manifest consumption for viewer.

GOVERNANCE: These tests verify presentation-only behavior.
Export ordering is tested separately in test_gate1_*.py
"""

import pytest
from dataclasses import dataclass
from typing import Optional

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from viewer_state import (
    ViewerInstance,
    ViewerSeries,
    ViewerStudyState,
    ViewerOrderingMethod,
    SeriesOrderingMethod,
    build_viewer_state,
    parse_ordered_series_manifest,
    parse_baseline_manifest_series_order,
    get_instance_ordering_label,
    get_series_ordering_label,
)


# ═══════════════════════════════════════════════════════════════════════════════
# FIXTURES
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class MockFileBuffer:
    """Mock file buffer for testing."""
    name: str
    
    def getbuffer(self):
        return b""


def make_mock_file(name: str) -> MockFileBuffer:
    """Create a mock file buffer."""
    return MockFileBuffer(name=name)


def make_file_info_cache(entries: list) -> dict:
    """
    Create file_info_cache from list of entry dicts.
    
    Each entry: {
        'filename': str,
        'sop_instance_uid': str,
        'series_instance_uid': str,
        'instance_number': int,
        'modality': str,
        ...
    }
    """
    cache = {}
    for entry in entries:
        filename = entry.get('filename', f"file_{len(cache)}.dcm")
        cache[filename] = {
            'sop_instance_uid': entry.get('sop_instance_uid', 'UNKNOWN'),
            'series_instance_uid': entry.get('series_instance_uid', 'UNKNOWN'),
            'instance_number': entry.get('instance_number'),
            'acquisition_time': entry.get('acquisition_time'),
            'modality': entry.get('modality', 'US'),
            'series_desc': entry.get('series_desc', 'Test Series'),
            'series_number': entry.get('series_number'),
            'temp_path': entry.get('temp_path', f'/tmp/{filename}'),
        }
    return cache


# ═══════════════════════════════════════════════════════════════════════════════
# TEST: ORDERED_INDEX FROM MANIFEST TAKES PRIORITY
# ═══════════════════════════════════════════════════════════════════════════════

class TestOrderedManifestPriority:
    """Test that ordered_series_manifest.json is used when available."""
    
    def test_uses_ordered_index_when_present(self):
        """Instances should be sorted by ordered_index from manifest."""
        # Files in non-sequential order
        files = [
            make_mock_file('file_c.dcm'),
            make_mock_file('file_a.dcm'),
            make_mock_file('file_b.dcm'),
        ]
        
        # Cache with instance numbers in different order
        cache = make_file_info_cache([
            {'filename': 'file_c.dcm', 'sop_instance_uid': 'SOP_C', 
             'series_instance_uid': 'SERIES_1', 'instance_number': 30},
            {'filename': 'file_a.dcm', 'sop_instance_uid': 'SOP_A',
             'series_instance_uid': 'SERIES_1', 'instance_number': 10},
            {'filename': 'file_b.dcm', 'sop_instance_uid': 'SOP_B',
             'series_instance_uid': 'SERIES_1', 'instance_number': 20},
        ])
        
        # Manifest defines different order (B, C, A)
        ordered_manifest = {
            'entries': [
                {'series_instance_uid': 'SERIES_1', 'sop_instance_uid': 'SOP_B', 'ordered_index': 1},
                {'series_instance_uid': 'SERIES_1', 'sop_instance_uid': 'SOP_C', 'ordered_index': 2},
                {'series_instance_uid': 'SERIES_1', 'sop_instance_uid': 'SOP_A', 'ordered_index': 3},
            ]
        }
        
        state = build_viewer_state(
            preview_files=files,
            file_info_cache=cache,
            ordered_series_manifest=ordered_manifest,
        )
        
        # Should have one series
        assert len(state.series_list) == 1
        series = state.series_list[0]
        
        # Should use ordered manifest method
        assert series.ordering_method == ViewerOrderingMethod.ORDERED_MANIFEST
        
        # Order should be: B, C, A (from manifest)
        assert len(series.instances) == 3
        assert series.instances[0].sop_instance_uid == 'SOP_B'
        assert series.instances[1].sop_instance_uid == 'SOP_C'
        assert series.instances[2].sop_instance_uid == 'SOP_A'
        
        # Stack positions should be 1, 2, 3
        assert series.instances[0].stack_position == 1
        assert series.instances[1].stack_position == 2
        assert series.instances[2].stack_position == 3
    
    def test_falls_back_to_instance_number_when_no_manifest(self):
        """Without manifest, should sort by instance_number."""
        files = [
            make_mock_file('file_c.dcm'),
            make_mock_file('file_a.dcm'),
            make_mock_file('file_b.dcm'),
        ]
        
        cache = make_file_info_cache([
            {'filename': 'file_c.dcm', 'sop_instance_uid': 'SOP_C',
             'series_instance_uid': 'SERIES_1', 'instance_number': 30},
            {'filename': 'file_a.dcm', 'sop_instance_uid': 'SOP_A',
             'series_instance_uid': 'SERIES_1', 'instance_number': 10},
            {'filename': 'file_b.dcm', 'sop_instance_uid': 'SOP_B',
             'series_instance_uid': 'SERIES_1', 'instance_number': 20},
        ])
        
        state = build_viewer_state(
            preview_files=files,
            file_info_cache=cache,
            ordered_series_manifest=None,  # No manifest
        )
        
        series = state.series_list[0]
        
        # Should use instance_number method
        assert series.ordering_method == ViewerOrderingMethod.INSTANCE_NUMBER
        
        # Order should be: A (10), B (20), C (30)
        assert series.instances[0].sop_instance_uid == 'SOP_A'
        assert series.instances[1].sop_instance_uid == 'SOP_B'
        assert series.instances[2].sop_instance_uid == 'SOP_C'


# ═══════════════════════════════════════════════════════════════════════════════
# TEST: SERIES ORDER FROM BASELINE MANIFEST
# ═══════════════════════════════════════════════════════════════════════════════

class TestSeriesOrderFromBaseline:
    """Test that series are ordered by baseline_order_manifest first occurrence."""
    
    def test_uses_baseline_first_seen_when_present(self):
        """Series should be sorted by first occurrence in baseline manifest."""
        # Files from two series, interleaved
        files = [
            make_mock_file('s2_img1.dcm'),  # Series 2
            make_mock_file('s1_img1.dcm'),  # Series 1
            make_mock_file('s2_img2.dcm'),  # Series 2
        ]
        
        cache = make_file_info_cache([
            {'filename': 's2_img1.dcm', 'sop_instance_uid': 'S2_I1',
             'series_instance_uid': 'SERIES_2', 'instance_number': 1},
            {'filename': 's1_img1.dcm', 'sop_instance_uid': 'S1_I1',
             'series_instance_uid': 'SERIES_1', 'instance_number': 1},
            {'filename': 's2_img2.dcm', 'sop_instance_uid': 'S2_I2',
             'series_instance_uid': 'SERIES_2', 'instance_number': 2},
        ])
        
        # Baseline manifest says SERIES_1 appeared first (file_index 1)
        baseline_manifest = {
            'entries': [
                {'series_instance_uid': 'SERIES_1', 'file_index': 1},
                {'series_instance_uid': 'SERIES_2', 'file_index': 5},
            ]
        }
        
        state = build_viewer_state(
            preview_files=files,
            file_info_cache=cache,
            baseline_order_manifest=baseline_manifest,
        )
        
        # Should use baseline ordering
        assert state.series_ordering_method == SeriesOrderingMethod.BASELINE_MANIFEST
        
        # SERIES_1 should come first (lower file_index in baseline)
        assert len(state.series_list) == 2
        assert state.series_list[0].series_instance_uid == 'SERIES_1'
        assert state.series_list[1].series_instance_uid == 'SERIES_2'
    
    def test_falls_back_to_series_number_when_no_baseline(self):
        """Without baseline, should sort by series_number."""
        files = [
            make_mock_file('s99_img1.dcm'),
            make_mock_file('s01_img1.dcm'),
        ]
        
        cache = make_file_info_cache([
            {'filename': 's99_img1.dcm', 'sop_instance_uid': 'S99_I1',
             'series_instance_uid': 'SERIES_99', 'instance_number': 1,
             'series_number': 99},
            {'filename': 's01_img1.dcm', 'sop_instance_uid': 'S01_I1',
             'series_instance_uid': 'SERIES_01', 'instance_number': 1,
             'series_number': 1},
        ])
        
        state = build_viewer_state(
            preview_files=files,
            file_info_cache=cache,
            baseline_order_manifest=None,
        )
        
        # Should use discovery order (with series_number sorting)
        assert state.series_ordering_method == SeriesOrderingMethod.DISCOVERY_ORDER
        
        # Series 1 should come before Series 99
        assert state.series_list[0].series_instance_uid == 'SERIES_01'
        assert state.series_list[1].series_instance_uid == 'SERIES_99'


# ═══════════════════════════════════════════════════════════════════════════════
# TEST: FALLBACK ORDERING
# ═══════════════════════════════════════════════════════════════════════════════

class TestFallbackOrdering:
    """Test fallback ordering when primary keys are missing."""
    
    def test_acquisition_time_fallback(self):
        """Should fall back to acquisition_time when instance_number missing."""
        files = [
            make_mock_file('img_late.dcm'),
            make_mock_file('img_early.dcm'),
            make_mock_file('img_mid.dcm'),
        ]
        
        cache = make_file_info_cache([
            {'filename': 'img_late.dcm', 'sop_instance_uid': 'LATE',
             'series_instance_uid': 'SERIES_1', 'instance_number': None,
             'acquisition_time': '150000.000'},
            {'filename': 'img_early.dcm', 'sop_instance_uid': 'EARLY',
             'series_instance_uid': 'SERIES_1', 'instance_number': None,
             'acquisition_time': '090000.000'},
            {'filename': 'img_mid.dcm', 'sop_instance_uid': 'MID',
             'series_instance_uid': 'SERIES_1', 'instance_number': None,
             'acquisition_time': '120000.000'},
        ])
        
        state = build_viewer_state(
            preview_files=files,
            file_info_cache=cache,
        )
        
        series = state.series_list[0]
        
        # Should use acquisition_time method
        assert series.ordering_method == ViewerOrderingMethod.ACQUISITION_TIME
        
        # Order should be: EARLY, MID, LATE
        assert series.instances[0].sop_instance_uid == 'EARLY'
        assert series.instances[1].sop_instance_uid == 'MID'
        assert series.instances[2].sop_instance_uid == 'LATE'
    
    def test_filename_fallback_last_resort(self):
        """Should fall back to filename when all else missing."""
        files = [
            make_mock_file('zebra.dcm'),
            make_mock_file('alpha.dcm'),
            make_mock_file('middle.dcm'),
        ]
        
        cache = make_file_info_cache([
            {'filename': 'zebra.dcm', 'sop_instance_uid': 'ZEBRA',
             'series_instance_uid': 'SERIES_1', 'instance_number': None,
             'acquisition_time': None},
            {'filename': 'alpha.dcm', 'sop_instance_uid': 'ALPHA',
             'series_instance_uid': 'SERIES_1', 'instance_number': None,
             'acquisition_time': None},
            {'filename': 'middle.dcm', 'sop_instance_uid': 'MIDDLE',
             'series_instance_uid': 'SERIES_1', 'instance_number': None,
             'acquisition_time': None},
        ])
        
        state = build_viewer_state(
            preview_files=files,
            file_info_cache=cache,
        )
        
        series = state.series_list[0]
        
        # Should use filename method (last resort)
        assert series.ordering_method == ViewerOrderingMethod.FILENAME
        
        # Order should be alphabetical: alpha, middle, zebra
        assert series.instances[0].sop_instance_uid == 'ALPHA'
        assert series.instances[1].sop_instance_uid == 'MIDDLE'
        assert series.instances[2].sop_instance_uid == 'ZEBRA'


# ═══════════════════════════════════════════════════════════════════════════════
# TEST: VIEWER SERIES PROPERTIES
# ═══════════════════════════════════════════════════════════════════════════════

class TestViewerSeriesProperties:
    """Test ViewerSeries computed properties."""
    
    def test_display_label_format(self):
        """Display label should include series number, icon, description, count."""
        series = ViewerSeries(
            series_instance_uid='TEST_SERIES',
            modality='US',
            series_description='Obstetric 3rd Trimester',
            series_number=1,
            instances=[
                ViewerInstance(
                    file_index=i, filename=f'f{i}.dcm', temp_path=f'/tmp/f{i}.dcm',
                    sop_instance_uid=f'SOP_{i}', series_instance_uid='TEST_SERIES',
                    instance_number=i, acquisition_time=None,
                    modality='US', series_description='Test',
                ) for i in range(5)
            ],
        )
        
        label = series.display_label
        
        # Should contain series number
        assert 'S001' in label
        # Should contain US icon
        assert '🔊' in label
        # Should contain count
        assert '(5)' in label
    
    def test_is_image_modality_true_for_imaging(self):
        """is_image_modality should return True for imaging modalities."""
        imaging_modalities = ['US', 'CT', 'MR', 'DX', 'CR', 'MG', 'XA', 'RF', 'NM', 'PT']
        
        for mod in imaging_modalities:
            series = ViewerSeries(
                series_instance_uid='TEST',
                modality=mod,
                series_description='Test',
            )
            assert series.is_image_modality is True, f"{mod} should be image modality"
    
    def test_is_image_modality_false_for_documents(self):
        """is_image_modality should return False for document modalities."""
        doc_modalities = ['SC', 'OT', 'DOC', 'SR']
        
        for mod in doc_modalities:
            series = ViewerSeries(
                series_instance_uid='TEST',
                modality=mod,
                series_description='Test',
            )
            assert series.is_image_modality is False, f"{mod} should not be image modality"


# ═══════════════════════════════════════════════════════════════════════════════
# TEST: VIEWER STUDY STATE NAVIGATION
# ═══════════════════════════════════════════════════════════════════════════════

class TestViewerStudyStateNavigation:
    """Test ViewerStudyState navigation methods."""
    
    def make_test_state(self) -> ViewerStudyState:
        """Create a test state with 2 series, 3 instances each."""
        def make_instances(series_uid: str, count: int):
            return [
                ViewerInstance(
                    file_index=i, filename=f'{series_uid}_{i}.dcm',
                    temp_path=f'/tmp/{series_uid}_{i}.dcm',
                    sop_instance_uid=f'{series_uid}_SOP_{i}',
                    series_instance_uid=series_uid,
                    instance_number=i+1, acquisition_time=None,
                    modality='US', series_description='Test',
                    stack_position=i+1,
                ) for i in range(count)
            ]
        
        return ViewerStudyState(
            series_list=[
                ViewerSeries(
                    series_instance_uid='SERIES_1', modality='US',
                    series_description='Series 1', series_number=1,
                    instances=make_instances('S1', 3),
                ),
                ViewerSeries(
                    series_instance_uid='SERIES_2', modality='CT',
                    series_description='Series 2', series_number=2,
                    instances=make_instances('S2', 3),
                ),
            ],
        )
    
    def test_select_series_resets_instance(self):
        """Selecting a series should reset instance index to 0."""
        state = self.make_test_state()
        state.selected_instance_idx = 2  # At last instance
        
        state.select_series(1)  # Select second series
        
        assert state.selected_series_idx == 1
        assert state.selected_instance_idx == 0
    
    def test_next_instance_moves_forward(self):
        """next_instance should move to next instance."""
        state = self.make_test_state()
        state.selected_instance_idx = 0
        
        result = state.next_instance()
        
        assert result is True
        assert state.selected_instance_idx == 1
    
    def test_next_instance_at_end_returns_false(self):
        """next_instance at end of series should return False."""
        state = self.make_test_state()
        state.selected_instance_idx = 2  # Last instance (0-indexed)
        
        result = state.next_instance()
        
        assert result is False
        assert state.selected_instance_idx == 2  # Unchanged
    
    def test_prev_instance_moves_backward(self):
        """prev_instance should move to previous instance."""
        state = self.make_test_state()
        state.selected_instance_idx = 2
        
        result = state.prev_instance()
        
        assert result is True
        assert state.selected_instance_idx == 1
    
    def test_prev_instance_at_start_returns_false(self):
        """prev_instance at start should return False."""
        state = self.make_test_state()
        state.selected_instance_idx = 0
        
        result = state.prev_instance()
        
        assert result is False
        assert state.selected_instance_idx == 0


# ═══════════════════════════════════════════════════════════════════════════════
# TEST: NON-IMAGE FILTERING
# ═══════════════════════════════════════════════════════════════════════════════

class TestNonImageFiltering:
    """Test filtering of non-image modalities (OT/SC)."""
    
    def make_mixed_state(self) -> ViewerStudyState:
        """Create state with imaging and document series."""
        return ViewerStudyState(
            series_list=[
                ViewerSeries(
                    series_instance_uid='US_SERIES', modality='US',
                    series_description='Ultrasound', series_number=1,
                ),
                ViewerSeries(
                    series_instance_uid='OT_SERIES', modality='OT',
                    series_description='Worksheet', series_number=99,
                ),
                ViewerSeries(
                    series_instance_uid='CT_SERIES', modality='CT',
                    series_description='CT Head', series_number=2,
                ),
            ],
        )
    
    def test_default_hides_non_image(self):
        """Default filter should hide OT/SC modalities."""
        state = self.make_mixed_state()
        
        # Default: show_non_image_objects = False
        assert state.show_non_image_objects is False
        
        filtered = state.filtered_series_list
        
        # Should only have US and CT
        assert len(filtered) == 2
        assert all(s.modality in {'US', 'CT'} for s in filtered)
    
    def test_toggle_shows_all(self):
        """Toggling filter should show all modalities."""
        state = self.make_mixed_state()
        
        state.toggle_non_image_filter()
        
        assert state.show_non_image_objects is True
        
        filtered = state.filtered_series_list
        
        # Should have all 3 series
        assert len(filtered) == 3
    
    def test_summary_counts_hidden(self):
        """Summary should report hidden series count."""
        state = self.make_mixed_state()
        
        summary = state.get_summary()
        
        assert summary['total_series'] == 3
        assert summary['filtered_series'] == 2
        assert summary['hidden_series'] == 1


# ═══════════════════════════════════════════════════════════════════════════════
# TEST: MANIFEST PARSING
# ═══════════════════════════════════════════════════════════════════════════════

class TestManifestParsing:
    """Test manifest parsing functions."""
    
    def test_parse_ordered_series_manifest(self):
        """Should parse ordered_series_manifest to lookup table."""
        manifest = {
            'entries': [
                {'series_instance_uid': 'S1', 'sop_instance_uid': 'SOP_A', 'ordered_index': 1},
                {'series_instance_uid': 'S1', 'sop_instance_uid': 'SOP_B', 'ordered_index': 2},
                {'series_instance_uid': 'S2', 'sop_instance_uid': 'SOP_C', 'ordered_index': 1},
            ]
        }
        
        lookup = parse_ordered_series_manifest(manifest)
        
        assert lookup[('S1', 'SOP_A')] == 1
        assert lookup[('S1', 'SOP_B')] == 2
        assert lookup[('S2', 'SOP_C')] == 1
    
    def test_parse_baseline_manifest_series_order(self):
        """Should parse baseline manifest for series first occurrence."""
        manifest = {
            'entries': [
                {'series_instance_uid': 'S1', 'file_index': 5},
                {'series_instance_uid': 'S2', 'file_index': 1},
                {'series_instance_uid': 'S1', 'file_index': 10},  # Second occurrence, ignored
            ]
        }
        
        first_seen = parse_baseline_manifest_series_order(manifest)
        
        assert first_seen['S1'] == 5  # First occurrence
        assert first_seen['S2'] == 1


# ═══════════════════════════════════════════════════════════════════════════════
# TEST: PROVENANCE LABELS
# ═══════════════════════════════════════════════════════════════════════════════

class TestProvenanceLabels:
    """Test provenance display helpers."""
    
    def test_instance_ordering_labels(self):
        """Should return appropriate icons and descriptions."""
        icon, desc = get_instance_ordering_label(ViewerOrderingMethod.ORDERED_MANIFEST)
        assert icon == '✅'
        assert 'manifest' in desc.lower()
        
        icon, desc = get_instance_ordering_label(ViewerOrderingMethod.FILENAME)
        assert icon == '⚠️'
        assert 'filename' in desc.lower()
    
    def test_series_ordering_labels(self):
        """Should return appropriate icons and descriptions."""
        icon, desc = get_series_ordering_label(SeriesOrderingMethod.BASELINE_MANIFEST)
        assert icon == '✅'
        assert 'manifest' in desc.lower()
