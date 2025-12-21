# tests/test_voxelmask_core.py
"""
Unit tests for voxelmask_core package.

Tests cover the pure logic extracted from app.py:
- viewmodel.py: compute_view_model()
- model.py: DraftState, CoreState, ViewModel
- selection.py: apply_selection_scope, compute_bucket_assignment
- classify.py: classify_dicom_file (integration), bucket_classify_files
- audit.py: create_scope_audit_block, create_processing_stats
- actions.py: Action creation, apply_action reducer

NOTE: Pipeline tests are NOT included here because pipeline.py
coordinates file I/O operations. Those are integration-tested separately.
"""
import pytest
from pathlib import Path

# Import from core package (no streamlit dependency)
from src.voxelmask_core import (
    # Model
    DraftState,
    CoreState,
    ViewModel,
    
    # ViewModel
    compute_view_model,
    compute_review_summary,
    
    # Actions
    Action,
    ActionType,
    ActionResult,
    apply_action,
    
    # Classification
    FileClassification,
    FileCategory,
    RiskLevel,
    bucket_classify_files,
    is_pixel_clean_modality,
    PIXEL_CLEAN_MODALITIES,
    
    # Selection
    SelectionResult,
    SelectionScope,
    apply_selection_scope,
    compute_bucket_assignment,
    get_selection_summary,
    
    # Audit
    create_scope_audit_block,
    create_processing_stats,
    AuditEvent,
    AuditEventType,
    ProcessingAuditSummary,
    
    # Export
    generate_export_folder_name,
    sanitize_filename,
    generate_repair_filename,
)


# =============================================================================
# MODEL TESTS
# =============================================================================

class TestViewModel:
    """Tests for ViewModel dataclass."""
    
    def test_default_values(self):
        """ViewModel initializes with safe defaults."""
        vm = ViewModel()
        assert vm.can_process is False
        assert vm.processing_complete is False
        assert vm.has_files is False
        assert vm.file_count == 0
        assert vm.rss_mb == 0.0
    
    def test_processing_gate_fields(self):
        """ViewModel has all processing gate fields."""
        vm = ViewModel(
            can_process=True,
            processing_complete=False,
            has_review_session=True,
        )
        assert vm.can_process is True
        assert vm.has_review_session is True


class TestDraftState:
    """Tests for DraftState dataclass."""
    
    def test_default_values(self):
        """DraftState initializes with widget defaults."""
        ds = DraftState()
        assert ds.us_mx_manual == 0
        assert ds.selected_instance_idx == 0
        assert ds.manual_w == 50
    
    def test_from_session_state(self):
        """DraftState can be created from session_state dict."""
        ss = {
            'us_mx_manual': 100,
            'us_my_manual': 50,
            'selected_series_uid': 'test-uid',
        }
        ds = DraftState.from_session_state(ss)
        assert ds.us_mx_manual == 100
        assert ds.us_my_manual == 50
        assert ds.selected_series_uid == 'test-uid'
    
    def test_from_session_state_with_missing_keys(self):
        """DraftState handles missing keys with defaults."""
        ss = {}
        ds = DraftState.from_session_state(ss)
        assert ds.us_mx_manual == 0
        assert ds.selected_series_uid is None


class TestCoreState:
    """Tests for CoreState dataclass."""
    
    def test_default_values(self):
        """CoreState initializes with run defaults."""
        cs = CoreState()
        assert cs.run_id is None
        assert cs.processing_complete is False
        assert cs.uploaded_dicom_files == []
    
    def test_from_session_state(self):
        """CoreState can be created from session_state dict."""
        ss = {
            'run_id': 'test-run-123',
            'processing_complete': True,
            'mask_candidates_ready': True,
        }
        cs = CoreState.from_session_state(ss)
        assert cs.run_id == 'test-run-123'
        assert cs.processing_complete is True
        assert cs.mask_candidates_ready is True
    
    def test_to_session_state_updates(self):
        """CoreState can generate session_state updates."""
        cs = CoreState(
            run_id='test-run',
            processing_complete=True,
        )
        updates = cs.to_session_state_updates()
        assert updates['run_id'] == 'test-run'
        assert updates['processing_complete'] is True


# =============================================================================
# VIEWMODEL COMPUTATION TESTS
# =============================================================================

class TestComputeViewModel:
    """Tests for compute_view_model function."""
    
    def test_empty_state(self):
        """compute_view_model works with empty state."""
        ss = {}
        vm = compute_view_model(ss)
        assert isinstance(vm, ViewModel)
        assert vm.can_process is False
        assert vm.file_count == 0
    
    def test_can_process_requires_all_gates(self):
        """can_process requires detection + review + not complete."""
        ss = {
            'mask_candidates_ready': True,
            'mask_review_accepted': True,
            'processing_complete': False,
        }
        vm = compute_view_model(ss)
        assert vm.can_process is True
    
    def test_can_process_blocked_by_detection(self):
        """can_process False when detection not done."""
        ss = {
            'mask_candidates_ready': False,
            'mask_review_accepted': True,
            'processing_complete': False,
        }
        vm = compute_view_model(ss)
        assert vm.can_process is False
    
    def test_can_process_blocked_by_review(self):
        """can_process False when review not accepted."""
        ss = {
            'mask_candidates_ready': True,
            'mask_review_accepted': False,
            'processing_complete': False,
        }
        vm = compute_view_model(ss)
        assert vm.can_process is False
    
    def test_can_process_blocked_when_complete(self):
        """can_process False when processing already complete."""
        ss = {
            'mask_candidates_ready': True,
            'mask_review_accepted': True,
            'processing_complete': True,
        }
        vm = compute_view_model(ss)
        assert vm.can_process is False
    
    def test_file_count(self):
        """file_count reflects uploaded files."""
        ss = {
            'uploaded_dicom_files': [1, 2, 3],  # Dummy files
        }
        vm = compute_view_model(ss)
        assert vm.file_count == 3
        assert vm.has_files is True
    
    def test_has_output(self):
        """has_output True when zip path or buffer exists."""
        ss = {'output_zip_path': '/path/to/output.zip'}
        vm = compute_view_model(ss)
        assert vm.has_output is True
        
        ss = {'output_zip_buffer': b'zipdata'}
        vm = compute_view_model(ss)
        assert vm.has_output is True


# =============================================================================
# CLASSIFICATION TESTS
# =============================================================================

class TestIsPixelCleanModality:
    """Tests for is_pixel_clean_modality function."""
    
    def test_ct_is_pixel_clean(self):
        assert is_pixel_clean_modality('CT') is True
    
    def test_mr_is_pixel_clean(self):
        assert is_pixel_clean_modality('MR') is True
    
    def test_us_is_not_pixel_clean(self):
        assert is_pixel_clean_modality('US') is False
    
    def test_sc_is_not_pixel_clean(self):
        assert is_pixel_clean_modality('SC') is False
    
    def test_case_insensitive(self):
        assert is_pixel_clean_modality('ct') is True


class TestBucketClassifyFiles:
    """Tests for bucket_classify_files function."""
    
    def test_empty_list(self):
        """Empty input returns empty buckets."""
        us, safe, docs, skip = bucket_classify_files([])
        assert us == []
        assert safe == []
        assert docs == []
        assert skip == []
    
    def test_us_goes_to_us_bucket(self):
        """Ultrasound files go to US bucket."""
        clf = FileClassification(
            filepath='/test/us.dcm',
            filename='us.dcm',
            modality='US',
            sop_class_uid='1.2.3',
            category=FileCategory.IMAGE,
            risk_level=RiskLevel.HIGH,
            include_by_default=True,
            requires_preview=True,
            requires_masking=True,
        )
        us, safe, docs, skip = bucket_classify_files([clf])
        assert len(us) == 1
        assert us[0].modality == 'US'
    
    def test_ct_goes_to_safe_bucket(self):
        """CT files go to safe bucket."""
        clf = FileClassification(
            filepath='/test/ct.dcm',
            filename='ct.dcm',
            modality='CT',
            sop_class_uid='1.2.3',
            category=FileCategory.IMAGE,
            risk_level=RiskLevel.LOW,
            include_by_default=True,
            requires_preview=False,
            requires_masking=False,
        )
        us, safe, docs, skip = bucket_classify_files([clf])
        assert len(safe) == 1
        assert safe[0].modality == 'CT'


# =============================================================================
# SELECTION TESTS
# =============================================================================

class TestSelectionScope:
    """Tests for SelectionScope class."""
    
    def test_default_includes_images_only(self):
        """Default scope includes images, excludes documents."""
        scope = SelectionScope()
        assert scope.include_images is True
        assert scope.include_documents is False
    
    def test_should_include_category(self):
        """should_include_category respects settings."""
        scope = SelectionScope(include_images=True, include_documents=False)
        assert scope.should_include_category(FileCategory.IMAGE) is True
        assert scope.should_include_category(FileCategory.DOCUMENT) is False


class TestApplySelectionScope:
    """Tests for apply_selection_scope function."""
    
    def test_empty_files(self):
        """Empty file list returns empty result."""
        result = apply_selection_scope(
            all_files=[],
            classifications={},
            selection_scope=SelectionScope(),
        )
        assert result.total_included == 0
        assert result.total_excluded == 0
    
    def test_excludes_documents_by_default(self):
        """Documents excluded when include_documents=False."""
        # Create a mock file object with .name attribute
        class MockFile:
            def __init__(self, name):
                self.name = name
        
        files = [MockFile('doc1.dcm')]
        classifications = {
            'doc1.dcm': FileClassification(
                filepath='/test/doc1.dcm',
                filename='doc1.dcm',
                modality='SC',
                sop_class_uid='1.2.3',
                category=FileCategory.DOCUMENT,
                risk_level=RiskLevel.MEDIUM,
                include_by_default=False,
                requires_preview=True,
                requires_masking=False,
            )
        }
        
        result = apply_selection_scope(
            all_files=files,
            classifications=classifications,
            selection_scope=SelectionScope(include_documents=False),
        )
        assert result.total_included == 0
        assert result.excluded_document_count == 1


# =============================================================================
# AUDIT TESTS
# =============================================================================

class TestCreateScopeAuditBlock:
    """Tests for create_scope_audit_block function."""
    
    def test_returns_string(self):
        """Audit block is a string."""
        block = create_scope_audit_block(
            include_images=True,
            include_documents=False,
            gateway_profile='internal_repair',
        )
        assert isinstance(block, str)
    
    def test_contains_profile(self):
        """Audit block contains gateway profile."""
        block = create_scope_audit_block(
            include_images=True,
            include_documents=True,
            gateway_profile='foi_legal',
        )
        assert 'foi_legal' in block
    
    def test_contains_scope_values(self):
        """Audit block contains include settings."""
        block = create_scope_audit_block(
            include_images=True,
            include_documents=True,
            gateway_profile='internal_repair',
        )
        assert 'Include Images: True' in block
        assert 'Include Documents: True' in block


class TestCreateProcessingStats:
    """Tests for create_processing_stats function."""
    
    def test_basic_stats(self):
        """Creates stats dict with required fields."""
        stats = create_processing_stats(
            processing_time_seconds=10.5,
            total_input_bytes=1024 * 1024 * 100,  # 100 MB
            total_output_bytes=1024 * 1024 * 95,  # 95 MB
            file_count=10,
        )
        assert stats['processing_time_seconds'] == 10.5
        assert stats['file_count'] == 10
        assert 'throughput_mbps' in stats
    
    def test_zero_time_safe(self):
        """Handles zero processing time without division error."""
        stats = create_processing_stats(
            processing_time_seconds=0,
            total_input_bytes=100,
            total_output_bytes=100,
            file_count=1,
        )
        assert stats['throughput_mbps'] == 0.0


class TestAuditEvent:
    """Tests for AuditEvent class."""
    
    def test_create_event(self):
        """AuditEvent.create generates event with timestamp."""
        event = AuditEvent.create(
            AuditEventType.RUN_STARTED,
            run_id='test-123',
            file_count=5,
        )
        assert event.event_type == AuditEventType.RUN_STARTED
        assert event.run_id == 'test-123'
        assert event.details['file_count'] == 5
        assert event.timestamp is not None
    
    def test_to_dict(self):
        """AuditEvent serializes to dict."""
        event = AuditEvent.create(AuditEventType.FILE_PROCESSED)
        d = event.to_dict()
        assert d['event_type'] == 'file_processed'
        assert 'timestamp' in d


# =============================================================================
# EXPORT TESTS
# =============================================================================

class TestGenerateExportFolderName:
    """Tests for generate_export_folder_name function."""
    
    def test_internal_repair_profile(self):
        """Generates name for internal repair."""
        from datetime import datetime
        name = generate_export_folder_name('internal_repair', datetime(2024, 12, 21, 18, 51, 0))
        assert 'VoxelMask_InternalRepair_20241221_185100' == name
    
    def test_foi_legal_profile(self):
        """Generates name for FOI legal."""
        from datetime import datetime
        name = generate_export_folder_name('foi_legal', datetime(2024, 1, 1, 12, 0, 0))
        assert 'VoxelMask_FOI_Legal_20240101_120000' == name


class TestSanitizeFilename:
    """Tests for sanitize_filename function."""
    
    def test_preserves_safe_chars(self):
        """Safe chars are preserved."""
        assert sanitize_filename('test_file.dcm') == 'test_file.dcm'
    
    def test_replaces_unsafe_chars(self):
        """Unsafe chars replaced with underscore."""
        assert sanitize_filename('test file!.dcm') == 'test_file_.dcm'


class TestGenerateRepairFilename:
    """Tests for generate_repair_filename function."""
    
    def test_basic_generation(self):
        """Generates descriptive repair filename."""
        name = generate_repair_filename(
            original_filename='original.dcm',
            new_patient_id='SMITH_JOHN',
            series_description='Abdomen',
        )
        assert name.endswith('.dcm')
        assert 'CORRECTED' in name
        assert 'SMITH_JOHN' in name


# =============================================================================
# ACTIONS TESTS
# =============================================================================

class TestAction:
    """Tests for Action creation."""
    
    def test_detect_phi_action(self):
        """Creates PHI detection action."""
        action = Action.detect_phi(10, 20, 100, 50, 5)
        assert action.type == ActionType.DETECT_PHI_REGIONS
        assert action.payload.mask_x == 10
        assert action.payload.us_file_count == 5
    
    def test_accept_review_action(self):
        """Creates review acceptance action."""
        action = Action.accept_review()
        assert action.type == ActionType.ACCEPT_REVIEW
    
    def test_toggle_region_action(self):
        """Creates region toggle action."""
        action = Action.toggle_region('region-123')
        assert action.type == ActionType.TOGGLE_REGION
        assert action.payload.region_id == 'region-123'


class TestApplyAction:
    """Tests for apply_action reducer."""
    
    def test_detect_phi_updates_state(self):
        """DETECT_PHI_REGIONS updates mask state."""
        state = CoreState()
        action = Action.detect_phi(10, 20, 100, 50, 3)
        result = apply_action(state, action)
        
        assert result.success is True
        assert result.state.mask_candidates_ready is True
        assert result.state.us_shared_mask == (10, 20, 100, 50)
    
    def test_accept_review_updates_state(self):
        """ACCEPT_REVIEW sets mask_review_accepted."""
        state = CoreState()
        action = Action.accept_review()
        result = apply_action(state, action)
        
        assert result.success is True
        assert result.state.mask_review_accepted is True
    
    def test_reset_run_clears_state(self):
        """RESET_RUN returns empty state."""
        state = CoreState(
            run_id='test-123',
            processing_complete=True,
        )
        action = Action.reset_run()
        result = apply_action(state, action)
        
        assert result.state.run_id is None
        assert result.state.processing_complete is False


# =============================================================================
# NO STREAMLIT IMPORT VERIFICATION
# =============================================================================

class TestNoStreamlitImports:
    """Verify no streamlit imports in core package."""
    
    def test_no_streamlit_in_model(self):
        """model.py has no streamlit imports."""
        import src.voxelmask_core.model as model_module
        source = Path(model_module.__file__).read_text()
        assert 'import streamlit' not in source
    
    def test_no_streamlit_in_viewmodel(self):
        """viewmodel.py has no streamlit imports."""
        import src.voxelmask_core.viewmodel as vm_module
        source = Path(vm_module.__file__).read_text()
        assert 'import streamlit' not in source
    
    def test_no_streamlit_in_actions(self):
        """actions.py has no streamlit imports."""
        import src.voxelmask_core.actions as actions_module
        source = Path(actions_module.__file__).read_text()
        assert 'import streamlit' not in source
    
    def test_no_streamlit_in_classify(self):
        """classify.py has no streamlit imports."""
        import src.voxelmask_core.classify as classify_module
        source = Path(classify_module.__file__).read_text()
        assert 'import streamlit' not in source
    
    def test_no_streamlit_in_selection(self):
        """selection.py has no streamlit imports."""
        import src.voxelmask_core.selection as selection_module
        source = Path(selection_module.__file__).read_text()
        assert 'import streamlit' not in source
    
    def test_no_streamlit_in_export(self):
        """export.py has no streamlit imports."""
        import src.voxelmask_core.export as export_module
        source = Path(export_module.__file__).read_text()
        assert 'import streamlit' not in source
    
    def test_no_streamlit_in_audit(self):
        """audit.py has no streamlit imports."""
        import src.voxelmask_core.audit as audit_module
        source = Path(audit_module.__file__).read_text()
        assert 'import streamlit' not in source
    
    def test_no_streamlit_in_pipeline(self):
        """pipeline.py has no streamlit imports."""
        import src.voxelmask_core.pipeline as pipeline_module
        source = Path(pipeline_module.__file__).read_text()
        assert 'import streamlit' not in source
