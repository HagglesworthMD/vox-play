"""
Phase 13: Document-Only Study UX Hint Tests

Tests that the UI shows a specific, actionable hint when:
- No imaging files are present (bucket_us/bucket_safe empty)
- Documents ARE present (bucket_docs non-empty)
- Include Associated Documents toggle is OFF

This is a governance requirement: users should understand WHY files aren't processing
and HOW to enable them if intended.
"""

import unittest
from dataclasses import dataclass
from typing import Optional


# Mock SelectionScope for testing (mirrors the real one)
@dataclass
class MockSelectionScope:
    include_images: bool = True
    include_documents: bool = False


def get_documents_excluded_hint(
    bucket_us: list,
    bucket_safe: list,
    bucket_docs: list,
    selection_scope: Optional[MockSelectionScope]
) -> Optional[str]:
    """
    Determine if the document-excluded hint should be shown.
    
    This replicates the logic from app.py lines 3688-3710 for testability.
    
    Returns:
        Hint message string if the condition is met, None otherwise.
    """
    # Imaging buckets are empty
    if bucket_us or bucket_safe:
        return None
    
    # Check if we have documents excluded by scope
    docs_excluded_by_scope = (
        len(bucket_docs) > 0 and 
        selection_scope is not None and 
        not selection_scope.include_documents
    )
    
    if docs_excluded_by_scope:
        return (
            f"📄 **Only associated documents detected** ({len(bucket_docs)} file(s))\n\n"
            f"The selected files are classified as associated documents (Secondary Capture, worksheets, or reports). "
            f"These are excluded by default to ensure FOI and governance safety.\n\n"
            f"**To process these files:** Enable \"Include Associated Documents\" in the **Selection Scope** section above."
        )
    else:
        return None


class TestDocumentsExcludedHint(unittest.TestCase):
    """Tests for the documents-excluded UX hint (Phase 13)."""
    
    def test_hint_shown_when_only_docs_present_and_toggle_off(self):
        """When only documents are present and toggle is OFF, show specific hint."""
        bucket_us = []
        bucket_safe = []
        bucket_docs = ["file1.dcm", "file2.dcm", "file3.dcm"]
        scope = MockSelectionScope(include_images=True, include_documents=False)
        
        hint = get_documents_excluded_hint(bucket_us, bucket_safe, bucket_docs, scope)
        
        self.assertIsNotNone(hint)
        self.assertIn("Only associated documents detected", hint)
        self.assertIn("(3 file(s))", hint)
        self.assertIn("Include Associated Documents", hint)
        self.assertIn("Selection Scope", hint)
    
    def test_no_hint_when_imaging_files_present(self):
        """When imaging files are present, don't show the document hint."""
        bucket_us = ["us_file.dcm"]
        bucket_safe = []
        bucket_docs = ["doc.dcm"]
        scope = MockSelectionScope(include_documents=False)
        
        hint = get_documents_excluded_hint(bucket_us, bucket_safe, bucket_docs, scope)
        
        self.assertIsNone(hint)
    
    def test_no_hint_when_documents_toggle_on(self):
        """When documents toggle is ON, don't show the hint (files will process)."""
        bucket_us = []
        bucket_safe = []
        bucket_docs = ["doc1.dcm", "doc2.dcm"]
        scope = MockSelectionScope(include_documents=True)  # Toggle is ON
        
        hint = get_documents_excluded_hint(bucket_us, bucket_safe, bucket_docs, scope)
        
        self.assertIsNone(hint)
    
    def test_no_hint_when_no_files_at_all(self):
        """When no files at all, don't show the document-specific hint."""
        bucket_us = []
        bucket_safe = []
        bucket_docs = []  # Empty
        scope = MockSelectionScope(include_documents=False)
        
        hint = get_documents_excluded_hint(bucket_us, bucket_safe, bucket_docs, scope)
        
        self.assertIsNone(hint)
    
    def test_hint_includes_governance_language(self):
        """Hint should include governance-safe language about FOI safety."""
        bucket_us = []
        bucket_safe = []
        bucket_docs = ["worksheet.dcm"]
        scope = MockSelectionScope(include_documents=False)
        
        hint = get_documents_excluded_hint(bucket_us, bucket_safe, bucket_docs, scope)
        
        self.assertIn("FOI", hint)
        self.assertIn("governance safety", hint)


if __name__ == '__main__':
    unittest.main()
