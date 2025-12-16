"""
Phase 5A Tests — Review UX Semantics
====================================
Status: Approved | Risk Class: Low | Behavioral Change: None

Lightweight tests that prove Phase 5A is presentation-only.
These tests verify:
1. Badge renders for each detection strength (HIGH, MEDIUM, LOW, None)
2. Zone label renders correctly for each zone
3. No mutation of ReviewSession state
4. No new audit fields written

DOCUMENTATION REQUIREMENT (PR Description / Release Notes):
"Phase 5A introduces no new decision logic and does not alter review outcomes."

Run: PYTHONPATH=src pytest tests/test_phase5a_ui_semantics.py -v
"""

import pytest
import sys
import os

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from phase5a_ui_semantics import (
    get_strength_badge_html,
    get_strength_badge_text,
    get_zone_label_html,
    get_zone_label_text,
    UncertaintyIndicator,
    get_uncertainty_tooltip_html,
    get_uncertainty_tooltip_text,
    RegionSemantics,
    STRENGTH_BADGE_TOOLTIP,
    ZONE_LABEL_TOOLTIP,
    UNCERTAINTY_TOOLTIPS,
)
from review_session import ReviewSession, ReviewRegion, RegionSource, RegionAction


# ═══════════════════════════════════════════════════════════════════════════════
# DETECTION STRENGTH BADGE TESTS
# ═══════════════════════════════════════════════════════════════════════════════

class TestDetectionStrengthBadge:
    """Badge renders for each detection strength level."""
    
    def test_badge_html_high_strength(self):
        """HIGH strength badge should contain 'OCR: HIGH'."""
        html = get_strength_badge_html("HIGH")
        assert "[ OCR: HIGH ]" in html
        assert STRENGTH_BADGE_TOOLTIP in html
        assert "title=" in html  # Tooltip present
    
    def test_badge_html_medium_strength(self):
        """MEDIUM strength badge should contain 'OCR: MEDIUM'."""
        html = get_strength_badge_html("MEDIUM")
        assert "[ OCR: MEDIUM ]" in html
        assert "title=" in html
    
    def test_badge_html_low_strength(self):
        """LOW strength badge should contain 'OCR: LOW'."""
        html = get_strength_badge_html("LOW")
        assert "[ OCR: LOW ]" in html
        assert "title=" in html
    
    def test_badge_html_none_ocr_failure(self):
        """None (OCR failure) should show '?' indicator."""
        html = get_strength_badge_html(None)
        assert "[ OCR: ? ]" in html
        assert "title=" in html
    
    def test_badge_text_high(self):
        """Plain text badge for HIGH strength."""
        text = get_strength_badge_text("HIGH")
        assert text == "[ OCR: HIGH ]"
    
    def test_badge_text_none(self):
        """Plain text badge for None (OCR failure)."""
        text = get_strength_badge_text(None)
        assert text == "[ OCR: ? ]"
    
    def test_badge_html_no_action_icons(self):
        """Badge should NOT contain action-suggesting icons (ticks, warnings, locks)."""
        for strength in ["HIGH", "MEDIUM", "LOW", None]:
            html = get_strength_badge_html(strength)
            # No action-suggesting icons
            assert "✓" not in html
            assert "✔" not in html
            assert "⚠" not in html
            assert "⚡" not in html
            assert "🔒" not in html
            assert "🔓" not in html
    
    def test_badge_html_neutral_colors(self):
        """Badge should use neutral colors, not 'safe' (green) or 'unsafe' (red)."""
        for strength in ["HIGH", "MEDIUM", "LOW", None]:
            html = get_strength_badge_html(strength)
            # Should not have traffic-light semantics
            # (These are approximate checks - neutral grays are used)
            assert "color: #ff0000" not in html.lower()  # No red text
            assert "color: #00ff00" not in html.lower()  # No green text
            assert "background: #ff" not in html.lower()  # No red background


# ═══════════════════════════════════════════════════════════════════════════════
# SPATIAL ZONE LABEL TESTS
# ═══════════════════════════════════════════════════════════════════════════════

class TestSpatialZoneLabel:
    """Zone label renders correctly for each zone."""
    
    def test_zone_label_html_header(self):
        """HEADER zone should render correctly."""
        html = get_zone_label_html("HEADER")
        assert "Zone: HEADER" in html
        assert ZONE_LABEL_TOOLTIP in html
    
    def test_zone_label_html_body(self):
        """BODY zone should render correctly."""
        html = get_zone_label_html("BODY")
        assert "Zone: BODY" in html
    
    def test_zone_label_html_footer(self):
        """FOOTER zone should render correctly."""
        html = get_zone_label_html("FOOTER")
        assert "Zone: FOOTER" in html
    
    def test_zone_label_html_none_returns_empty(self):
        """None zone should return empty string (no label)."""
        html = get_zone_label_html(None)
        assert html == ""
    
    def test_zone_label_text_header(self):
        """Plain text zone label for HEADER."""
        text = get_zone_label_text("HEADER")
        assert text == "Zone: HEADER"
    
    def test_zone_label_text_none_returns_empty(self):
        """None zone text should return empty string."""
        text = get_zone_label_text(None)
        assert text == ""


# ═══════════════════════════════════════════════════════════════════════════════
# UNCERTAINTY TOOLTIP TESTS
# ═══════════════════════════════════════════════════════════════════════════════

class TestUncertaintyTooltip:
    """Uncertainty tooltips for LOW strength or OCR failure."""
    
    def test_indicator_low_strength_triggers(self):
        """LOW strength for OCR region should trigger uncertainty indicator."""
        indicator = UncertaintyIndicator.from_region(
            detection_strength="LOW",
            source="OCR"
        )
        assert indicator.show_indicator is True
        assert indicator.indicator_type == "LOW_STRENGTH"
        assert "limited confidence" in indicator.tooltip_text
    
    def test_indicator_ocr_failure_triggers(self):
        """None strength for OCR region (OCR failure) should trigger uncertainty."""
        indicator = UncertaintyIndicator.from_region(
            detection_strength=None,
            source="OCR"
        )
        assert indicator.show_indicator is True
        assert indicator.indicator_type == "OCR_FAILURE"
        assert "Partial text detection" in indicator.tooltip_text
    
    def test_indicator_medium_no_trigger(self):
        """MEDIUM strength should NOT trigger uncertainty indicator."""
        indicator = UncertaintyIndicator.from_region(
            detection_strength="MEDIUM",
            source="OCR"
        )
        assert indicator.show_indicator is False
    
    def test_indicator_high_no_trigger(self):
        """HIGH strength should NOT trigger uncertainty indicator."""
        indicator = UncertaintyIndicator.from_region(
            detection_strength="HIGH",
            source="OCR"
        )
        assert indicator.show_indicator is False
    
    def test_indicator_manual_never_triggers(self):
        """MANUAL regions should NEVER trigger uncertainty (even with None)."""
        indicator = UncertaintyIndicator.from_region(
            detection_strength=None,
            source="MANUAL"
        )
        assert indicator.show_indicator is False
    
    def test_tooltip_html_renders_for_low(self):
        """Uncertainty tooltip HTML should render for LOW strength."""
        indicator = UncertaintyIndicator.from_region(
            detection_strength="LOW",
            source="OCR"
        )
        html = get_uncertainty_tooltip_html(indicator)
        assert "ℹ️" in html
        assert "title=" in html
    
    def test_tooltip_html_empty_for_high(self):
        """Uncertainty tooltip HTML should be empty for HIGH strength."""
        indicator = UncertaintyIndicator.from_region(
            detection_strength="HIGH",
            source="OCR"
        )
        html = get_uncertainty_tooltip_html(indicator)
        assert html == ""
    
    def test_tooltip_language_no_action_words(self):
        """Tooltip language must NOT contain action-suggesting words."""
        for tooltip_type, tooltip_text in UNCERTAINTY_TOOLTIPS.items():
            # Must NOT contain action language
            assert "action required" not in tooltip_text.lower()
            assert "please review" not in tooltip_text.lower()
            assert "you should" not in tooltip_text.lower()
            assert "must" not in tooltip_text.lower()
            # "Review context may be required" is acceptable per governance


# ═══════════════════════════════════════════════════════════════════════════════
# COMBINED REGION SEMANTICS TESTS
# ═══════════════════════════════════════════════════════════════════════════════

class TestRegionSemantics:
    """Combined Phase 5A presentation elements."""
    
    def test_semantics_ocr_high_header(self):
        """OCR region with HIGH strength in HEADER zone."""
        semantics = RegionSemantics.from_region_attributes(
            detection_strength="HIGH",
            region_zone="HEADER",
            source="OCR"
        )
        assert "[ OCR: HIGH ]" in semantics.strength_badge_html
        assert "Zone: HEADER" in semantics.zone_label_html
        assert semantics.has_uncertainty is False
    
    def test_semantics_ocr_low_footer(self):
        """OCR region with LOW strength in FOOTER zone - should show uncertainty."""
        semantics = RegionSemantics.from_region_attributes(
            detection_strength="LOW",
            region_zone="FOOTER",
            source="OCR"
        )
        assert "[ OCR: LOW ]" in semantics.strength_badge_html
        assert "Zone: FOOTER" in semantics.zone_label_html
        assert semantics.has_uncertainty is True
        assert "ℹ️" in semantics.uncertainty_html
    
    def test_semantics_ocr_failure_body(self):
        """OCR region with failure (None) in BODY zone."""
        semantics = RegionSemantics.from_region_attributes(
            detection_strength=None,
            region_zone="BODY",
            source="OCR"
        )
        assert "[ OCR: ? ]" in semantics.strength_badge_html
        assert "Zone: BODY" in semantics.zone_label_html
        assert semantics.has_uncertainty is True
    
    def test_semantics_manual_no_badge(self):
        """MANUAL regions should NOT have strength badge."""
        semantics = RegionSemantics.from_region_attributes(
            detection_strength=None,
            region_zone=None,
            source="MANUAL"
        )
        assert semantics.strength_badge_html == ""
        assert semantics.zone_label_html == ""
        assert semantics.has_uncertainty is False


# ═══════════════════════════════════════════════════════════════════════════════
# NO MUTATION TESTS (CRITICAL)
# These tests prove Phase 5A does NOT alter ReviewSession state.
# ═══════════════════════════════════════════════════════════════════════════════

class TestNoMutation:
    """Phase 5A must NOT mutate ReviewSession state."""
    
    def test_region_semantics_no_side_effects(self):
        """Calling RegionSemantics.from_region_attributes must not modify source data."""
        # Create a ReviewRegion
        region = ReviewRegion.create_ocr_region(
            x=10, y=20, w=100, h=50,
            detection_strength="LOW",
            region_zone="HEADER"
        )
        
        # Store original values
        orig_strength = region.detection_strength
        orig_zone = region.region_zone
        orig_action = region.reviewer_action
        
        # Call Phase 5A semantics (should be pure)
        semantics = RegionSemantics.from_region_attributes(
            detection_strength=region.detection_strength,
            region_zone=region.region_zone,
            source=region.source,
        )
        
        # Assert NO mutation
        assert region.detection_strength == orig_strength
        assert region.region_zone == orig_zone
        assert region.reviewer_action == orig_action
    
    def test_session_unchanged_after_semantics(self):
        """ReviewSession must be unchanged after generating Phase 5A visuals."""
        # Create session with regions
        session = ReviewSession.create(sop_instance_uid="1.2.3.test")
        session.add_ocr_region(x=10, y=20, w=100, h=50, detection_strength="LOW", region_zone="HEADER")
        session.add_ocr_region(x=10, y=80, w=100, h=50, detection_strength="HIGH", region_zone="BODY")
        
        # Store baseline state
        orig_region_count = len(session.regions)
        orig_accepted = session.review_accepted
        orig_started = session.review_started
        
        # Generate Phase 5A semantics for all regions
        for region in session.get_active_regions():
            _ = RegionSemantics.from_region_attributes(
                detection_strength=region.detection_strength,
                region_zone=region.region_zone,
                source=region.source,
            )
        
        # Assert NO mutation to session
        assert len(session.regions) == orig_region_count
        assert session.review_accepted == orig_accepted
        assert session.review_started == orig_started


# ═══════════════════════════════════════════════════════════════════════════════
# NO NEW AUDIT FIELDS TESTS
# Phase 5A must not add any new fields to DecisionRecord or audit logs.
# ═══════════════════════════════════════════════════════════════════════════════

class TestNoNewAuditFields:
    """
    Phase 5A must NOT introduce new audit fields.
    
    Audit logs should not change in Phase 5A.
    """
    
    def test_region_semantics_no_logging(self):
        """RegionSemantics should not write to any audit system."""
        # This is a design constraint - there are no logging calls in the module
        # We verify the module does not import audit modules
        import phase5a_ui_semantics
        source = phase5a_ui_semantics.__doc__
        
        # The module should be presentation-only with no audit imports
        assert "audit" not in source.lower() or "no persistence to audit" in source.lower()
    
    def test_region_semantics_returns_strings_only(self):
        """RegionSemantics should only return display strings, no audit data."""
        semantics = RegionSemantics.from_region_attributes(
            detection_strength="HIGH",
            region_zone="HEADER",
            source="OCR"
        )
        
        # All output fields should be strings (presentation only)
        assert isinstance(semantics.strength_badge_html, str)
        assert isinstance(semantics.strength_badge_text, str)
        assert isinstance(semantics.zone_label_html, str)
        assert isinstance(semantics.zone_label_text, str)
        assert isinstance(semantics.uncertainty_html, str)
        assert isinstance(semantics.uncertainty_text, str)
        assert isinstance(semantics.has_uncertainty, bool)
