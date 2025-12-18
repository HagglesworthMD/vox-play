# Phase 12 — Activation Declaration

---

## 1. Declaration

| Field | Value |
|-------|-------|
| **Activation Date** | 2025-12-18T01:16:00Z |
| **Baseline Tag** | `v0.9.0-phase9-operator-pack` |
| **Activation Basis** | Binary checklist closure (50 / 50 gates PASS) |
| **Checklist Reference** | `docs/PHASE12_ACTIVATION_CHECKLIST.md` |

**Statement:**

Phase 12 is activated. VoxelMask transitions from internal pilot artefact to externally legible evaluation product.

The system may be used by non-authors, without explanation, without breaking governance, semantics, or audit posture.

---

## 2. Scope (Affirmed)

Phase 12 activation affirms the following scope constraints:

| Constraint | Status |
|------------|--------|
| Non-clinical | Affirmed |
| Copy-out only | Affirmed |
| Evaluation / pilot usage | Affirmed |
| Source data not modified | Affirmed |
| PACS authoritative | Affirmed |

VoxelMask does not claim to be a clinical system, a regulatory-certified de-identification tool, or a production PACS component.

---

## 3. What Phase 12 Is Not

Phase 12 activation does **not** permit or imply:

| Exclusion | Status |
|-----------|--------|
| Clinical routing | Forbidden |
| Write-back to PACS | Forbidden |
| Background automation | Forbidden |
| Claims of completeness | Forbidden |
| Claims of regulatory compliance | Forbidden |
| "AI" marketing framing | Forbidden |
| Performance guarantees | Forbidden |
| Workflow shortcuts bypassing review | Forbidden |

Phase 12 does not relax safety. It exposes safety to scrutiny.

---

## 4. Governance Locks

The following governance constraints remain in effect and are not revisited by Phase 12:

| Lock | Reference |
|------|-----------|
| UI language freeze | `FREEZE_LOG.md` (Phase 6) |
| Evidence schema freeze | `PHASE5C_GATE2_EVIDENCE_BUNDLE_SCHEMA.md` |
| Recoverability model (Model B) | `PHASE5C_GATE2_DECISION_RECORD.md` |
| Processing semantics freeze | `FREEZE_LOG.md` (Phase 5C Close-Out) |
| Change control | `RELEASE_FREEZE_v0.4.0.md` |

Any modification to the above requires a new phase declaration and explicit governance approval.

---

## 5. Distribution Posture

Phase 12 permits the following distribution activities:

| Activity | Permitted |
|----------|-----------|
| Internal distribution to imaging teams | Yes |
| Pilot evaluations without hand-holding | Yes |
| Cold-reader artefact review | Yes |
| Vendor curiosity (non-warranty) | Yes |
| "Have a look at this tool" conversations | Yes |

Phase 12 does **not** permit:

| Activity | Permitted |
|----------|-----------|
| Clinical deployment | No |
| Production routing | No |
| Unsupervised batch processing | No |
| Claims of regulatory certification | No |
| External marketing | No |

---

## 6. Reversion Clause

Phase 12 activation is revoked if any of the following occur:

- Breach of scope constraints (Section 2)
- Violation of exclusions (Section 3)
- Modification of governance locks without new phase declaration
- Discovery of checklist gate failure not identified during activation

Upon revocation, VoxelMask reverts to pre-Phase-12 posture (internal pilot only, author-supervised).

Reversion does not require new code. It requires explicit declaration.

---

## 7. References

### Activation Basis

| Document | Purpose |
|----------|---------|
| `PHASE12_ACTIVATION_CHECKLIST.md` | Binary pass/fail gates (50 gates) |

### Governance Artefacts

| Document | Purpose |
|----------|---------|
| `FREEZE_LOG.md` | Freeze history and change control |
| `PHASE5C_GATE2_DECISION_RECORD.md` | Recoverability model decision |
| `PHASE5C_GATE2_EVIDENCE_BUNDLE_SCHEMA.md` | Audit evidence schema |
| `PHASE4_KNOWN_LIMITATIONS.md` | OCR and detection limitations |
| `PHASE4_NON_GOALS.md` | Explicit scope exclusions |

### Operator Documentation

| Document | Purpose |
|----------|---------|
| `ARTEFACT_INDEX.md` | Navigation guide by role |
| `phase9_operator_pack/PILOT_README.md` | Operator getting started |
| `phase9_operator_pack/OPERATOR_CHECKLIST.md` | Pre/post-run checklist |
| `phase9_operator_pack/RUNBOOK_TROUBLESHOOTING.md` | Failure triage |

---

## Document Metadata

| Field | Value |
|-------|-------|
| Version | 1.0 |
| Created | 2025-12-18 |
| Classification | Governance / Activation |
| Audience | Internal governance, PACS management, vendor diligence |

---

*This document declares activation. It does not promise capability, performance, or regulatory status.*
