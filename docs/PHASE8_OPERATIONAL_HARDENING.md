# PHASE 8 — Operational Hardening (Pilot-Safe)

**Document ID:** PHASE8_OPERATIONAL_HARDENING  
**Status:** Draft (ready to commit)  
**Applies to:** VoxelMask pilot / internal evaluation builds  
**Audience:** PACS engineers, imaging ops, governance reviewers  
**Last updated:** 2025-12-18

---

## 0. Purpose

Phase 8 hardens VoxelMask operationally **without changing any de-identification semantics**.

This phase is about making the tool **boringly reliable** for internal evaluation:
- predictable startup
- safer temp / workspace hygiene
- clearer version + configuration capture
- guardrails that reduce operator error
- better "what happened" evidence for audit

**Not in scope:** new de-id logic, new detection behaviour, UI redesign, performance tuning that changes outcomes.

---

## 1. Preservation Guarantee (Phase 7)

Phase 7 pilot evaluation completed with **PASS** across all sections.

**Phase 8 must preserve Phase 7 behaviour.**
- No change to masking decisions
- No change to metadata anonymisation outputs
- No change to inclusion/exclusion logic
- No change to evidence bundle structure (unless it is strictly additive and documented)

**Decision rule:**  
If a change could alter what an operator *believes* is happening, it is **not Phase 8**.

---

## 2. Scope

### 2.1 In scope (allowed)

Operational hardening that is:
- deterministic
- testable
- audit-friendly
- does not alter de-id outcomes

Allowed categories:

1) **Startup checks & preflight**
- environment validation (dependencies, permissions)
- writable paths verification
- disk space preflight
- sanity checks on mode flags (pilot / research)

2) **Temp + workspace hygiene**
- predictable temp directories
- safe cleanup rules
- collision resistance (unique run IDs)
- optional retention for debugging (explicitly enabled)

3) **Configuration + version capture**
- capture app version, git commit (if available)
- capture anonymisation profile id / name
- capture OCR engine info + thresholds used
- capture runtime environment summary (OS, Python)

4) **Audit log robustness**
- ensure audit logs are always written (or fail closed)
- improve integrity linking between run log and bundle
- clearer operator-facing "receipt" content (without semantic claims)

5) **Operational failure modes**
- fail early, fail loudly, fail safe
- no partial output without explicit "incomplete run" marking
- explicit exit codes

### 2.2 Out of scope (explicit non-goals)

Phase 8 MUST NOT:
- change detection thresholds or heuristics
- change any anonymisation mapping rules
- alter which instances/series are processed
- add new SOP Class behaviours
- change UI meaning, labels, or operator language semantics
- add PACS write-back, auto-routing, or clinical workflow integration
- promise "complete PHI removal" or any clinical-grade guarantee
- add "smart" or learning behaviour

If it sounds like a feature, it's probably not Phase 8.

---

## 3. Pilot Safety Constraints

VoxelMask remains **copy-out only** for pilot/internal evaluation:
- No modification of studies in PACS
- No automatic forwarding into clinical storage
- No background routing
- Outputs stored to evaluation-designated paths only

Phase 8 cannot introduce:
- silent data movement
- unattended scheduling
- "watch folder" auto-export without explicit operator invocation

---

## 4. Phase 8 Work Items

### 4.1 Startup Preflight Gate (Hard Fail)

Add a preflight step that runs before processing begins.

**Checks (minimum):**
- Output directory exists or can be created
- Output directory is writable
- Temp directory is writable
- Sufficient free disk space for worst-case run (configurable conservative estimate)
- Required dependencies available (OCR backend, pydicom, etc.)
- Mode flag sanity: Pilot vs Research must be explicit

**Behaviour:**
- If any check fails: do not process anything; exit with non-zero code
- Preflight results must be logged (audit log + console summary)

**Acceptance criteria:**
- Preflight fails are clear, actionable, and deterministic
- No partial evidence bundle created on preflight fail
- Preflight info is included in the audit receipt

---

### 4.2 Deterministic Run Identity + Path Layout

Introduce a run identifier used across:
- output bundle directory name
- audit log record key
- receipt

**Run ID format (suggested):**
- `VM_RUN_YYYYMMDD_HHMMSS_<short-rand>` OR a UUIDv4
- Must be unique

**Directory layout (example):**
- `<output_root>/voxelmask_runs/<run_id>/`
  - `bundle/`
  - `logs/`
  - `receipts/`
  - `tmp/` (optional; see 4.3)

**Acceptance criteria:**
- Two runs cannot collide
- A run directory is either complete or explicitly marked incomplete
- Run ID appears in every relevant artefact

---

### 4.3 Temp Hygiene & Retention Policy

Ensure temp artefacts do not leak beyond what is required.

**Rules:**
- Default: delete temp artefacts on success
- On failure: keep temp artefacts *only if* `--retain-temp` is set
- Never place temp outputs into ambiguous system locations by default

**Acceptance criteria:**
- Successful run leaves no temp residue unless retention is explicitly enabled
- Failure mode is deterministic and logged
- Retention is opt-in and recorded in audit

---

### 4.4 Evidence/Config Capture (Additive Only)

Capture runtime and configuration metadata for defensibility.

**Minimum fields (recommended):**
- VoxelMask version string
- Git commit hash (if available; otherwise "unknown")
- Execution mode (Pilot/Research) and applicable profile
- OCR engine and version (if discoverable)
- Configuration snapshot hash (sha256 of normalized config JSON)
- Host environment summary (OS, Python, hostname optional)
- Operator-provided run label (optional, non-PHI)

**Constraints:**
- Must not capture PHI
- Must not capture local file paths that reveal patient identifiers
- Prefer hashes and sanitized summaries

**Acceptance criteria:**
- Audit receipt includes configuration + version capture
- Captured data is stable across reruns with same config
- Additive only (does not modify existing schema fields unexpectedly)

---

### 4.5 Fail-Safe Output Rules

Prevent "looks successful but isn't" outcomes.

**Rules:**
- If processing fails mid-run, output bundle must be marked incomplete
- Receipt must state incomplete status clearly
- Exit code must reflect failure
- Optional: partial outputs go under `incomplete/` or flagged in manifest

**Acceptance criteria:**
- Operators cannot mistake a failed run for a successful run
- Integrity hashes (if used) do not "pass" on incomplete bundles
- Logs clearly record the first failure cause

---

## 5. Testing Approach (Phase 8)

Phase 8 emphasises testable operational logic.

### 5.1 Unit tests (required)
- Preflight gate logic (permission denied, disk low, missing dependency)
- Run ID generation format + uniqueness
- Temp retention behaviour (success vs failure)
- Config snapshot hashing (stable normalization)

### 5.2 Integration tests (allowed, pragmatic)
- End-to-end "happy path" run produces:
  - run directory structure
  - bundle
  - receipt
  - logs
- End-to-end failure produces:
  - incomplete marking
  - correct exit code
  - retained temp only when enabled

**Note:** heavy PACS integration remains out of scope; this phase is local operational discipline.

---

## 6. Governance Notes

- Phase 8 must not blur pilot boundaries.
- Phase 8 must not add claims that imply clinical-grade de-identification.
- Phase 8 improves defensibility by ensuring operators can show:
  - what version ran
  - what config ran
  - what happened (success/failure)
  - where artefacts are

---

## 7. Completion Checklist

Phase 8 is "done" when:

- [ ] Preflight gate exists and blocks unsafe runs
- [ ] Run ID is generated and used everywhere
- [ ] Temp hygiene is deterministic; retention is opt-in and audited
- [ ] Version/config capture is present and PHI-safe
- [ ] Failure modes cannot masquerade as success
- [ ] Tests cover operational logic (unit) and one e2e smoke path
- [ ] Documentation states Phase 8 does not change de-id semantics

---

## 8. Change Control

Any change that might alter de-identification output, operator interpretation, or governance stance must be deferred to a future phase and explicitly re-evaluated.

Phase 8 is operational hardening only.
