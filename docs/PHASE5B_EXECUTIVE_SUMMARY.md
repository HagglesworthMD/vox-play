# VoxelMask — Phase 5b (Masking Correctness)

## Executive Summary

**Phase 5b defines what "correct masking" means — without enabling masking yet.**

This phase deliberately focuses on **governance, auditability, and trust prerequisites**, not feature delivery.

---

## What Phase 5b Achieves

* Defines **when masking would be allowed** and when it must not occur
* Establishes **mandatory human review** before any pixel mutation
* Separates **detection confidence** from **masking eligibility**
* Treats **series order and cine integrity** as trust prerequisites
* Specifies **audit requirements** before masking is even considered

No code was written.  
No pixels were modified.

---

## What Phase 5b Explicitly Does *Not* Do

* Does **not** enable masking
* Does **not** claim complete PHI removal
* Does **not** support clinical use
* Does **not** introduce PACS write-back or routing
* Does **not** reduce human oversight

---

## Why This Matters (Governance View)

* Prevents premature pixel mutation
* Avoids audit gaps
* Reduces FOI and research risk
* Creates a defensible gate before any irreversible action
* Makes later phases reviewable and stoppable

This phase exists to ensure that **if masking ever happens, it happens safely, traceably, and defensibly**.

---

## Current Project State

| Phase                         | Status                     |
| ----------------------------- | -------------------------- |
| Phase 4 — Detection           | Complete                   |
| Phase 5a — Review Semantics   | Complete                   |
| **Phase 5b — Masking Design** | **Complete (Design Only)** |
| Masking Implementation        | **Not Approved**           |

---

## Bottom Line

Phase 5b locks in **discipline before action**.

It ensures that any future masking work:

* Can be audited
* Can be explained
* Can be stopped if governance concerns arise

This significantly lowers organisational and reputational risk.
