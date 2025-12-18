#!/usr/bin/env bash
# VoxelMask - Unified Test Runner
#
# Ensures tests are run using the project virtual environment and the correct
# version of pytest. Prevents accidentally running tests with the system
# interpreter which may lack imaging dependencies.

set -euo pipefail

# Determine root directory based on script location (handles spaces safely)
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PY="${ROOT_DIR}/.venv/bin/python3"

if [[ ! -x "${PY}" ]]; then
    echo "ERROR: venv python not found at: ${PY}"
    echo "Please ensure the project is set up correctly."
    exit 1
fi

# Auto safe-harbor: if user targets tests_unit anywhere in args
PURE_UNIT=0
for arg in "$@"; do
    if [[ "${arg}" == *"tests_unit"* ]]; then
        PURE_UNIT=1
        break
    fi
done

if [[ "${PURE_UNIT}" -eq 1 ]]; then
    export VOXELMASK_PURE_UNIT=1
fi

echo "--- VoxelMask Test Runner ---"
echo "Root:        ${ROOT_DIR}"
echo "Interpreter: $("${PY}" --version)"
echo "Pytest:      $("${PY}" -m pytest --version | head -n 1)"
echo "PURE_UNIT:   ${VOXELMASK_PURE_UNIT:-0}"
echo "------------------------------"

exec "${PY}" -m pytest "$@"
