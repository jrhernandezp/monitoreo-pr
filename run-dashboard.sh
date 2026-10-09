#!/bin/bash
set -euo pipefail
DASH_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
cd "$DASH_DIR"
if [[ -f .venv/bin/activate ]]; then
    source .venv/bin/activate
fi
python3 dashboard.py --open
