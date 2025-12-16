# Gate 3 — Audit Completeness

**Design Phase (No Execution)**

---

## Document Metadata

| Field            | Value                                      |
| ---------------- | ------------------------------------------ |
| Gate             | 3                                          |
| Phase            | 5c                                         |
| Status           | Design Complete                            |
| Author           | VoxelMask Governance                       |
| Created          | 2025-12-16                                 |
| Execution Auth   | Blocked until Phase 5c design triad closes |

---

## 1. Purpose of Gate 3

Gate 3 defines the **minimum sufficient evidence set** required to credibly answer the question:

> "Did VoxelMask do enough — and not too much — to be defensible under audit, FOI, and governance review?"

This gate does **not** add new capabilities.
It **constrains and formalises** what must already be produced by Gates 1 and 2.

---

## 2. Core Design Principle

### Audit Completeness ≠ Maximal Logging

Gate 3 explicitly rejects:

* "Log everything just in case"
* Retaining PHI-adjacent artefacts indefinitely
* Developer-centric debug exhaust

Instead, it defines:

* **What evidence is required**
* **For which audience**
* **For how long**
* **At what granularity**

> Completeness is defined by *defensibility*, not curiosity.

---

## 3. Audit Audiences (Explicit)

Gate 3 introduces **audience-scoped completeness**, because "audit" is not monolithic.

### 3.1 Audit Audience Classes

| Audience             | Characteristics             | Risk            |
| -------------------- | --------------------------- | --------------- |
| Internal Ops         | Technical, trusted          | Over-logging    |
| Governance / Privacy | Non-technical, risk-focused | Ambiguity       |
| FOI Officer          | Procedural, adversarial     | Missing proof   |
| External Auditor     | Formal, standards-driven    | Inconsistency   |
| Acquisition DD       | Skeptical, time-limited     | Over-complexity |

Gate 3 ensures **one artefact set** can answer all of them *without branching logic*.

---

## 4. Definition of "Audit-Complete"

A VoxelMask job is **audit-complete** if and only if:

1. **Every discovered SOP Instance is accounted for**
   * Even if skipped or failed

2. **Every action taken has a recorded reason**

3. **Every mutation is provable without reversibility**

4. **The system state that made the decision is reconstructable**

5. **Artefacts are internally consistent and tamper-evident**

6. **Retention posture is explicit and enforced**

If *any* of these fail → the job is **audit-incomplete**, even if masking "worked".

---

## 5. Gate 3 Completeness Dimensions

Gate 3 evaluates completeness across **six dimensions**:

### 5.1 Coverage Completeness

* All input instances appear in `gate2_object_record`
* No "silent drops"
* Count reconciliation:
  * discovered vs processed vs output

### 5.2 Decision Completeness

* Every object has:
  * `action_taken`
  * ≥1 `reason_code`
* "NO_CHANGE" is an explicit decision, not absence of data

### 5.3 Evidence Completeness

* If `PIXEL_MASKED`:
  * mask plan exists
  * before/after hashes exist

* If `METADATA_ONLY`:
  * header diff evidence exists

* If `SKIPPED` or `FAILED`:
  * rationale and error context recorded

### 5.4 Configuration Completeness

* Immutable config snapshot captured
* Algorithm versions recorded
* Thresholds and rules frozen per run

### 5.5 Integrity Completeness

* Hashes present for:
  * datasets
  * pixel data (if touched)
  * evidence blobs
* Manifest-level signing present
* No unsigned artefact paths

### 5.6 Retention Completeness

* Retention policy declared
* Purge date computable
* PHI-containing artefacts flagged (ideally zero)

---

## 6. Explicit Non-Goals of Gate 3

Gate 3 **does not**:

* Judge masking quality
* Decide detection correctness
* Re-run algorithms
* Add new artefacts
* Introduce recoverability

It only answers:

> "Is the *evidence produced* sufficient, bounded, and defensible?"

---

## 7. Gate 3 Outputs (Design-Level)

Gate 3 introduces **no new raw artefacts**, only **derived assertions**:

### 7.1 Audit Completeness Report (Logical)

A structured evaluation result, e.g.:

```json
{
  "audit_complete": true,
  "failed_dimensions": [],
  "warnings": [],
  "completeness_score": null
}
```

Fields:

| Field                 | Type          | Description                                  |
| --------------------- | ------------- | -------------------------------------------- |
| `audit_complete`      | boolean       | Overall pass/fail                            |
| `failed_dimensions`   | string[]      | List of dimensions that failed validation    |
| `warnings`            | string[]      | Non-blocking concerns                        |
| `completeness_score`  | number | null | Optional numeric score (non-marketing)       |

### 7.2 Operator-Facing Summary (Human)

Plain-language statements such as:

* "All 312 instances were processed and accounted for."
* "47 instances were pixel-masked with verifiable evidence."
* "No recoverable PHI was retained."
* "This job meets FOI evidentiary requirements."

> This is *not* a compliance claim — it's a transparency summary.

---

## 8. Failure Semantics (Important)

Gate 3 failures are **non-fatal but blocking**:

* Masking may have occurred
* Output may exist
* **But export, attestation, or sign-off must be blocked**

This preserves:

* Safety
* Governance posture
* Credibility under scrutiny

### 8.1 Failure Response Matrix

| Failure Type              | System Response                          | Operator Action Required |
| ------------------------- | ---------------------------------------- | ------------------------ |
| Coverage gap              | Export blocked, warning raised           | Review missing instances |
| Decision gap              | Export blocked, validation failed        | Complete decision audit  |
| Evidence gap              | Export blocked, attestation unavailable  | Re-process or escalate   |
| Configuration gap         | Warning, reduced auditability            | Document manually        |
| Integrity gap             | Export blocked, tamper concern           | Investigate immediately  |
| Retention gap             | Warning, policy non-compliance           | Update retention config  |

---

## 9. Relationship to Gates 1 & 2

Gate 3 is a **closure gate**:

| Gate   | Role                                                |
| ------ | --------------------------------------------------- |
| Gate 1 | "Did we preserve order and fidelity?"               |
| Gate 2 | "Can we prove what changed without storing PHI?"    |
| Gate 3 | "Is the total evidence set sufficient and bounded?" |

Only when **all three** are satisfied does VoxelMask cross from *technical success* to *audit-grade success*.

### 9.1 Gate Dependency Chain

```
Gate 1 (Series Order Preservation)
    ↓ produces artefacts
Gate 2 (Source Non-Recoverability)  
    ↓ constrains evidence
Gate 3 (Audit Completeness)
    ↓ validates sufficiency
Export / Attestation Unlocked
```

---

## 10. Completeness Validation Checklist

For implementation, Gate 3 validation must check:

### 10.1 Coverage Validation

- [ ] Input manifest exists and is non-empty
- [ ] All SOPInstanceUIDs from input appear in object record
- [ ] Count: `discovered == processed + skipped + failed`
- [ ] No orphaned output files (output without input record)

### 10.2 Decision Validation

- [ ] Every object has non-null `action_taken`
- [ ] Every object has ≥1 `reason_code`
- [ ] No `action_taken` value is "UNKNOWN" or empty
- [ ] `NO_CHANGE` decisions have explicit reasoning

### 10.3 Evidence Validation

- [ ] `PIXEL_MASKED` objects have mask plan reference
- [ ] `PIXEL_MASKED` objects have before/after pixel hashes
- [ ] `METADATA_ONLY` objects have header diff evidence
- [ ] `SKIPPED` objects have skip reason
- [ ] `FAILED` objects have error context

### 10.4 Configuration Validation

- [ ] Config snapshot exists for run
- [ ] Algorithm version recorded
- [ ] Threshold values frozen
- [ ] Profile/mode recorded

### 10.5 Integrity Validation

- [ ] All artefacts have SHA-256 hashes
- [ ] Manifest hash covers all component hashes
- [ ] No file modified after hash computation
- [ ] Signing chain complete (if applicable)

### 10.6 Retention Validation

- [ ] Retention policy declared in config
- [ ] Purge date calculable from policy + run date
- [ ] PHI flag present on all artefacts (should be zero)
- [ ] No transient/temp files remain

---

## 11. Artefact Inventory (Gate 3 Scope)

Gate 3 does not create artefacts but validates the following exist and are complete:

| Artefact                      | Source Gate | Validated By Gate 3           |
| ----------------------------- | ----------- | ----------------------------- |
| `gate1_series_manifest.json`  | Gate 1      | Coverage, Integrity           |
| `gate2_object_record.json`    | Gate 2      | Coverage, Decision, Evidence  |
| `config_snapshot.json`        | Runtime     | Configuration                 |
| Mask plans                    | Processing  | Evidence                      |
| Hash records                  | Gate 2      | Integrity                     |
| Retention policy              | Config      | Retention                     |

---

## 12. Phase Boundary

**After Gate 3 design is persisted:**

* Execution of Gates 1–3 may be authorised
* Schema, validators, and checks can be implemented
* Operator workflows may be finalised

**Before that:**

* No implementation
* No UI claims
* No export guarantees

---

## 13. Design Triad Completion Status

With this document, the Phase 5c design triad is **complete**:

| Gate   | Document                                      | Status          |
| ------ | --------------------------------------------- | --------------- |
| Gate 1 | `PHASE5C_GATE1_SERIES_ORDER_PRESERVATION.md`  | ✅ Complete     |
| Gate 2 | `PHASE5C_GATE2_SOURCE_RECOVERABILITY.md`      | ✅ Complete     |
| Gate 3 | `PHASE5C_GATE3_AUDIT_COMPLETENESS.md`         | ✅ Complete     |

**Execution of Phase 5c implementation is now formally unlocked.**

---

## 14. Approval Record

| Role                | Name | Date | Signature |
| ------------------- | ---- | ---- | --------- |
| Design Lead         |      |      |           |
| Governance Lead     |      |      |           |
| Technical Reviewer  |      |      |           |

---

*End of Gate 3 Design Document*
