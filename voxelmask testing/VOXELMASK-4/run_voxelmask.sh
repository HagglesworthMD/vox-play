#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

echo "=== VoxelMask launcher ==="
echo "Repo: $SCRIPT_DIR"
echo "Python: $(python -V 2>&1)"
echo "=========================="

if [ -f ".venv/bin/activate" ]; then
  source ".venv/bin/activate"
else
  echo "Virtual environment not found at $SCRIPT_DIR/.venv" >&2
  exit 1
fi

if ! python - <<'PY'
import importlib
import sys
try:
    importlib.import_module("streamlit")
except ImportError:
    sys.exit(1)
PY
then
  pip install -r requirements.txt
fi

streamlit run src/app.py --server.address 127.0.0.1 --server.port 8501 --server.headless true
