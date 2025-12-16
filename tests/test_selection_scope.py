"""
Tests for Selection Scope Module
================================
Phase 6: Explicit Document Inclusion Semantics

Validates:
- SelectionScope default behavior (conservative)
- Object classification logic
- Audit logging format
- Selection filtering

Author: VoxelMask Engineering
Version: 0.6.0-explicit-selection
"""

import pytest
import sys
import os

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), 'src'))

from selection_scope import (
    SelectionScope,
    ObjectCategory,
    classify_object,
    should_include_object,
    get_category_label,
    generate_scope_audit_block,
    generate_scope_json,
    DOCUMENT_SOP_CLASSES,
    DOCUMENT_MODALITIES,
)


class TestSelectionScopeDefaults:
    """Test default SelectionScope behavior (conservative)."""
    
    def test_default_includes_images(self):
        """Default scope should include images."""
        scope = SelectionScope.create_default()
        assert scope.include_images is True
    
    def test_default_excludes_documents(self):
        """Default scope should exclude documents (conservative)."""
        scope = SelectionScope.create_default()
        assert scope.include_documents is False
    
    def test_created_at_set(self):
        """Created timestamp should be set."""
        scope = SelectionScope.create_default()
        assert scope.created_at is not None
        assert "Z" in scope.created_at  # UTC format
    
    def test_modified_at_initially_none(self):
        """Modified timestamp should be None initially."""
        scope = SelectionScope.create_default()
        assert scope.modified_at is None


class TestSelectionScopeModification:
    """Test SelectionScope modification tracking."""
    
    def test_set_include_documents_updates_timestamp(self):
        """Setting include_documents should update modified_at."""
        scope = SelectionScope.create_default()
        assert scope.modified_at is None
        
        scope.set_include_documents(True)
        
        assert scope.include_documents is True
        assert scope.modified_at is not None
    
    def test_set_include_images_updates_timestamp(self):
        """Setting include_images should update modified_at."""
        scope = SelectionScope.create_default()
        
        scope.set_include_images(False)
        
        assert scope.include_images is False
        assert scope.modified_at is not None


class TestSelectionScopeSerialization:
    """Test SelectionScope serialization for audit."""
    
    def test_to_dict_structure(self):
        """to_dict should return proper structure."""
        scope = SelectionScope.create_default()
        result = scope.to_dict()
        
        assert "include_images" in result
        assert "include_documents" in result
        assert "created_at" in result
        assert "modified_at" in result
    
    def test_to_dict_values(self):
        """to_dict values should match scope."""
        scope = SelectionScope(include_images=True, include_documents=True)
        result = scope.to_dict()
        
        assert result["include_images"] is True
        assert result["include_documents"] is True


class TestExclusionReason:
    """Test exclusion reason generation for audit."""
    
    def test_no_exclusion_returns_none(self):
        """When nothing excluded, should return None."""
        scope = SelectionScope(include_images=True, include_documents=True)
        assert scope.get_exclusion_reason() is None
    
    def test_documents_excluded_reason(self):
        """When documents excluded, should return appropriate reason."""
        scope = SelectionScope(include_images=True, include_documents=False)
        reason = scope.get_exclusion_reason()
        
        assert reason is not None
        assert "non-image objects" in reason.lower()
        assert "explicit user selection" in reason.lower()
    
    def test_images_excluded_reason(self):
        """When images excluded, should return appropriate reason."""
        scope = SelectionScope(include_images=False, include_documents=True)
        reason = scope.get_exclusion_reason()
        
        assert reason is not None
        assert "imaging series" in reason.lower()


class TestObjectClassification:
    """Test object classification logic."""
    
    def test_us_is_image(self):
        """US modality should be classified as IMAGE."""
        result = classify_object(
            modality="US",
            sop_class_uid="1.2.840.10008.5.1.4.1.1.6.1"  # US Image Storage
        )
        assert result == ObjectCategory.IMAGE
    
    def test_ct_is_image(self):
        """CT modality should be classified as IMAGE."""
        result = classify_object(
            modality="CT",
            sop_class_uid="1.2.840.10008.5.1.4.1.1.2"  # CT Image Storage
        )
        assert result == ObjectCategory.IMAGE
    
    def test_sc_is_document(self):
        """SC modality should be classified as DOCUMENT."""
        result = classify_object(
            modality="SC",
            sop_class_uid="1.2.840.10008.5.1.4.1.1.7"  # Secondary Capture
        )
        assert result == ObjectCategory.DOCUMENT
    
    def test_ot_is_document(self):
        """OT modality should be classified as DOCUMENT."""
        result = classify_object(
            modality="OT",
            sop_class_uid=""
        )
        assert result == ObjectCategory.DOCUMENT
    
    def test_sr_is_document(self):
        """SR modality should be classified as DOCUMENT."""
        result = classify_object(
            modality="SR",
            sop_class_uid=""
        )
        assert result == ObjectCategory.DOCUMENT
    
    def test_secondary_capture_sop_is_document(self):
        """Secondary Capture SOP Class should be classified as DOCUMENT."""
        result = classify_object(
            modality="",
            sop_class_uid="1.2.840.10008.5.1.4.1.1.7"  # SC SOP Class
        )
        assert result == ObjectCategory.DOCUMENT
    
    def test_encapsulated_pdf_sop(self):
        """Encapsulated PDF SOP Class should be classified correctly."""
        result = classify_object(
            modality="",
            sop_class_uid="1.2.840.10008.5.1.4.1.1.104.1"
        )
        assert result == ObjectCategory.ENCAPSULATED_PDF
    
    def test_worksheet_keyword_in_description(self):
        """Worksheet keyword in series description should classify as DOCUMENT."""
        result = classify_object(
            modality="US",  # Even US modality
            sop_class_uid="",
            series_description="OB WORKSHEET PAGE 1"
        )
        assert result == ObjectCategory.DOCUMENT
    
    def test_report_keyword_in_description(self):
        """Report keyword in series description should classify as DOCUMENT."""
        result = classify_object(
            modality="US",
            sop_class_uid="",
            series_description="GENERAL REPORT"
        )
        assert result == ObjectCategory.DOCUMENT
    
    def test_normal_us_not_document(self):
        """Normal US without document keywords should be IMAGE."""
        result = classify_object(
            modality="US",
            sop_class_uid="1.2.840.10008.5.1.4.1.1.6.1",
            series_description="OB NT 12W3D"
        )
        assert result == ObjectCategory.IMAGE


class TestShouldIncludeObject:
    """Test inclusion logic based on selection scope."""
    
    def test_image_included_when_images_true(self):
        """Images should be included when include_images is True."""
        scope = SelectionScope(include_images=True, include_documents=False)
        assert should_include_object(ObjectCategory.IMAGE, scope) is True
    
    def test_image_excluded_when_images_false(self):
        """Images should be excluded when include_images is False."""
        scope = SelectionScope(include_images=False, include_documents=True)
        assert should_include_object(ObjectCategory.IMAGE, scope) is False
    
    def test_document_included_when_documents_true(self):
        """Documents should be included when include_documents is True."""
        scope = SelectionScope(include_images=True, include_documents=True)
        assert should_include_object(ObjectCategory.DOCUMENT, scope) is True
    
    def test_document_excluded_when_documents_false(self):
        """Documents should be excluded when include_documents is False."""
        scope = SelectionScope(include_images=True, include_documents=False)
        assert should_include_object(ObjectCategory.DOCUMENT, scope) is False
    
    def test_sr_follows_documents_toggle(self):
        """Structured Reports should follow include_documents toggle."""
        scope_yes = SelectionScope(include_images=True, include_documents=True)
        scope_no = SelectionScope(include_images=True, include_documents=False)
        
        assert should_include_object(ObjectCategory.STRUCTURED_REPORT, scope_yes) is True
        assert should_include_object(ObjectCategory.STRUCTURED_REPORT, scope_no) is False
    
    def test_pdf_follows_documents_toggle(self):
        """Encapsulated PDFs should follow include_documents toggle."""
        scope_yes = SelectionScope(include_images=True, include_documents=True)
        scope_no = SelectionScope(include_images=True, include_documents=False)
        
        assert should_include_object(ObjectCategory.ENCAPSULATED_PDF, scope_yes) is True
        assert should_include_object(ObjectCategory.ENCAPSULATED_PDF, scope_no) is False


class TestCategoryLabels:
    """Test human-readable category labels."""
    
    def test_image_label(self):
        """IMAGE category should have readable label."""
        label = get_category_label(ObjectCategory.IMAGE)
        assert "imaging" in label.lower() or "series" in label.lower()
    
    def test_document_label(self):
        """DOCUMENT category should have readable label."""
        label = get_category_label(ObjectCategory.DOCUMENT)
        assert "associated" in label.lower() or "worksheet" in label.lower()
    
    def test_pdf_label(self):
        """ENCAPSULATED_PDF category should have readable label."""
        label = get_category_label(ObjectCategory.ENCAPSULATED_PDF)
        assert "pdf" in label.lower()


class TestAuditGeneration:
    """Test audit log generation."""
    
    def test_audit_block_contains_scope(self):
        """Audit block should contain selection scope values."""
        scope = SelectionScope(include_images=True, include_documents=False)
        block = generate_scope_audit_block(scope)
        
        assert "Include Imaging Series" in block
        assert "Include Associated Documents" in block
        assert "YES" in block  # For images
        assert "NO" in block   # For documents
    
    def test_audit_block_contains_exclusion_note(self):
        """Audit block should contain exclusion note when applicable."""
        scope = SelectionScope(include_images=True, include_documents=False)
        block = generate_scope_audit_block(scope)
        
        assert "EXCLUSION NOTE" in block
    
    def test_scope_json_structure(self):
        """JSON output should have proper structure."""
        scope = SelectionScope.create_default()
        result = generate_scope_json(scope)
        
        assert "selection_scope" in result
        assert "include_images" in result["selection_scope"]
        assert "include_documents" in result["selection_scope"]
    
    def test_scope_json_includes_exclusion_note(self):
        """JSON output should include exclusion note when applicable."""
        scope = SelectionScope(include_images=True, include_documents=False)
        result = generate_scope_json(scope)
        
        assert "exclusion_note" in result


class TestDocumentModalitiesComplete:
    """Test that all document modalities are properly defined."""
    
    def test_sc_in_document_modalities(self):
        """SC should be in document modalities."""
        assert "SC" in DOCUMENT_MODALITIES
    
    def test_ot_in_document_modalities(self):
        """OT should be in document modalities."""
        assert "OT" in DOCUMENT_MODALITIES
    
    def test_sr_in_document_modalities(self):
        """SR should be in document modalities."""
        assert "SR" in DOCUMENT_MODALITIES
    
    def test_secondary_capture_sop_defined(self):
        """Secondary Capture SOP Class should be defined."""
        assert "1.2.840.10008.5.1.4.1.1.7" in DOCUMENT_SOP_CLASSES
    
    def test_encapsulated_pdf_sop_defined(self):
        """Encapsulated PDF SOP Class should be defined."""
        assert "1.2.840.10008.5.1.4.1.1.104.1" in DOCUMENT_SOP_CLASSES


class TestSOPClassOverridesModality:
    """
    REGRESSION TESTS: SOP Class-Based Classification Loophole Fix
    
    These tests verify the fix for the critical bug where documents could
    bypass the include_documents=False filter by having a non-document
    modality string (e.g., "US" or "CT").
    
    The fix ensures SOP Class UID is ALWAYS checked FIRST, making it
    impossible for documents to leak into image buckets.
    
    Added: Phase 6 (v0.6.x)
    Bug Fixed: Documents with wrong modality bypassing include_documents gate
    """
    
    def test_pdf_with_us_modality_is_still_pdf(self):
        """
        CRITICAL: Encapsulated PDF with US modality must be classified as PDF.
        
        This is the exact loophole scenario: a PDF stored with modality="US"
        should NOT be treated as an image.
        """
        result = classify_object(
            modality="US",  # Wrong modality!
            sop_class_uid="1.2.840.10008.5.1.4.1.1.104.1",  # PDF SOP Class
            series_description="",
            image_type=""
        )
        assert result == ObjectCategory.ENCAPSULATED_PDF
    
    def test_secondary_capture_with_ct_modality_is_document(self):
        """
        CRITICAL: SC with CT modality must be classified as DOCUMENT.
        
        Another loophole scenario: SC stored with modality="CT".
        """
        result = classify_object(
            modality="CT",  # Wrong modality!
            sop_class_uid="1.2.840.10008.5.1.4.1.1.7",  # SC SOP Class
            series_description="",
            image_type=""
        )
        assert result == ObjectCategory.DOCUMENT
    
    def test_multiframe_sc_with_mr_modality_is_document(self):
        """Multi-frame SC with MR modality must be classified as DOCUMENT."""
        result = classify_object(
            modality="MR",  # Wrong modality!
            sop_class_uid="1.2.840.10008.5.1.4.1.1.7.1",  # Multi-frame SC
            series_description="",
            image_type=""
        )
        assert result == ObjectCategory.DOCUMENT
    
    def test_sr_sop_with_us_modality_is_sr(self):
        """Structured Report SOP with US modality must be classified as SR."""
        result = classify_object(
            modality="US",  # Wrong modality!
            sop_class_uid="1.2.840.10008.5.1.4.1.1.88.11",  # Basic Text SR
            series_description="",
            image_type=""
        )
        assert result == ObjectCategory.STRUCTURED_REPORT
    
    def test_sop_class_takes_priority_over_safe_modality(self):
        """SOP Class should override even 'safe' modalities like CT/MR/XR."""
        # PDF with XR modality
        result = classify_object(
            modality="XR",  # "Safe" modality
            sop_class_uid="1.2.840.10008.5.1.4.1.1.104.1",  # PDF
            series_description="",
            image_type=""
        )
        assert result == ObjectCategory.ENCAPSULATED_PDF
        
        # SC with NM modality
        result2 = classify_object(
            modality="NM",  # "Safe" modality
            sop_class_uid="1.2.840.10008.5.1.4.1.1.7",  # SC
            series_description="",
            image_type=""
        )
        assert result2 == ObjectCategory.DOCUMENT
    
    def test_document_exclusion_works_with_mismatched_modality(self):
        """
        END-TO-END: Document with wrong modality should be excluded
        when include_documents=False.
        """
        scope = SelectionScope(include_images=True, include_documents=False)
        
        # PDF pretending to be US
        category = classify_object(
            modality="US",
            sop_class_uid="1.2.840.10008.5.1.4.1.1.104.1",
        )
        assert should_include_object(category, scope) is False
        
        # SC pretending to be CT
        category2 = classify_object(
            modality="CT",
            sop_class_uid="1.2.840.10008.5.1.4.1.1.7",
        )
        assert should_include_object(category2, scope) is False
    
    def test_real_us_image_still_included(self):
        """Real US image (correct SOP Class) should still be included."""
        scope = SelectionScope(include_images=True, include_documents=False)
        
        category = classify_object(
            modality="US",
            sop_class_uid="1.2.840.10008.5.1.4.1.1.6.1",  # US Image Storage
        )
        assert category == ObjectCategory.IMAGE
        assert should_include_object(category, scope) is True
    
    def test_real_ct_image_still_included(self):
        """Real CT image (correct SOP Class) should still be included."""
        scope = SelectionScope(include_images=True, include_documents=False)
        
        category = classify_object(
            modality="CT",
            sop_class_uid="1.2.840.10008.5.1.4.1.1.2",  # CT Image Storage
        )
        assert category == ObjectCategory.IMAGE
        assert should_include_object(category, scope) is True
