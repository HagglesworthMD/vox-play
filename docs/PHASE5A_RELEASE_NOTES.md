# Phase 5A — Review UX Semantics

**Tag:** `v0.5.0-phase5a-review-semantics`
**Status:** Approved to proceed
**Risk Class:** Low
**Behavioral Change:** None (presentation only)

> **Invariant:** Phase 5A does not change masking defaults, acceptance gating, region actions, or audit logging. It only changes how existing region metadata is displayed.

> *Post-tag wording hygiene: "required" → "helpful" in LOW_STRENGTH tooltip (no behavioral change).*

---

## Summary

Phase 5A introduces **presentation-only** UI enhancements to the Burned-In PHI Review workflow. These visual elements surface detection metadata to operators without changing any system behavior.

**Critical Invariant:** If someone disables the visuals entirely, system behavior is identical.

---

## What's New

### 1. Detection Strength Badges
- Small, neutral badges showing OCR engine signal strength: `[ OCR: HIGH ]`, `[ OCR: MEDIUM ]`, `[ OCR: LOW ]`, or `[ OCR: ? ]` for OCR failure
- No color semantics implying "safe" vs "unsafe"
- No icons suggesting action (ticks, warnings, locks)
- Tooltip text: *"Detection strength: Indicates OCR engine confidence based on text clarity and consistency. Higher strength does not guarantee PHI presence or completeness."*

### 2. Spatial Zone Labels
- Small uppercase labels showing detection zone: `Zone: HEADER`, `Zone: BODY`, `Zone: FOOTER`
- Positioned near the detected region in the metadata panel
- No layout emphasis (not a warning)
- Tooltip text: *"Detection zone: Location of detected text relative to image layout. Zones are approximate and modality-aware."*

### 3. Uncertainty Tooltips
Appears when `detection_strength == LOW` OR OCR failure:

- **LOW strength:** *"Low detection strength: Text was detected with limited confidence due to image quality, font variation, or overlap. Review context may be required."*
- **OCR failure:** *"Partial text detection: Some characters may not have been fully captured. This does not indicate absence or presence of sensitive information."*

---

## Design Contract (Non-Negotiable)

| Constraint | Enforced |
|------------|----------|
| ❌ No automation | ✅ |
| ❌ No recommendations | ✅ |
| ❌ No "should", "action", or "next step" language | ✅ |
| ❌ No masking triggers | ✅ |
| ❌ No workflow branching | ✅ |
| ❌ No persistence beyond existing ReviewSession state | ✅ |
| ✅ Derived from existing Phase 4 data | ✅ |
| ✅ Visible, explainable, and ignorable | ✅ |

---

## What This Does NOT Add

- ❌ No buttons
- ❌ No toggles
- ❌ No auto-scroll
- ❌ No decision banners
- ❌ No "risk level" wording
- ❌ No persistence to audit beyond existing fields

**Audit logs do NOT change in Phase 5A.**

---

## Testing

30 lightweight tests covering:
- Badge renders for each strength (HIGH, MEDIUM, LOW, None)
- Zone label renders correctly for each zone
- No mutation of ReviewSession state
- No new audit fields written

```bash
PYTHONPATH=src pytest tests/test_phase5a_ui_semantics.py -v
```

---

## Files Changed

| File | Change |
|------|--------|
| `src/phase5a_ui_semantics.py` | **NEW** - Presentation-only UI helpers |
| `src/app.py` | Import Phase 5A module + render badges/tooltips in region list |
| `tests/test_phase5a_ui_semantics.py` | **NEW** - 30 lightweight tests |

---

## Governance Statement

> **"Phase 5A introduces no new decision logic and does not alter review outcomes."**

This statement belongs in:
- ✅ This release note
- ✅ PR description
- ✅ Phase 5A module header comment

---

## Why This Is Acquisition-Safe

From a buyer's perspective:
- This is **interpretability**, not automation
- It increases operator trust without increasing liability
- It demonstrates UI restraint — rare and valued
- It preserves a clean upgrade path to later decision support without pre-committing

We are essentially saying: *"We surface uncertainty instead of hiding it."*

---

## Upgrade Path

Phase 5A is positioned as a foundation for potential future enhancements:
- Phase 5B: Confidence histograms (still presentation-only)
- Phase 6: Optional decision suggestions (gated, operator-controlled)

No commitment is made to these future phases. Phase 5A stands alone as a complete, audit-safe enhancement.
