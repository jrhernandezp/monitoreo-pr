#!/bin/bash
# Reset seen markers without replacing the last good news page with an empty page.
set -euo pipefail
DASH_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
cd "$DASH_DIR"
if [[ -f .venv/bin/activate ]]; then
    source .venv/bin/activate
fi
python3 - <<'PYTHON'
from sources.state import load_state, save_state
from sources.dates import now_local
state = load_state()
state["seen"] = []
state["session_date"] = now_local().strftime("%Y-%m-%d")
save_state(state)
print("Marcadores reiniciados; se conserva la última página de noticias.")
PYTHON
