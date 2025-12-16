"""
Phase 5A — Review UX Semantics
==============================
Status: Approved to proceed
Risk Class: Low
Behavioral Change: None (presentation only)

This module provides presentation-only UI helpers for displaying detection
strength badges, spatial zone labels, and uncertainty tooltips in the
Burned-In PHI Review workflow.

═══════════════════════════════════════════════════════════════════════════════
PHASE 5A DESIGN CONTRACT (NON-NEGOTIABLE)
═══════════════════════════════════════════════════════════════════════════════

* ❌ No automation
* ❌ No recommendations
* ❌ No "should", "action", or "next step" language
* ❌ No masking triggers
* ❌ No workflow branching
* ❌ No persistence beyond existing ReviewSession state

✅ Everything is derived from already-existing Phase 4 data
✅ Everything is visible, explainable, and ignorable

CRITICAL INVARIANT:
    If someone disables the visuals entirely, system behavior is identical.

═══════════════════════════════════════════════════════════════════════════════
WHAT THIS MODULE DOES NOT ADD (EXPLICITLY)
═══════════════════════════════════════════════════════════════════════════════

* ❌ No buttons
* ❌ No toggles
* ❌ No auto-scroll
* ❌ No decision banners
* ❌ No "risk level" wording
* ❌ No persistence to audit beyond existing fields

Phase 5A introduces no new decision logic and does not alter review outcomes.

Author: VoxelMask Engineering
Version: 0.5.0-phase5a-review-semantics
"""

from typing import Optional, Tuple
from dataclasses import dataclass


# ═══════════════════════════════════════════════════════════════════════════════
# DETECTION STRENGTH BADGE
# Purpose: Provide at-a-glance signal strength, not confidence in correctness.
# ═══════════════════════════════════════════════════════════════════════════════

# Neutral badge styles - NO color semantics implying "safe" vs "unsafe"
# NO icons suggesting action (ticks, warnings, locks)
STRENGTH_BADGE_STYLES = {
    "HIGH": {
        "background": "#1f2937",   # Neutral dark gray
        "border": "#374151",       # Subtle gray border
        "text": "#9ca3af",         # Muted gray text
    },
    "MEDIUM": {
        "background": "#1f2937",
        "border": "#374151",
        "text": "#9ca3af",
    },
    "LOW": {
        "background": "#1f2937",
        "border": "#374151",
        "text": "#9ca3af",
    },
    None: {  # OCR failure / unknown
        "background": "#1f2937",
        "border": "#374151",
        "text": "#9ca3af",
    },
}

# Mandatory tooltip text (governance-approved wording)
STRENGTH_BADGE_TOOLTIP = (
    "Detection strength: Indicates OCR engine confidence based on text clarity "
    "and consistency. Higher strength does not guarantee PHI presence or completeness."
)


def get_strength_badge_html(detection_strength: Optional[str]) -> str:
    """
    Generate HTML for a detection strength badge.
    
    Small, neutral badge with no color semantics implying safe/unsafe.
    No icons suggesting action (ticks, warnings, locks).
    
    Args:
        detection_strength: LOW, MEDIUM, HIGH, or None (OCR failure)
        
    Returns:
        HTML string for the badge
        
    Example:
        >>> html = get_strength_badge_html("HIGH")
        >>> # Returns: <span title="...">[ OCR: HIGH ]</span>
    """
    strength_key = detection_strength if detection_strength in STRENGTH_BADGE_STYLES else None
    styles = STRENGTH_BADGE_STYLES[strength_key]
    
    # Display text: None becomes "?" to indicate uncertainty
    display_text = detection_strength if detection_strength else "?"
    
    return f'''<span 
        title="{STRENGTH_BADGE_TOOLTIP}"
        style="
            display: inline-block;
            padding: 2px 6px;
            margin-left: 4px;
            font-size: 0.7em;
            font-family: monospace;
            background: {styles["background"]};
            border: 1px solid {styles["border"]};
            border-radius: 3px;
            color: {styles["text"]};
            cursor: help;
        ">[ OCR: {display_text} ]</span>'''


def get_strength_badge_text(detection_strength: Optional[str]) -> str:
    """
    Generate plain text for a detection strength badge (for non-HTML contexts).
    
    Args:
        detection_strength: LOW, MEDIUM, HIGH, or None (OCR failure)
        
    Returns:
        Plain text badge string
    """
    display_text = detection_strength if detection_strength else "?"
    return f"[ OCR: {display_text} ]"


# ═══════════════════════════════════════════════════════════════════════════════
# SPATIAL ZONE LABELS (HEADER / BODY / FOOTER)
# Purpose: Explain *where* text was detected, not *what to do* about it.
# ═══════════════════════════════════════════════════════════════════════════════

# Mandatory tooltip text (governance-approved wording)
ZONE_LABEL_TOOLTIP = (
    "Detection zone: Location of detected text relative to image layout. "
    "Zones are approximate and modality-aware."
)


def get_zone_label_html(region_zone: Optional[str]) -> str:
    """
    Generate HTML for a spatial zone label.
    
    Small uppercase label with no layout emphasis (not a warning).
    
    Args:
        region_zone: HEADER, BODY, FOOTER, or None
        
    Returns:
        HTML string for the zone label, or empty string if zone is None
        
    Example:
        >>> html = get_zone_label_html("HEADER")
        >>> # Returns: <span title="...">Zone: HEADER</span>
    """
    if not region_zone:
        return ""
    
    return f'''<span 
        title="{ZONE_LABEL_TOOLTIP}"
        style="
            display: inline-block;
            padding: 2px 6px;
            margin-left: 4px;
            font-size: 0.7em;
            font-family: monospace;
            text-transform: uppercase;
            background: #1f2937;
            border: 1px solid #374151;
            border-radius: 3px;
            color: #9ca3af;
            cursor: help;
        ">Zone: {region_zone}</span>'''


def get_zone_label_text(region_zone: Optional[str]) -> str:
    """
    Generate plain text for a zone label (for non-HTML contexts).
    
    Args:
        region_zone: HEADER, BODY, FOOTER, or None
        
    Returns:
        Plain text zone label string, or empty string if zone is None
    """
    if not region_zone:
        return ""
    return f"Zone: {region_zone}"


# ═══════════════════════════════════════════════════════════════════════════════
# UNCERTAINTY TOOLTIPS (MOST IMPORTANT PART)
# Trigger Conditions: detection_strength == LOW OR OCR failure/partial detection
# ═══════════════════════════════════════════════════════════════════════════════

# Governance-approved tooltip language
# Must explain uncertainty without suggesting operator action
# Must avoid implying system failure
UNCERTAINTY_TOOLTIPS = {
    "LOW_STRENGTH": (
        "Low detection strength: Text was detected with limited confidence due to "
        "image quality, font variation, or overlap. Review context may be helpful."
    ),
    "OCR_FAILURE": (
        "Partial text detection: Some characters may not have been fully captured. "
        "This does not indicate absence or presence of sensitive information."
    ),
}


@dataclass
class UncertaintyIndicator:
    """
    Represents an uncertainty indicator for a region.
    
    This is presentation-only data derived from existing Phase 4 fields.
    Does NOT trigger any workflow changes or masking decisions.
    """
    show_indicator: bool
    tooltip_text: str
    indicator_type: str  # "LOW_STRENGTH" or "OCR_FAILURE"
    
    @classmethod
    def from_region(
        cls,
        detection_strength: Optional[str],
        source: str,
    ) -> "UncertaintyIndicator":
        """
        Create an UncertaintyIndicator from region attributes.
        
        Trigger conditions:
        - detection_strength == LOW → show LOW_STRENGTH tooltip
        - detection_strength == None AND source == OCR → show OCR_FAILURE tooltip
        
        Args:
            detection_strength: LOW, MEDIUM, HIGH, or None
            source: RegionSource.OCR or RegionSource.MANUAL
            
        Returns:
            UncertaintyIndicator with appropriate state
        """
        # Only show for OCR regions
        if source != "OCR":
            return cls(
                show_indicator=False,
                tooltip_text="",
                indicator_type="",
            )
        
        # Trigger: OCR failure (None strength for OCR region)
        if detection_strength is None:
            return cls(
                show_indicator=True,
                tooltip_text=UNCERTAINTY_TOOLTIPS["OCR_FAILURE"],
                indicator_type="OCR_FAILURE",
            )
        
        # Trigger: LOW detection strength
        if detection_strength == "LOW":
            return cls(
                show_indicator=True,
                tooltip_text=UNCERTAINTY_TOOLTIPS["LOW_STRENGTH"],
                indicator_type="LOW_STRENGTH",
            )
        
        # No uncertainty for MEDIUM or HIGH
        return cls(
            show_indicator=False,
            tooltip_text="",
            indicator_type="",
        )


def get_uncertainty_tooltip_html(indicator: UncertaintyIndicator) -> str:
    """
    Generate HTML for an uncertainty tooltip indicator.
    
    Only renders if indicator.show_indicator is True.
    Uses neutral styling - no warnings, no action prompts.
    
    Args:
        indicator: UncertaintyIndicator from from_region()
        
    Returns:
        HTML string for the indicator, or empty string if not applicable
    """
    if not indicator.show_indicator:
        return ""
    
    # Small info icon with tooltip - neutral, not alarming
    return f'''<span 
        title="{indicator.tooltip_text}"
        style="
            display: inline-block;
            margin-left: 4px;
            font-size: 0.8em;
            color: #6b7280;
            cursor: help;
        ">ℹ️</span>'''


def get_uncertainty_tooltip_text(indicator: UncertaintyIndicator) -> str:
    """
    Get plain text uncertainty message (for non-HTML contexts).
    
    Args:
        indicator: UncertaintyIndicator from from_region()
        
    Returns:
        Tooltip text, or empty string if not applicable
    """
    return indicator.tooltip_text if indicator.show_indicator else ""


# ═══════════════════════════════════════════════════════════════════════════════
# COMBINED REGION SEMANTICS
# Convenience function to get all Phase 5A presentation elements for a region.
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class RegionSemantics:
    """
    Combined Phase 5A presentation elements for a single region.
    
    This is purely presentation data. Disabling these visuals entirely
    has ZERO effect on system behavior. This is the core audit invariant.
    """
    strength_badge_html: str
    strength_badge_text: str
    zone_label_html: str
    zone_label_text: str
    uncertainty_html: str
    uncertainty_text: str
    has_uncertainty: bool
    
    @classmethod
    def from_region_attributes(
        cls,
        detection_strength: Optional[str],
        region_zone: Optional[str],
        source: str,
    ) -> "RegionSemantics":
        """
        Generate all Phase 5A presentation elements for a region.
        
        This function is pure - no side effects, no state changes.
        
        Args:
            detection_strength: LOW, MEDIUM, HIGH, or None
            region_zone: HEADER, BODY, FOOTER, or None
            source: RegionSource.OCR or RegionSource.MANUAL
            
        Returns:
            RegionSemantics with all presentation elements
        """
        uncertainty = UncertaintyIndicator.from_region(detection_strength, source)
        
        return cls(
            strength_badge_html=get_strength_badge_html(detection_strength) if source == "OCR" else "",
            strength_badge_text=get_strength_badge_text(detection_strength) if source == "OCR" else "",
            zone_label_html=get_zone_label_html(region_zone),
            zone_label_text=get_zone_label_text(region_zone),
            uncertainty_html=get_uncertainty_tooltip_html(uncertainty),
            uncertainty_text=get_uncertainty_tooltip_text(uncertainty),
            has_uncertainty=uncertainty.show_indicator,
        )
