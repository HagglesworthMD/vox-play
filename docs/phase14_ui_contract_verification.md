# Phase 14 — UI Contract Verification

## Not run yet
- Commit hash tested: _TBD_
- Environment (OS / browser): _TBD_
- Pass/fail notes: _TBD_

## Operator-focused verification checklist

| Scenario | Steps | Expected outcome |
| --- | --- | --- |
| Cold start (no upload) | 1. Open the UI from a clean browser session.<br>2. Do not upload any files.<br>3. Inspect default profile/mode selections and disabled states. | Default profile/mode reflects latest freeze. No blocking errors. Actions that require uploads remain disabled. |
| Upload then change profile/mode and revert | 1. Upload a valid sample dataset.<br>2. Switch profile/mode (e.g., FOI → Research → Clinical as available).<br>3. Revert to the original selection before running.<br>4. Confirm retained inputs and warnings. | Mode/profile toggle does not clear uploaded files unexpectedly. Any warnings reflect the active selection. UI state reverts cleanly without stale badges or toasts. |
| Successful run path | 1. Upload dataset.<br>2. Choose intended profile/mode.<br>3. Start processing and wait for completion.<br>4. Review results, resolved settings, and downloads. | Run completes without UI errors. Results view matches chosen profile/mode. Download options render without crashing. |
| Mid-run interruption (refresh/close) then reopen | 1. Start a run.<br>2. While processing, refresh the page or close/reopen the tab.<br>3. Re-establish the session and review state. | System resumes gracefully per pilot-safe constraints. UI shows consistent status (either resumed, retriable, or safely reset) without hanging spinners. |
| Per-profile/mode quick run (FOI/Research/Clinical/etc.) | 1. For each available profile/mode, upload a minimal valid dataset.<br>2. Trigger processing and observe completion.<br>3. Record any profile-specific UI differences. | Each profile/mode runs end-to-end without divergence from documented behavior. UI labels, warnings, and outputs align with the selected profile/mode. |
| Verify “Resolved Settings (Before Run)” matches actual behavior | 1. Before starting a run, open the “Resolved Settings (Before Run)” panel.<br>2. Note effective parameters (e.g., masking, anonymisation, export constraints).<br>3. Execute the run and compare observed behavior and outputs. | Observed behavior matches the resolved settings with no silent overrides. Any discrepancies are captured in notes. |
| Verify downloads (zip + audit) don’t crash when empty/partial | 1. Attempt downloads with no files, with partial results, and after a full run.<br>2. Trigger zip export and audit download paths.<br>3. Monitor UI responsiveness and error handling. | UI stays responsive; empty/partial states do not crash the page. Download affordances communicate status clearly (disabled, error, or success). |

## Evidence capture notes
- Record timestamps, browser console logs (if errors), and screenshots for any anomalies.
- Highlight any deviations from pilot-safe constraints (copy-out only; no PACS write-back).
- File issues immediately for UI regressions that affect operator predictability.
