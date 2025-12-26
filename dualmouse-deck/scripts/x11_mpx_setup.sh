#!/usr/bin/env bash
set -euo pipefail

if ! xinput list --name-only | grep -q '^DualA pointer$'; then
  xinput create-master DualA
fi
if ! xinput list --name-only | grep -q '^DualB pointer$'; then
  xinput create-master DualB
fi

LEFT_ID="$(xinput list --id-only 'DualMouse_Left' 2>/dev/null || true)"
RIGHT_ID="$(xinput list --id-only 'DualMouse_Right' 2>/dev/null || true)"

if [[ -z "${LEFT_ID}" || -z "${RIGHT_ID}" ]]; then
  echo "Missing uinput devices. Start daemon with uinput enabled first."
  exit 1
fi

DUALA_PTR="$(xinput list --id-only 'DualA pointer')"
DUALB_PTR="$(xinput list --id-only 'DualB pointer')"

xinput reattach "${LEFT_ID}" "${DUALA_PTR}"
xinput reattach "${RIGHT_ID}" "${DUALB_PTR}"

echo "Attached DualMouse_Left -> DualA, DualMouse_Right -> DualB"
xinput list --short | sed -n '/DualA/,/DualB/p'
