# Phase 12 — UI Freeze (Daily Usability Hardening)

Status: **Frozen (Phase 12)**
Scope: UI behavior + operator workflow stabilization for pilot-safe, non-clinical copy-out use.

This document defines the Phase 12 UI contract: what exists, what is intentionally absent, and how the operator should recover from common issues.

---

## Objectives

- Ensure the UI behaves predictably across sessions and reruns.
- Keep export and review artefacts run-scoped and audit-defensible.
- Prevent unstable "temp path" behavior (e.g. document portal / transient mounts).
- Preserve governance controls: **two-flag PHI visibility model** and FOI signalling.

Non-goals:
- New features
- Clinical routing or write-back to PACS
- Claims of perfect PHI removal

---

## Operator Actions (UI Contract)

Phase 12 exposes only the following viewer/export actions:

### 1) Open Viewer (Run Folder)
- Opens the HTML export viewer from the canonical run folder location:
  - `downloads/voxelmask_runs/<RUN_ID>/viewer/viewer.html`
- Uses a **localhost HTTP server** (`http://127.0.0.1:<PORT>/viewer/viewer.html`) to avoid Flatpak/portal `file://` sandbox failures on Linux/Steam Deck.
- The server binds **localhost only** (not network-accessible).

### 2) Download Export ZIP
- Downloads the run-scoped export bundle (including viewer + index + images).
- ZIP is transport packaging; it does not change run outputs.

No other "open from ZIP", "open extracted ZIP", or transient viewer paths are exposed.

---

## Canonical Run Layout

Each run produces a stable, deterministic structure under:

`downloads/voxelmask_runs/<RUN_ID>/`

Relevant viewer paths:

- `viewer/viewer.html`
- `viewer/viewer.css`
- `viewer/viewer.js`
- `viewer/viewer_index.js`

Viewer assets are copied into the run folder at export time.

---

## Viewer Stability Guarantees

### Localhost HTTP viewer
Rationale:
- On Linux with Flatpak browsers, `file://` often becomes:
  - `/run/user/<uid>/doc/<token>/...`
- This breaks relative JS/CSS loads and causes "stuck loader".

Phase 12 behavior:
- Viewer is opened via localhost HTTP (not `file://`).
- Viewer remains usable after reruns, restarts, and days later, as long as the run folder remains present.

### Asset versioning
Viewer assets include cache-busting version strings:
- `viewer.css?v=<RUN_ID>`
- `viewer.js?v=<RUN_ID>`
- `viewer_index.js?v=<RUN_ID>`

This prevents stale browser caching across runs.

---

## Governance & Audit Signalling

Phase 12 enforces a two-flag visibility model in receipts:

- Patient identifiers: **REDACTED / VISIBLE**
- Staff identifiers: **REDACTED / VISIBLE**
- Patient tags in OUTPUT DICOM: **PRESERVED / ANONYMISED / CORRECTED / PROCESSED**
- Pixel masking applied: **YES/NO** (explicit)

FOI mode additionally includes:
- A prominent FOI header ("screaming header") in audit receipts
- Explicit visibility disclosure text

Staff identifiers (operator/sonographer) are redacted by default unless the profile explicitly allows them (e.g. internal repair workflows).

---

## Recovery Procedures (Operator)

### Viewer does not open / opens blank
1. Confirm the run folder exists:
   - `downloads/voxelmask_runs/<RUN_ID>/viewer/viewer.html`
2. Use the in-app **Open Viewer (Run Folder)** button.
3. If the viewer tab was opened earlier, refresh it after reopening from the UI.

### Viewer assets look "old" after an update
- In Phase 12, asset versioning is run-scoped.
- Generate a new run to pick up updated viewer assets.

### Localhost server issues (rare)
Symptoms:
- Browser fails to load `http://127.0.0.1:<PORT>/...`

Recovery:
1. Close viewer tab.
2. Click **Open Viewer (Run Folder)** again.
3. If still failing, restart the Streamlit app.

---

## Freeze Rules (Phase 12)

Allowed changes:
- Bug fixes that do not change the operator contract
- UI labeling/clarity improvements
- Stability hardening that does not add new modes or behavior branches
- Documentation and test corrections consistent with the governance model

Disallowed changes:
- Adding new operator actions/buttons
- Altering governance defaults or weakening audit defensibility
- Introducing clinical routing, write-back, or non-copy-out behavior

---

## Exit Criteria (to leave Phase 12)

- Viewer opens reliably on target platform(s) via localhost HTTP.
- Run artefacts are stable and inspectable days later.
- Test suite green on main.
- UI contract documented (this file).
