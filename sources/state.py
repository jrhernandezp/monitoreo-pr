"""State management for the dashboard — load/save seen articles and source status."""
import json
import os
import tempfile
from sources.dates import now_local
from pathlib import Path
from typing import Dict

DATA_DIR = Path(__file__).parent.parent / "data"
STATE_FILE = DATA_DIR / "state.json"


def load_state() -> Dict:
    """Reject malformed state instead of crashing a later collection."""
    empty = {"seen": [], "last_run": None, "source_status": {}}
    try:
        state = json.loads(STATE_FILE.read_text(encoding="utf-8"))
        if not isinstance(state, dict):
            return empty
        if not isinstance(state.get("seen", []), list):
            state["seen"] = []
        state["seen"] = [key for key in state.get("seen", []) if isinstance(key, str)]
        if not isinstance(state.get("source_status", {}), dict):
            state["source_status"] = {}
        return state
    except (OSError, ValueError):
        return empty


def write_text_atomic(path, content):
    """Replace only after a complete write, keeping the last good file on failure."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as output:
            output.write(content)
            output.flush()
            os.fsync(output.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def save_state(state: Dict):
    write_text_atomic(STATE_FILE, json.dumps(state, indent=2, ensure_ascii=False))


def migrate_seen_keys(state: Dict) -> bool:
    """Migrate old URL-based seen keys to stable content keys. Returns True if migrated."""
    seen = state.get("seen", [])
    if seen and seen[0].startswith("http"):
        state["seen"] = []
        return True
    return False


def should_reset_weekly(state: Dict) -> bool:
    """Check if weekly reset is needed (7+ days since last reset)."""
    from datetime import datetime
    session_date = state.get("session_date", "")
    if not session_date:
        return False
    try:
        last = datetime.strptime(session_date[:10], "%Y-%m-%d")
        return (now_local().date() - last.date()).days >= 7
    except Exception:
        return True
