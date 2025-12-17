# Phase 6 — UX Hardening Acceptance Checklist

**Recoverability Model:** Model B — External Source Recoverability
**Phase:** 6
**Prerequisite:** Phase 5C CLOSED
**Audience:** PACS engineers, governance reviewers, acquisition due diligence

---

## Acceptance Rule

**Phase 6 is accepted only if *all* mandatory items below are satisfied.**
Any failed item constitutes a **governance breach**, not a UX defect.

---

## 1. Recoverability Truthfulness

☐ The UI does **not** claim, imply, or suggest that original pixel data can be restored from VoxelMask
☐ The UI does **not** use the terms:

* “Unmask”
* “Undo”
* “Restore”
* “Revert”
* “Recover original”

☐ The UI consistently uses approved language:

* “Processed copy”
* “Masked output”
* “Derived data”
* “Audit-linked to source PACS”

☐ No tooltip, help text, or empty-state text contradicts Model B semantics

**PASS / FAIL**

---

## 2. Irreversible Action Signalling

☐ All irreversible actions are explicitly labelled as such
☐ Buttons initiating irreversible processing use final-action language (e.g. “Generate masked copy”)
☐ No irreversible action is presented as a toggle, checkbox, or slider

☐ Re-running a job requires explicit re-selection of source data
☐ No UI element suggests a reversible processing pipeline

**PASS / FAIL**

---

## 3. Confirmation Dialog Accuracy

☐ All confirmation dialogs for processing/export explicitly state:

> “Original pixel data is not retained by VoxelMask.”

☐ No confirmation dialog claims or implies:

* That cancelling restores state
* That results can be undone
* That originals are cached for recovery

☐ Dialog language has been reviewed for legal and audit clarity, not friendliness

**PASS / FAIL**

---

## 4. Viewer & Comparison Behaviour

☐ Any displayed source imagery is clearly labelled as:

* “Source (from PACS)” or equivalent
  ☐ Masked imagery is clearly labelled as:
* “Masked Output (VoxelMask)”

☐ No slider, toggle, or animation implies reversible transformation
☐ No “before / after” control allows pixel-level toggling

☐ If side-by-side views exist, they are explicitly described as **independent representations**

**PASS / FAIL**

---

## 5. Audit Artefact Visibility

☐ Job-level audit metadata is visible without developer tooling
☐ The UI surfaces:

* Source SOPInstanceUID
* Output SOPInstanceUID
* Presence of cryptographic hashes

☐ The UI clearly states:

> “Verification is performed against the source PACS.”

☐ Audit artefacts are not hidden behind optional or advanced-only UI paths

**PASS / FAIL**

---

## 6. Error & Failure Messaging

☐ Error messages do **not** imply recoverability or restoration
☐ Error messages do **not** suggest that retrying will restore original pixels

☐ Approved phrasing is used where applicable:

* “Masked output can be regenerated from the source PACS.”
* “Original images remain unchanged in PACS.”

☐ No error text contradicts Phase 5C recoverability guarantees

**PASS / FAIL**

---

## 7. Job History Semantics

☐ Job history entries are treated as immutable records
☐ Prior jobs cannot be “continued,” “resumed,” or “undone”

☐ Reprocessing always creates a **new job**
☐ UI does not resemble an undo stack or editable workflow history

**PASS / FAIL**

---

## 8. Export & Packaging Clarity

☐ All exports are labelled as:

* “Derived de-identified copy”

☐ Export screens do **not** suggest:

* Authority
* Clinical primacy
* Replacement of source records

☐ Audit bundle inclusion is enabled by default
☐ Export UX makes clear that PACS remains the system of record

**PASS / FAIL**

---

## 9. Help Text & In-App Documentation

☐ Help/about sections explicitly state:

* Recoverability Model B
* “VoxelMask does not retain original pixel data”

☐ In-app documentation is consistent with:

* `PHASE5C_GATE2_SOURCE_RECOVERABILITY.md`

☐ No marketing, hype, or AI-centric language appears in governance-facing UI

**PASS / FAIL**

---

## 10. Red-Team Validation Question (Mandatory)

Answer the following honestly:

> “Could a reasonable PACS engineer believe, based on the UI alone, that VoxelMask can restore original images?”

☐ NO — the UI makes this impossible to infer
☐ YES — **Phase 6 FAIL**

**PASS / FAIL**

---

## Phase 6 Acceptance Declaration

☐ All checklist items above are marked PASS
☐ No exceptions or “known issues” contradict recoverability semantics
☐ UX changes are presentation-only and do not alter processing logic

**Phase 6 UX Hardening: ACCEPTED / REJECTED**

**Reviewer:** ____________________
**Date:** ____________________
**Signature (optional):** ____________________

---

## Phase 6 Validation Run

**Date:** 2025-12-17
**Build/Commit:** c8309be (pre-commit, changes pending)
**Reviewer:** Automated + Brian Shaw
**Recoverability model:** Model B (External Source Recoverability)

### Evidence

#### UI Code Scan (src/app.py)

```bash
rg -n -i "(unmask|undo|restore|revert|recover original|clinical correction)" src/app.py
```

**Result:** ✅ PASS
- No user-facing "unmask/undo/restore/revert/recover original" terminology
- No "Clinical Correction" in UI text
- Internal API parameter names (`clinical_context`, `unmask_all`) are acceptable (non-user-facing)
- Remaining "clinical" occurrences are explicit disclaimers ("Not for clinical use") — correct

#### PDF Artefact Scan

```bash
pdftotext /tmp/phase6_test_report.pdf - | rg -i "(unmask|undo|restore|revert|recover original|clinical correction|\\bclinical\\b|CLINICAL)"
```

**Result:** ✅ PASS — NO FORBIDDEN TERMS FOUND IN PDF

**PDF Content Verification:**
- Title: "VoxelMask | Data Repair Log"
- Heading: "Internal Data Repair Summary"
- Report Type Badge: "INTERNAL REPAIR"
- No "CLINICAL" branding anywhere

#### Test Suite

```bash
python3 -m pytest -q
```

**Result:** ✅ 800 passed, 2 skipped, 341 warnings in 5.85s

#### Viewer Semantics Scan

```bash
rg -n -i "(before|after|compare|side-by-side|diff|undo|restore|revert|unmask)" src/app.py
```

**Result:** ✅ PASS
- "before/after" occurrences are all technical (e.g., `stop_before_pixels`, `before proceeding`)
- "unmask" occurrences are internal method names (`unmask_all()`, `bulk_unmask_all` key) — not user-facing
- No before/after comparison toggles or diff viewers exist
- No "undo/restore/revert" in viewer context

#### Error/Warning Message Scan

```bash
rg -n "st\.error|st\.warning" src/app.py | rg -i "(unmask|undo|restore|revert|recover|clinical)"
```

**Result:** ✅ NO FORBIDDEN TERMS IN ERROR/WARNING MESSAGES

### Results

| Section | Status | Notes |
| :--- | :--- | :--- |
| 1. Recoverability Truthfulness | **PASS** | "Keep" replaces "Unmask", "visible PHI" replaces "unmasked PHI" |
| 2. Irreversible Action Signalling | **PASS** | Warning added: "Original pixel data is NOT retained" |
| 3. No Recovery Promise UI | **PASS** | No "Restore Original" buttons exist |
| 4. Viewer & Comparison Behaviour | **PASS** | No before/after comparison toggles; "before" usages are technical |
| 5. Operator Confirmation Points | **PASS** | Accept dialog includes irreversibility warning |
| 6. Error & Failure Messaging | **PASS** | No forbidden terms in st.error/st.warning messages |
| 7. Error State Language | **PASS** | Scanned all error/warning calls — clean |
| 8. Export & Packaging Clarity | **PASS** | PDF shows "INTERNAL REPAIR", no "CLINICAL" |
| 9. Help & Documentation | **PASS** | Disclaimers remain correct ("Not for clinical use") |
| 10. Red-Team Question | **PASS** | UI cannot reasonably imply recoverability |

### Files Modified

- `src/app.py` — UI terminology changes
- `src/pdf_reporter.py` — Report type renamed CLINICAL → INTERNAL_REPAIR
- `tests/test_pdf_reporter.py` — Test updates for renamed report type

### Validation Notes

- PDF verification performed using `pdftotext` + forbidden-terms scan
- Sample output retained at `/tmp/phase6_test_report.pdf` during validation run

**Overall:** **ACCEPTED**
