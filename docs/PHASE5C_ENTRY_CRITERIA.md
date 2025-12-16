# Phase 5c — Masking Enablement Entry Criteria

**Document Type:** Governance Gate Checklist  
**Status:** Active — Blocks Implementation  
**Purpose:** Define mandatory preconditions before any pixel mutation is approved

---

## Guiding Principle

> No pixel shall be modified until every criterion below is **demonstrably satisfied** and **documented**.

This is not a feature checklist. It is a **risk gate**.

---

## 1. Series Order Preservation (Trust Prerequisite)

| Criterion | Verification Method |
|-----------|---------------------|
| Exported frames preserve source Instance Number order | Automated test with multi-frame study |
| Excluded frames are logged with original position | Audit log inspection |
| Cine sequences remain playable after export | Manual verification on DICOM viewer |
| No frame duplication or omission occurs | Hash comparison of source vs export manifest |

**Gate status:** ⬜ Not demonstrated

---

## 2. Source Recoverability

| Criterion | Verification Method |
|-----------|---------------------|
| Original pixel data is preserved before any mutation | Quarantine archive exists and is populated |
| Recovery path is documented and tested | Manual recovery of test case |
| Source hash is recorded per frame | Audit log contains hash field |

**Gate status:** ⬜ Not demonstrated

---

## 3. Audit Schema Completeness

| Criterion | Verification Method |
|-----------|---------------------|
| All required audit fields from Phase 5b §5.1 are implemented | Schema review against spec |
| Audit log is append-only | Attempted modification fails or is logged |
| Audit log is exportable in human-readable format | Export and manual inspection |
| Region identifiers are sufficient for decision reproduction | Test: given audit log, reproduce mask decision |

**Gate status:** ⬜ Not demonstrated

---

## 4. Review Session Integrity

| Criterion | Verification Method |
|-----------|---------------------|
| Export is blocked until explicit reviewer acceptance | UI test: attempt export without accept |
| Decision set is immutable once accepted | Attempt modification after accept fails |
| Reviewer action is logged with session ID | Audit log inspection |
| Conflict between detection and review blocks export | Test with conflicting state |

**Gate status:** ⬜ Not demonstrated

---

## 5. Masking Eligibility Enforcement

| Criterion | Verification Method |
|-----------|---------------------|
| LOW/OCR_FAIL regions cannot be auto-masked | Automated test with LOW confidence region |
| Header/footer regions require explicit confirmation | UI test: attempt policy-mask on header |
| Blocking exclusions (PDF, worksheet) prevent masking | Automated test with excluded types |
| Confidence and zone influence eligibility per Phase 5b §2.2 | Matrix test |

**Gate status:** ⬜ Not demonstrated

---

## 6. DICOM Validity Post-Mutation

| Criterion | Verification Method |
|-----------|---------------------|
| Masked files remain DICOM-valid | Validation tool (e.g., dciodvfy) |
| Masked files are parseable by reference viewers | Test on OsiriX, Horos, or equivalent |
| No unintended metadata mutation occurs | Diff of pre/post metadata |
| Transfer syntax is preserved or explicitly converted | Automated check |

**Gate status:** ⬜ Not demonstrated

---

## 7. Test Coverage

| Criterion | Verification Method |
|-----------|---------------------|
| Unit tests exist for masking eligibility logic | Test suite review |
| Integration test covers full detection → review → mask → export path | CI pass |
| Edge cases documented in Phase 5b are covered | Test matrix vs spec |
| Failure modes produce explicit, logged rejections | Test with invalid inputs |

**Gate status:** ⬜ Not demonstrated

---

## 8. Documentation & Governance Sign-Off

| Criterion | Verification Method |
|-----------|---------------------|
| Phase 5b design spec is referenced in implementation | Code comments or PR description |
| Known limitations are documented in user-facing materials | README or release notes |
| Rollback path exists if masking is disabled post-release | Documented procedure |
| Internal stakeholder review complete (if applicable) | Sign-off record |

**Gate status:** ⬜ Not demonstrated

---

## 9. Non-Clinical Assertion & Scope Lock

| Criterion | Verification Method |
|-----------|---------------------|
| Masking feature is explicitly labelled non-clinical | UI text / documentation review |
| No clinical workflow references exist | Search for RIS / reporting / diagnostic language |
| Export outputs are marked for research / FOI use only | Metadata flag or documentation |
| No claims of diagnostic suitability are present | README / release notes review |

**Gate status:** ⬜ Not demonstrated

**Governance boundary:** Any clinical framing blocks masking enablement regardless of technical readiness.

---

## Gate Decision (Do Not Proceed Until All Pass)

| Section | Status |
|---------|--------|
| 1. Series Order Preservation | ⬜ |
| 2. Source Recoverability | ⬜ |
| 3. Audit Schema Completeness | ⬜ |
| 4. Review Session Integrity | ⬜ |
| 5. Masking Eligibility Enforcement | ⬜ |
| 6. DICOM Validity Post-Mutation | ⬜ |
| 7. Test Coverage | ⬜ |
| 8. Documentation & Governance | ⬜ |
| 9. Non-Clinical Scope Lock | ⬜ |

**Overall gate status:** 🔴 **NOT PASSED**

---

## Explicit Rule

> Masking implementation may **only** begin when **all nine sections** show ✅.
> 
> Partial progress does not unlock implementation.
> This gate is **binary**.

---

**Phase 5c is a governance gate, not a delivery phase.**  
**Any masking code without a green gate is a process violation.**
