# Phase 5b — Masking Correctness (Design Specification)

**Document Type:** Internal Design Artefact  
**Status:** Design Complete — No Implementation Approved  
**Phase Dependencies:**

* Phase 4 — OCR Detection ✅
* Phase 5a — Review Semantics ✅

**Audience:** PACS Engineering, Governance, Acquisition Due Diligence

---

## 1. Definition of Masking Correctness

### 1.1 Scope of Correctness

Masking correctness in VoxelMask is defined as the property that **pixel mutation, when eventually applied**, satisfies all of the following:

* Mutation affects **only regions explicitly approved** through a documented human review process or reviewer-endorsed deterministic policy
* Output is **visually deterministic** — identical inputs and decision sets produce identical outputs
* Source pixel data remains **recoverable** from preserved originals or quarantine archives
* Exported files remain **DICOM-valid and parseable** by downstream consumers

### 1.2 Explicit Exclusions from Correctness Claims

Masking correctness does **not** imply:

| Excluded Claim              | Rationale                                       |
| --------------------------- | ----------------------------------------------- |
| Guaranteed PHI removal      | Detection is systematic, not exhaustive         |
| Clinical fitness            | System is explicitly non-clinical               |
| Elimination of human review | Review is a governance requirement              |
| Detection completeness      | Phase 4 limitations are documented and accepted |

### 1.3 Correctness vs PHI Removal

| Correctness Scope                            | Not Correctness                         |
| -------------------------------------------- | --------------------------------------- |
| Predictable mutation of approved regions     | Autonomous removal of all detected text |
| Traceable decision-to-mutation chain         | Implicit "trust the output" posture     |
| Deterministic output per decision set        | Best-effort fuzzy processing            |
| Explicit documentation of non-masked regions | Silence about detection gaps            |

**Governance boundary:** Any correctness claim is scoped to the **decision set**, not the residual PHI state of the output.

---

## 2. Masking Eligibility Rules

### 2.1 Preconditions for Eligibility

Pixel mutation is eligible **only** when all conditions are met:

* Phase 4 detection output exists
* An active `ReviewSession` holds the current decision state
* Human review has occurred via:
  * Explicit reviewer acceptance, **or**
  * Reviewer-endorsed deterministic review policy with audit trail
* No blocking exclusions apply
* Export has not yet been triggered

### 2.2 Confidence and Zone Influence

| Confidence | Zone            | Eligibility Status                                                   |
| ---------- | --------------- | -------------------------------------------------------------------- |
| HIGH       | Body            | Eligible for **reviewer-proposed masking** under documented policy   |
| HIGH       | Header / Footer | Requires explicit reviewer confirmation                              |
| MEDIUM     | Any             | Requires explicit reviewer confirmation                              |
| LOW        | Any             | Flagged only — masking requires explicit override with justification |
| OCR_FAIL   | Any             | Not eligible — escalate or exclude                                   |

### 2.3 Absolute Exclusions

The following must **never** be masked without explicit, logged human override:

* LOW or OCR_FAIL confidence regions
* Footer regions on modalities with worksheet ambiguity (US, SC)
* Detection–review conflicts
* Images without confirmed decision sets

### 2.4 Blocking Exclusions

* Encapsulated PDFs
* Worksheet / document images
* Secondary captures with ambiguous provenance
* Images excluded by preflight policy

**Governance boundary:** The system may propose; the human must approve.

---

## 3. Header / Footer / Body Banding Strategy

### 3.1 Region Classification

| Region | Characteristic                         | Masking Posture                               |
| ------ | -------------------------------------- | --------------------------------------------- |
| Header | Branding, identifiers, metadata        | High-risk — explicit review required          |
| Footer | Timestamps, operator IDs, possible PHI | Ambiguous — explicit review required          |
| Body   | Primary imaging content                | Lower incidental risk — review still required |

### 3.2 Conservative Treatment

* Header/footer regions are **never** policy-masked without reviewer action
* OCR detections in these regions are **flagged**, not auto-proposed
* No assumption of cross-institution or cross-vendor stability

### 3.3 Worksheet Handling

* Worksheet detection is **heuristic and conservative**
* False negatives are acceptable, documented residual risk
* When heuristics trigger:
  * UI flags *"Document — Review Recommended"*
  * Excluded from policy-guided masking
  * Reviewer disposition logged in audit trail

---

## 4. Series Order & Cine Preservation

### 4.1 Governance Rationale

* Imaging studies are ordered sequences
* Order disruption undermines completeness and trust
* FOI and legal contexts require frame fidelity

### 4.2 Preservation Requirements

| Requirement        | Description                           |
| ------------------ | ------------------------------------- |
| Order fidelity     | Exported frames preserve source order |
| Gap documentation  | Exclusions logged with rationale      |
| Index traceability | Source and export indices recorded    |
| Cine integrity     | Multi-frame sequences remain playable |

### 4.3 Dependency Rule

**Pixel mutation is not approvable** until series order preservation is demonstrated and tested.

---

## 5. Auditability Model (Future-Facing)

### 5.1 Required Audit Fields

* Source SOPInstanceUID
* Exported SOPInstanceUID
* Region identifier sufficient to deterministically reproduce the decision
* Mask method (method selection subject to separate approval)
* Reviewer / session identifier
* Timestamp
* Detection confidence
* Zone classification
* Origin (detected vs manual)

### 5.2 Source Recoverability

* Original pixels preserved or retrievable
* "Recoverability" refers to **source retrieval**, not mutation reversal
* Source hashes recorded for tamper detection

### 5.3 Audit Trail Integrity

* Append-only
* Timestamped
* Human-readable export supported

**Governance boundary:** Audit schema must be finalised **before** masking implementation.

---

## 6. Explicit Non-Goals

* Real-time PACS routing
* Write-back to PACS
* Clinical use claims
* Guaranteed PHI removal
* Masking without review
* Multi-frame mutation before order enforcement
* Footer PHI learning
* Autonomous worksheet exclusion

---

**Phase 5b (Design) is complete.**  
**No masking implementation may proceed without explicit reference to this document.**
