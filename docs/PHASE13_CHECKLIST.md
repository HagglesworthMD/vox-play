# Phase 13 — Daily Usability Stabilisation (Checklist)

**Goal:**
Make VoxelMask feel reliable and calm for everyday internal use **without changing behaviour, compliance, or meaning**.

**Exit criterion:**
A curious PACS engineer can use it all day without confusion, crashes, or surprises.

---

## 1️⃣ Viewer Reliability (Highest Priority)

**Scope:** file paths, lifecycle, messaging — *not viewer features*

- [x] Viewer opens reliably after processing (localhost HTTP server)
- [x] Viewer path does **not** reference ephemeral `/run/user/*` locations
- [x] Viewer ZIP + in-app viewer use the **same stable source** (`run_paths.viewer_dir`)
- [ ] If viewer is missing → clear message, not browser error
- [ ] Viewer failure does **not** invalidate processing result

**Hard rule:**
No new viewer buttons, modes, or export types.

---

## 2️⃣ Error Path Calmness

**Scope:** user-facing failures only

- [ ] Missing input folder → friendly explanation
- [ ] No files selected → guidance message
- [ ] Invalid combinations → disabled button + reason
- [ ] No stack traces in UI
- [ ] Errors never look like "something broke internally"

**Hard rule:**
Errors explain *what the user can do next*, not what went wrong technically.

---

## 3️⃣ UI Language Consistency

**Scope:** text only

- [ ] Button labels match receipts and docs
- [ ] Profile names identical everywhere
- [ ] No ambiguous terms ("maybe", "smart", "AI")
- [ ] Help text matches actual behaviour
- [ ] No legacy or duplicate terminology

**Hard rule:**
Words may change; meaning may not.

---

## 4️⃣ State Predictability

**Scope:** session behaviour only

- [x] Changing profile updates visible settings immediately
- [x] No "sticky" state from previous runs (`reset_run_state`)
- [x] Rerunning does not reuse stale data (run_id scoping)
- [ ] Reset / new session behaves cleanly
- [ ] UI always reflects **resolved settings**

**Hard rule:**
User should never wonder "what is it actually going to do?"

---

## 5️⃣ Visual Calm (Optional but Valuable)

**Scope:** ordering, spacing, emphasis

- [ ] Primary action is visually obvious
- [ ] Secondary actions de-emphasised
- [ ] No clutter above the process button
- [ ] Collapsible sections used appropriately
- [ ] Screen reads top → bottom logically

**Hard rule:**
No new controls introduced.

---

## Explicitly Out of Scope (Do Not Touch)

❌ New profiles
❌ New anonymisation logic
❌ OCR changes
❌ Metadata rules
❌ Receipt semantics
❌ Compliance wording
❌ Performance optimisation
❌ Refactors "while you're here"

If you feel tempted → you've left Phase 13.

---

## How to Work Phase 13

- Fix **one irritation at a time**
- Run full test suite after each fix
- If a Phase 12 test fails → undo and reassess
- Commit small, descriptive commits
- Stop when the checklist is green

Phase 13 ends **when nothing feels sharp anymore**, not when it's perfect.
