"""Facebook scraper subprocess wrapper with aggressive timeouts and caching."""
import json
import subprocess
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Dict, List, Tuple

ATLANTIC = timezone(timedelta(hours=-4))

FACEBOOK_SCRAPER = Path.home() / ".hermes" / "scripts" / "facebook_scraper.py"
FACEBOOK_PYTHON = Path.home() / ".hermes" / "tools-venv" / "bin" / "python3"

# Cache file for last successful Facebook scrape
CACHE_DIR = Path(__file__).parent.parent / "data"
CACHE_FILE = CACHE_DIR / "facebook_cache.json"

# Pages to scrape (reduced from 28 to 12 most active)
PAGES_TO_SCRAPE = [
    "San Juan", "Carolina", "Caguas", "Fajardo", "Humacao",
    "Trujillo Alto", "Canóvanas", "Loíza", "Río Grande",
    "Luquillo", "Ceiba", "Naguabo",
]


def load_cache() -> list:
    """Load cached Facebook data from last successful scrape."""
    if CACHE_FILE.exists():
        try:
            with open(CACHE_FILE) as f:
                data = json.load(f)
            # Check cache age — use if less than 2 hours old
            cached_at = data.get("_cached_at", "")
            if cached_at:
                try:
                    from datetime import datetime
                    dt = datetime.fromisoformat(cached_at)
                    age_min = (datetime.now() - dt).total_seconds() / 60
                    if age_min < 120:
                        return data.get("results", [])
                except Exception:
                    pass
        except Exception:
            pass
    return []


def save_cache(results: list):
    """Save Facebook results to cache."""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    data = {
        "_cached_at": datetime.now().isoformat(),
        "results": results,
    }
    with open(CACHE_FILE, "w") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def collect_facebook_posts() -> Tuple[List[Dict], Dict[str, str]]:
    """Run Facebook scraper via subprocess with aggressive timeout.
    
    Returns (facebook_data, source_status).
    Falls back to cache if scraper fails or times out.
    """
    print("  📘 Scraping Facebook...")
    source_status = {}

    if not FACEBOOK_SCRAPER.exists():
        msg = f"Scraper not found: {FACEBOOK_SCRAPER}"
        print(f"    ❌ {msg}")
        source_status["Facebook"] = f"❌ {msg}"
        return [], source_status

    if not FACEBOOK_PYTHON.exists():
        msg = f"Python not found: {FACEBOOK_PYTHON}"
        print(f"    ❌ {msg}")
        source_status["Facebook"] = f"❌ {msg}"
        return [], source_status

    facebook_data = []
    try:
        result = subprocess.run(
            [str(FACEBOOK_PYTHON), str(FACEBOOK_SCRAPER), "--json"],
            capture_output=True,
            text=True,
            timeout=20,  # Aggressive: 20s total for all pages
        )
        if result.returncode == 0 and result.stdout.strip():
            facebook_data = json.loads(result.stdout)
            if not isinstance(facebook_data, list):
                facebook_data = []
            else:
                # Save successful results to cache
                save_cache(facebook_data)

            paginas_con_posts = sum(1 for r in facebook_data if r.get("posts"))
            total_posts = sum(len(r.get("posts", [])) for r in facebook_data)
            print(f"    ✅ {paginas_con_posts} páginas con posts ({total_posts} posts)")
            source_status["Facebook"] = f"✅ {paginas_con_posts}p/{total_posts}posts"
        else:
            error_msg = result.stderr.strip()[:100] if result.stderr else "No output"
            print(f"    ⚠️ Facebook scraper error: {error_msg}")
            raise RuntimeError(error_msg)

    except subprocess.TimeoutExpired:
        print("    ⏱️ Facebook timeout (20s) — usando cache")
        facebook_data = load_cache()
        if facebook_data:
            source_status["Facebook"] = f"⚠️ cache ({len(facebook_data)} páginas)"
        else:
            source_status["Facebook"] = "❌ timeout, sin cache"

    except (json.JSONDecodeError, RuntimeError) as e:
        print(f"    ⚠️ Facebook error: {e} — usando cache")
        facebook_data = load_cache()
        if facebook_data:
            source_status["Facebook"] = f"⚠️ cache ({len(facebook_data)} páginas)"
        else:
            source_status["Facebook"] = f"❌ {str(e)[:60]}"

    except Exception as e:
        print(f"    ❌ Facebook exception: {e}")
        facebook_data = load_cache()
        source_status["Facebook"] = f"❌ {str(e)[:60]}"

    return facebook_data, source_status
