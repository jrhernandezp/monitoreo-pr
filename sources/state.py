"""State management for the dashboard — load/save seen articles and source status."""
import json
from pathlib import Path
from typing import Dict

DATA_DIR = Path(__file__).parent.parent / "data"
STATE_FILE = DATA_DIR / "state.json"


def load_state() -> Dict:
    """Load previously seen article links and source status."""
    if STATE_FILE.exists():
        try:
            with open(STATE_FILE, "r") as f:
                return json.load(f)
        except Exception:
            return {"seen": [], "last_run": None, "source_status": {}}
    return {"seen": [], "last_run": None, "source_status": {}}


def save_state(state: Dict):
    """Save current state."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2, ensure_ascii=False)


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
        return (datetime.now() - last).days >= 7
    except Exception:
        return True
