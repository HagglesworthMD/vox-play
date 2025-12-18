"""
Tests for Phase 6 Viewer Index Generator
=========================================

Tests the viewer_index.py module for correct index generation.

GOVERNANCE: These tests verify presentation-only index generation.
They do NOT test filesystem operations or DICOM reading.
"""

import pytest
import json
from datetime import datetime
from pathlib import Path

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from export.viewer_index import (
    generate_viewer_index,
    validate_viewer_index,
    ViewerIndex,
    ViewerIndexSeries,
    ViewerIndexInstance,
    SCHEMA_VERSION,
    IMAGE_MODALITIES,
    DOCUMENT_MODALITIES,
)


# ═══════════════════════════════════════════════════════════════════════════════
# FIXTURES
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.fixture
def sample_entries():
    """Sample export manifest entries for testing."""
    return [
        # Series 1: US images (3 instances)
        {
            'file_path': 'US_S001/IMG_0001.dcm',
            'sop_instance_uid': '1.2.3.SOP.001',
            'series_instance_uid': '1.2.3.SERIES.001',
            'series_number': 1,
            'series_description': 'Obstetric 3rd Trimester',
            'modality': 'US',
            'instance_number': 1,
        },
        {
            'file_path': 'US_S001/IMG_0002.dcm',
            'sop_instance_uid': '1.2.3.SOP.002',
            'series_instance_uid': '1.2.3.SERIES.001',
            'series_number': 1,
            'series_description': 'Obstetric 3rd Trimester',
            'modality': 'US',
            'instance_number': 2,
        },
        {
            'file_path': 'US_S001/IMG_0003.dcm',
            'sop_instance_uid': '1.2.3.SOP.003',
            'series_instance_uid': '1.2.3.SERIES.001',
            'series_number': 1,
            'series_description': 'Obstetric 3rd Trimester',
            'modality': 'US',
            'instance_number': 3,
        },
        # Series 2: OT document (1 instance)
        {
            'file_path': 'OT_S099/DOC_0001.dcm',
            'sop_instance_uid': '1.2.3.SOP.099',
            'series_instance_uid': '1.2.3.SERIES.099',
            'series_number': 99,
            'series_description': 'Vue RIS Scanned Documents',
            'modality': 'OT',
            'instance_number': 1,
        },
    ]


@pytest.fixture
def minimal_entry():
    """Minimal entry with only required fields."""
    return {
        'sop_instance_uid': '1.2.3.MINIMAL',
        'series_instance_uid': '1.2.3.SERIES.MIN',
        'modality': 'US',
    }


# ═══════════════════════════════════════════════════════════════════════════════
# TEST: INDEX GENERATION BASICS
# ═══════════════════════════════════════════════════════════════════════════════

class TestViewerIndexGeneration:
    """Test basic index generation functionality."""
    
    def test_generates_valid_index(self, sample_entries):
        """Should generate a valid ViewerIndex from entries."""
        index = generate_viewer_index(
            sample_entries,
            ordering_source='test_manifest',
        )
        
        assert index is not None
        assert isinstance(index, ViewerIndex)
        assert index.schema_version == SCHEMA_VERSION
        assert index.ordering_source == 'test_manifest'
    
    def test_preserves_entry_order(self, sample_entries):
        """Instances should appear in same order as input entries."""
        index = generate_viewer_index(
            sample_entries,
            ordering_source='test',
        )
        
        # First series should have 3 instances in order
        series1 = index.series[0]
        assert series1.instance_count == 3
        assert series1.instances[0].file_path == 'US_S001/IMG_0001.dcm'
        assert series1.instances[1].file_path == 'US_S001/IMG_0002.dcm'
        assert series1.instances[2].file_path == 'US_S001/IMG_0003.dcm'
    
    def test_display_index_is_one_indexed(self, sample_entries):
        """display_index should start at 1, not 0."""
        index = generate_viewer_index(
            sample_entries,
            ordering_source='test',
        )
        
        series1 = index.series[0]
        assert series1.instances[0].display_index == 1
        assert series1.instances[1].display_index == 2
        assert series1.instances[2].display_index == 3
    
    def test_groups_by_series_uid(self, sample_entries):
        """Should group entries by series_instance_uid."""
        index = generate_viewer_index(
            sample_entries,
            ordering_source='test',
        )
        
        assert len(index.series) == 2
        assert index.series[0].series_uid == '1.2.3.SERIES.001'
        assert index.series[1].series_uid == '1.2.3.SERIES.099'
    
    def test_series_order_matches_first_occurrence(self):
        """Series should appear in order of first occurrence in entries."""
        # Interleaved entries: S2 first, then S1, then S2 again
        entries = [
            {'sop_instance_uid': 'SOP_S2_1', 'series_instance_uid': 'S2', 'modality': 'US'},
            {'sop_instance_uid': 'SOP_S1_1', 'series_instance_uid': 'S1', 'modality': 'US'},
            {'sop_instance_uid': 'SOP_S2_2', 'series_instance_uid': 'S2', 'modality': 'US'},
        ]
        
        index = generate_viewer_index(entries, ordering_source='test')
        
        # S2 should come first (first occurrence)
        assert index.series[0].series_uid == 'S2'
        assert index.series[1].series_uid == 'S1'
        
        # S2 should have both its instances
        assert index.series[0].instance_count == 2
    
    def test_total_instances_correct(self, sample_entries):
        """total_instances should equal sum of all instance counts."""
        index = generate_viewer_index(
            sample_entries,
            ordering_source='test',
        )
        
        assert index.total_instances == 4
    
    def test_empty_entries_returns_empty_index(self):
        """Empty entries should produce empty but valid index."""
        index = generate_viewer_index(
            [],
            ordering_source='empty_test',
        )
        
        assert index is not None
        assert index.total_instances == 0
        assert index.series == []
        assert index.ordering_source == 'empty_test'


# ═══════════════════════════════════════════════════════════════════════════════
# TEST: MODALITY CLASSIFICATION
# ═══════════════════════════════════════════════════════════════════════════════

class TestModalityClassification:
    """Test is_image_modality classification."""
    
    def test_us_is_image_modality(self, sample_entries):
        """US modality should be classified as image."""
        index = generate_viewer_index(sample_entries, ordering_source='test')
        
        us_series = index.series[0]
        assert us_series.modality == 'US'
        assert us_series.is_image_modality is True
    
    def test_ot_is_not_image_modality(self, sample_entries):
        """OT modality should NOT be classified as image."""
        index = generate_viewer_index(sample_entries, ordering_source='test')
        
        ot_series = index.series[1]
        assert ot_series.modality == 'OT'
        assert ot_series.is_image_modality is False
    
    def test_all_image_modalities_classified_correctly(self):
        """All image modalities should have is_image_modality=True."""
        for modality in ['US', 'CT', 'MR', 'DX', 'CR', 'MG', 'XA', 'RF']:
            entries = [{'sop_instance_uid': f'SOP_{modality}', 
                       'series_instance_uid': f'S_{modality}', 
                       'modality': modality}]
            index = generate_viewer_index(entries, ordering_source='test')
            
            assert index.series[0].is_image_modality is True, f"{modality} should be image"
    
    def test_all_document_modalities_classified_correctly(self):
        """All document modalities should have is_image_modality=False."""
        for modality in ['OT', 'SC', 'SR', 'DOC']:
            entries = [{'sop_instance_uid': f'SOP_{modality}', 
                       'series_instance_uid': f'S_{modality}', 
                       'modality': modality}]
            index = generate_viewer_index(entries, ordering_source='test')
            
            assert index.series[0].is_image_modality is False, f"{modality} should be document"


# ═══════════════════════════════════════════════════════════════════════════════
# TEST: MISSING FIELD HANDLING
# ═══════════════════════════════════════════════════════════════════════════════

class TestMissingFieldHandling:
    """Test graceful handling of missing or incomplete entries."""
    
    def test_missing_file_path_uses_default(self):
        """Missing file_path should use 'unknown.dcm'."""
        entries = [{
            'sop_instance_uid': 'SOP_1',
            'series_instance_uid': 'S_1',
            'modality': 'US',
            # No file_path
        }]
        
        index = generate_viewer_index(entries, ordering_source='test')
        
        assert index.series[0].instances[0].file_path == 'unknown.dcm'
    
    def test_missing_series_description_uses_default(self):
        """Missing series_description should use 'Unknown Series'."""
        entries = [{
            'sop_instance_uid': 'SOP_1',
            'series_instance_uid': 'S_1',
            'modality': 'US',
            # No series_description
        }]
        
        index = generate_viewer_index(entries, ordering_source='test')
        
        assert index.series[0].series_description == 'Unknown Series'
    
    def test_missing_instance_number_is_none(self):
        """Missing instance_number should be None, not default."""
        entries = [{
            'sop_instance_uid': 'SOP_1',
            'series_instance_uid': 'S_1',
            'modality': 'US',
            # No instance_number
        }]
        
        index = generate_viewer_index(entries, ordering_source='test')
        
        assert index.series[0].instances[0].instance_number is None
    
    def test_missing_series_number_is_none(self):
        """Missing series_number should be None."""
        entries = [{
            'sop_instance_uid': 'SOP_1',
            'series_instance_uid': 'S_1',
            'modality': 'US',
            # No series_number
        }]
        
        index = generate_viewer_index(entries, ordering_source='test')
        
        assert index.series[0].series_number is None
    
    def test_supports_relative_path_key(self):
        """Should accept 'relative_path' as alternative to 'file_path'."""
        entries = [{
            'relative_path': 'alt/path/file.dcm',
            'sop_instance_uid': 'SOP_1',
            'series_instance_uid': 'S_1',
            'modality': 'US',
        }]
        
        index = generate_viewer_index(entries, ordering_source='test')
        
        assert index.series[0].instances[0].file_path == 'alt/path/file.dcm'


# ═══════════════════════════════════════════════════════════════════════════════
# TEST: JSON SERIALIZATION
# ═══════════════════════════════════════════════════════════════════════════════

class TestJSONSerialization:
    """Test JSON output format."""
    
    def test_to_json_produces_valid_json(self, sample_entries):
        """to_json should produce parseable JSON."""
        index = generate_viewer_index(sample_entries, ordering_source='test')
        
        json_str = index.to_json()
        
        # Should parse without error
        parsed = json.loads(json_str)
        assert isinstance(parsed, dict)
    
    def test_json_contains_required_keys(self, sample_entries):
        """JSON output should contain all required top-level keys."""
        index = generate_viewer_index(sample_entries, ordering_source='test')
        
        parsed = json.loads(index.to_json())
        
        assert 'schema_version' in parsed
        assert 'generated_at' in parsed
        assert 'total_instances' in parsed
        assert 'series' in parsed
        assert 'ordering_source' in parsed
        assert 'note' in parsed
    
    def test_json_series_contains_required_keys(self, sample_entries):
        """Each series in JSON should contain required keys."""
        index = generate_viewer_index(sample_entries, ordering_source='test')
        
        parsed = json.loads(index.to_json())
        series = parsed['series'][0]
        
        assert 'series_uid' in series
        assert 'series_number' in series
        assert 'series_description' in series
        assert 'modality' in series
        assert 'is_image_modality' in series
        assert 'instance_count' in series
        assert 'instances' in series
    
    def test_json_instance_contains_required_keys(self, sample_entries):
        """Each instance in JSON should contain required keys."""
        index = generate_viewer_index(sample_entries, ordering_source='test')
        
        parsed = json.loads(index.to_json())
        instance = parsed['series'][0]['instances'][0]
        
        assert 'file_path' in instance
        assert 'sop_instance_uid' in instance
        assert 'instance_number' in instance
        assert 'display_index' in instance

    def test_to_js_produces_valid_assignment(self, sample_entries):
        """to_js should produce a valid JavaScript global assignment."""
        index = generate_viewer_index(sample_entries, ordering_source='test')
        
        js_str = index.to_js()
        
        # Check for assignment prefix
        assert js_str.startswith('window.VOXELMASK_VIEWER_INDEX = ')
        assert js_str.endswith(';')
        
        # Extract and parse JSON part
        json_part = js_str[len('window.VOXELMASK_VIEWER_INDEX = '):-1]
        parsed = json.loads(json_part)
        assert parsed['total_instances'] == 4


# ═══════════════════════════════════════════════════════════════════════════════
# TEST: VALIDATION
# ═══════════════════════════════════════════════════════════════════════════════

class TestValidation:
    """Test index validation."""
    
    def test_valid_index_has_no_errors(self, sample_entries):
        """Valid index should produce empty error list."""
        index = generate_viewer_index(sample_entries, ordering_source='test')
        
        errors = validate_viewer_index(index)
        
        assert errors == []
    
    def test_missing_schema_version_detected(self):
        """Missing schema_version should be flagged."""
        index = ViewerIndex(
            schema_version='',  # Empty
            generated_at=datetime.now().isoformat(),
            study_uid=None,
            total_instances=0,
            series=[],
            ordering_source='test',
        )
        
        errors = validate_viewer_index(index)
        
        assert any('schema_version' in e for e in errors)
    
    def test_missing_ordering_source_detected(self):
        """Missing ordering_source should be flagged."""
        index = ViewerIndex(
            schema_version=SCHEMA_VERSION,
            generated_at=datetime.now().isoformat(),
            study_uid=None,
            total_instances=0,
            series=[],
            ordering_source='',  # Empty
        )
        
        errors = validate_viewer_index(index)
        
        assert any('ordering_source' in e for e in errors)

    def test_absolute_path_detected_as_error(self):
        """Absolute file_paths should be flagged as errors."""
        index = ViewerIndex(
            schema_version=SCHEMA_VERSION,
            generated_at=datetime.now().isoformat(),
            study_uid=None,
            total_instances=0,
            series=[ViewerIndexSeries(
                series_uid='S1', series_number=1, series_description='desc',
                modality='US', is_image_modality=True,
                instances=[ViewerIndexInstance(
                    file_path='/absolute/path.dcm',
                    sop_instance_uid='1.2.3',
                    instance_number=1,
                    display_index=1
                )]
            )],
            ordering_source='test',
        )
        
        errors = validate_viewer_index(index)
        assert any('Absolute path' in e for e in errors)


# ═══════════════════════════════════════════════════════════════════════════════
# TEST: ORDERING SOURCE PRESERVATION
# ═══════════════════════════════════════════════════════════════════════════════

class TestOrderingSourcePreservation:
    """Test that ordering_source is correctly preserved."""
    
    def test_ordering_source_in_output(self, sample_entries):
        """ordering_source should appear in output unchanged."""
        index = generate_viewer_index(
            sample_entries,
            ordering_source='gate1_ordered_series_manifest',
        )
        
        assert index.ordering_source == 'gate1_ordered_series_manifest'
    
    def test_ordering_source_in_json(self, sample_entries):
        """ordering_source should appear in JSON output."""
        index = generate_viewer_index(
            sample_entries,
            ordering_source='export_order_manifest',
        )
        
        parsed = json.loads(index.to_json())
        
        assert parsed['ordering_source'] == 'export_order_manifest'


# ═══════════════════════════════════════════════════════════════════════════════
# TEST: FILE WRITING (Optional)
# ═══════════════════════════════════════════════════════════════════════════════

class TestFileWriting:
    """Test optional file writing functionality."""
    
    def test_writes_to_output_path(self, sample_entries, tmp_path):
        """Should write viewer_index.json when output_path provided."""
        generate_viewer_index(
            sample_entries,
            ordering_source='test',
            output_path=tmp_path,
        )
        
        output_file = tmp_path / 'viewer_index.json'
        assert output_file.exists()
        
        js_file = tmp_path / 'viewer_index.js'
        assert js_file.exists()
    
    def test_written_file_is_valid_json(self, sample_entries, tmp_path):
        """Written file should contain valid, parseable JSON."""
        generate_viewer_index(
            sample_entries,
            ordering_source='test',
            output_path=tmp_path,
        )
        
        output_file = tmp_path / 'viewer_index.json'
        content = output_file.read_text()
        
        # Should parse without error
        parsed = json.loads(content)
        assert parsed['total_instances'] == 4

    def test_written_js_file_contains_assignment(self, sample_entries, tmp_path):
        """Written JS file should contain the global assignment."""
        generate_viewer_index(
            sample_entries,
            ordering_source='test',
            output_path=tmp_path,
        )
        
        js_file = tmp_path / 'viewer_index.js'
        content = js_file.read_text()
        
        assert content.startswith('window.VOXELMASK_VIEWER_INDEX = ')
        assert content.endswith(';')
    
    def test_no_write_when_output_path_none(self, sample_entries, tmp_path):
        """Should NOT write file when output_path is None."""
        index = generate_viewer_index(
            sample_entries,
            ordering_source='test',
            output_path=None,
        )
        
        # Function should return index without writing
        assert index is not None
        
        # No file should exist
        output_file = tmp_path / 'viewer_index.json'
        assert not output_file.exists()
