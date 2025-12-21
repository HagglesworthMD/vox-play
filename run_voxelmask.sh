#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
echo "Starting VoxelMask from: $(pwd)"
source venv/bin/activate
exec streamlit run src/app.py --server.port 8501 --server.address 0.0.0.0
