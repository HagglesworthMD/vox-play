# Phase 7 — Pilot Evaluation Checklist

**Scope:** Usage observations only
**Explicitly out of scope:** Feature requests, performance tuning, UI redesign, automation

This checklist is used to evaluate *how VoxelMask is used and understood* during an internal pilot.
No code or behavioural changes are expected during Phase 7.

---

## 1. Operator Understanding

Confirm whether operators:

* ☐ Correctly understand that VoxelMask is **copy-out only**
* ☐ Do not expect any PACS write-back or clinical correction
* ☐ Understand that masking is **irreversible** in exported artefacts
* ☐ Can explain the difference between *detected*, *kept*, and *masked* regions

**Notes:**

---

## 2. Workflow Comprehension

Observe whether operators:

* ☐ Follow the intended upload → review → accept → export flow
* ☐ Pause at the explicit acceptance step
* ☐ Recognise that review is mandatory, not optional
* ☐ Avoid attempting to use the viewer as a diagnostic tool

**Notes:**

---

## 3. Language & Semantics

Verify that users:

* ☐ Do not describe actions as "undo", "restore", or "fix"
* ☐ Use "keep" and "mask" consistently
* ☐ Do not refer to outputs as "corrected" images
* ☐ Do not interpret the tool as clinical or diagnostic

**Notes:**

---

## 4. Error & Warning Interpretation

Assess whether:

* ☐ Warning messages are understood as *operational*, not corrective
* ☐ Partial failures are recognised and respected
* ☐ Users do not assume silent recovery or automatic correction
* ☐ Audit logs are consulted when warnings occur

**Notes:**

---

## 5. Audit Artefact Usage

Confirm that reviewers:

* ☐ Can locate audit artefacts without guidance
* ☐ Understand what decisions are recorded
* ☐ Can trace operator intent via logs
* ☐ Do not expect audit artefacts to justify clinical decisions

**Notes:**

---

## 6. Governance Alignment

Evaluate whether governance stakeholders:

* ☐ Agree the tool is appropriately framed as non-clinical
* ☐ Are comfortable with irreversible masking semantics
* ☐ Understand stated limitations and exclusions
* ☐ Can identify where responsibility lies (operator vs tool)

**Notes:**

---

## 7. Misuse & Drift Signals (Red Flags)

Record any instances where:

* ☐ Users attempt to compare "before" and "after" images clinically
* ☐ Users request recovery of masked content
* ☐ Users bypass review steps
* ☐ Users treat outputs as clinically authoritative

**Notes:**

---

## 8. Documentation Effectiveness

Assess whether:

* ☐ README_PILOT.md is read and understood
* ☐ DEPLOYMENT_NOTES.md answers common IT questions
* ☐ PILOT_HANDOFF.md matches observed behaviour
* ☐ Additional explanation is repeatedly required (note where)

**Notes:**

---

## 9. Exit Criteria (Phase 7 Complete)

Phase 7 may be considered complete when:

* ☐ No semantic misunderstandings are observed
* ☐ No recoverability expectations emerge
* ☐ Governance reviewers raise no framing objections
* ☐ Pilot findings are limited to usage observations

**Outcome:**

* ☐ Proceed to broader internal evaluation
* ☐ Proceed to external discussion
* ☐ Stop / hold pending governance review

---

## 10. Explicit Non-Actions

During Phase 7, the following must **not** occur:

* ⛔ Feature additions
* ⛔ UX wording changes
* ⛔ Performance optimisation
* ⛔ Automation of review steps
* ⛔ Claims of PHI completeness

Any request in these categories should be logged and deferred.

---

**Phase 7 Principle:**

> *We are evaluating understanding, not improving capability.*
