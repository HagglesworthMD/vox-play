# Gate 3 — Audit Completeness

**Status:** EXECUTABLE — Verification method defined

---

## Document Metadata

| Field            | Value                                      |
| ---------------- | ------------------------------------------ |
| Gate             | 3                                          |
| Phase            | 5c                                         |
| Status           | **Executable** (verification method bound) |
| Author           | VoxelMask Governance                       |
| Created          | 2025-12-16                                 |
| Updated          | 2025-12-16                                 |
| Execution Auth   | Unlocked — schema + tests in place         |

---

## 1. Purpose of Gate 3

Gate 3 defines the **minimum sufficient evidence set** required to credibly answer the question:

> "Did VoxelMask do enough — and not too much — to be defensible under audit, FOI, and governance review?"

This gate does **not** add new capabilities.
It **constrains and formalises** what must already be produced by Gates 1 and 2.

---

## 2. Gate 3 Verification Method (Normative)

**Gate 3 SHALL be evaluated by validating a produced Evidence Bundle against:**

| Reference | Purpose | Location |
|-----------|---------|----------|
| Schema Contract | Defines required structure, files, and formats | `docs/PHASE5C_GATE2_EVIDENCE_BUNDLE_SCHEMA.md` |
| Reference Validator | Executable test suite | `tests/test_gate3_bundle_schema.py` |

### 2.1 Gate 3 Pass/Fail Rule

**Gate 3 PASS requires ALL of the following:**

| Requirement | Validation |
|-------------|------------|
| Evidence bundle schema validation passes | All required structure/files/hashes present |
| Model B constraints are satisfied | No stored pixels, no recovered PHI text |
| Audit completeness checks pass | Coverage/decision/linkage/config completeness |
| All hash integrity checks pass | Every file validates against its `.sha256` |

**Gate 3 FAIL if ANY of the above fail.** Processing output may exist, but attestation/export is blocked.

### 2.2 Verification Execution

```bash
# Execute Gate 3 verification against a produced bundle
pytest tests/test_gate3_bundle_schema.py -v --bundle-path=<EVIDENCE_BUNDLE_DIR>
```

Or programmatically via the validation functions in `src/audit/evidence_bundle.py`.

---

## 3. Core Design Principle

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

## 6. Gate 3 Completeness Dimensions

Gate 3 evaluates completeness across **six dimensions**, each mapped to executable tests:

### 6.1 Coverage Completeness

**Test Group:** `TestAuditCompleteness` in `test_gate3_bundle_schema.py`

| Check | Evidence Location | Test |
|-------|-------------------|------|
| All input instances appear in source index | `INPUT/source_index.json` | `test_coverage_completeness` |
| No "silent drops" | `MANIFEST.json` counts | `test_coverage_completeness` |
| Count reconciliation | `MANIFEST.json` vs `INPUT/*.csv` | `test_coverage_completeness` |

### 6.2 Decision Completeness

**Test Group:** `TestAuditCompleteness` in `test_gate3_bundle_schema.py`

| Check | Evidence Location | Test |
|-------|-------------------|------|
| Every object has decision | `DECISIONS/decision_log.jsonl` | `test_decision_completeness` |
| Reason recorded | `DECISIONS/masking_actions.jsonl` | `test_decision_completeness` |
| "NO_CHANGE" is explicit | `DECISIONS/decision_log.jsonl` | `test_decision_completeness` |

### 6.3 Evidence Completeness

**Test Group:** `TestModelBConstraints` + `TestAuditCompleteness` in `test_gate3_bundle_schema.py`

| Check | Evidence Location | Test |
|-------|-------------------|------|
| `PIXEL_MASKED`: action exists | `DECISIONS/masking_actions.jsonl` | `test_decision_completeness` |
| `PIXEL_MASKED`: hashes exist | `INPUT/source_hashes.csv` | `test_source_hashes_present` |
| Linkage recorded | `LINKAGE/instance_linkage.csv` | `test_linkage_completeness` |
| Exceptions logged | `QA/exceptions.jsonl` | Schema validation |

### 6.4 Configuration Completeness

**Test Group:** `TestAuditCompleteness` in `test_gate3_bundle_schema.py`

| Check | Evidence Location | Test |
|-------|-------------------|------|
| Config snapshot exists | `CONFIG/profile.json` | `test_config_completeness` |
| Algorithm version recorded | `CONFIG/app_build.json` | `test_config_completeness` |
| Thresholds frozen | `CONFIG/profile.json` | `test_config_completeness` |

### 6.5 Integrity Completeness

**Test Group:** `TestHashIntegrity` + `TestBundleTree` in `test_gate3_bundle_schema.py`

| Check | Evidence Location | Test |
|-------|-------------------|------|
| All artefacts have SHA-256 hashes | `*.sha256` companion files | `test_all_file_hashes_valid` |
| Manifest hash validates | `MANIFEST.json.sha256` | `test_manifest_hash_valid` |
| Bundle tree sorted and valid | `SIGNATURE/bundle_tree.txt` | `test_bundle_tree_sorted` |

### 6.6 Retention Completeness

**Test Group:** `TestManifestValidation` in `test_gate3_bundle_schema.py`

| Check | Evidence Location | Test |
|-------|-------------------|------|
| Retention policy declared | `CONFIG/profile.json` | `test_config_completeness` |
| Model B constraints enforced | `MANIFEST.json` constraints | `test_manifest_constraints_model_b` |
| No PHI stored | Detection results | `test_detection_results_no_phi_text` |

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

## 12. Artefact Inventory (Gate 3 Scope)

Gate 3 validates the **Model B Evidence Bundle** structure defined in `PHASE5C_GATE2_EVIDENCE_BUNDLE_SCHEMA.md`:

| Directory | Contents | Validated |
|-----------|----------|----------|
| `CONFIG/` | `profile.json`, `app_build.json`, `runtime_env.json` | Configuration completeness |
| `INPUT/` | `source_index.json`, `source_hashes.csv` | Coverage, Evidence |
| `OUTPUT/` | `masked_index.json`, `masked_hashes.csv` | Coverage |
| `DECISIONS/` | `detection_results.jsonl`, `masking_actions.jsonl`, `decision_log.jsonl` | Decision, Evidence |
| `LINKAGE/` | `instance_linkage.csv` | Coverage, Evidence |
| `QA/` | `exceptions.jsonl`, `verification_report.json` | Coverage, Integrity |
| `SIGNATURE/` | `bundle_tree.txt` | Integrity |
| Root | `MANIFEST.json` | All dimensions |

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

## 14. Gate Triad Execution Status

Phase 5c governance gates:

| Gate   | Document                                      | Design | Execution |
| ------ | --------------------------------------------- | ------ | --------- |
| Gate 1 | `PHASE5C_GATE1_SERIES_ORDER_PRESERVATION.md`  | ✅     | ✅ PASSED |
| Gate 2 | `PHASE5C_GATE2_DECISION_RECORD.md`            | ✅     | ✅ Model B Accepted |
| Gate 3 | `PHASE5C_GATE3_AUDIT_COMPLETENESS.md`         | ✅     | ⏳ Verification method bound |

**Gate 3 execution:** Run `pytest tests/test_gate3_bundle_schema.py -v` against any produced evidence bundle.

### Supporting Artefacts

| Artefact | Purpose |
|----------|--------|
| `PHASE5C_GATE2_EVIDENCE_BUNDLE_SCHEMA.md` | On-disk bundle schema |
| `PHASE5C_GATE2_ARTIFACT_CHECKLIST.md` | Evidence requirements |
| `src/audit/evidence_bundle.py` | Bundle generator |
| `tests/test_gate3_bundle_schema.py` | 21 validation tests |

---

## 14. Approval Record

| Role                | Name | Date | Signature |
| ------------------- | ---- | ---- | --------- |
| Design Lead         |      |      |           |
| Governance Lead     |      |      |           |
| Technical Reviewer  |      |      |           |

---

*End of Gate 3 Design Document*
