#!/usr/bin/env python3
"""
Dashboard de Observador del Noreste — Noreste de Puerto Rico
Recolecta noticias de múltiples fuentes y genera un HTML autónomo.

Uso: /usr/bin/python3 dashboard.py
"""
import sys
import webbrowser
from datetime import datetime
from dotenv import load_dotenv
from sources.dates import now_local
from pathlib import Path

from sources.collector import (
    collect_all,
    filter_recent,
    mark_new_articles,
    article_key,
)
from sources.state import load_state, save_state, migrate_seen_keys, should_reset_weekly, write_text_atomic
from sources.renderer import generate_html

OUTPUT_FILE = Path(__file__).parent / "index.html"


def main():
    load_dotenv(Path(__file__).parent / ".env", override=False)
    print("=" * 50)
    print("🗺️  Dashboard de Observador del Noreste")
    print(f"   Noreste de Puerto Rico — {now_local().strftime('%Y-%m-%d %I:%M %p')}")
    print("=" * 50)

    hoy = now_local().strftime("%Y-%m-%d")
    state = load_state()

    # Migrate old URL-based seen keys
    if migrate_seen_keys(state):
        print("  🔄 Migrando state.json: URLs → claves estables")

    # Weekly reset check
    if should_reset_weekly(state):
        days = "?"
        try:
            from datetime import datetime as dt
            last = dt.strptime(state.get("session_date", "")[:10], "%Y-%m-%d")
            days = (now_local().replace(tzinfo=None) - last).days
        except Exception:
            pass
        print(f"  📅 Reset semanal ({days} días).")
        state = {"seen": [], "last_run": None, "source_status": {}, "session_date": hoy}
    else:
        try:
            from datetime import datetime as dt
            last = dt.strptime(state.get("session_date", "")[:10], "%Y-%m-%d")
            print(f"  📅 Estado activo ({(now_local().replace(tzinfo=None) - last).days} días).")
        except Exception:
            pass

    state.setdefault("session_date", hoy)

    # Collect
    print("📡 Recolectando noticias...")
    articles, source_status, facebook_data = collect_all()

    # Filter recent (last 2 days)
    articles = filter_recent(articles, days=2)
    articles = mark_new_articles(articles, state)

    print(f"📊 Total: {len(articles)} artículos")
    if not articles:
        print("  ⚠️  No se encontraron noticias de hoy.")

    # Update state
    state["seen"] = list(set(state.get("seen", []) + [article_key(a) for a in articles]))
    state["last_run"] = now_local().strftime("%Y-%m-%d %I:%M:%S %p")
    state["source_status"] = source_status

    # Generate HTML before committing seen state; failed rendering must not mark articles seen.
    html = generate_html(articles, source_status, state, facebook_data)
    if not any("✅" in status for status in source_status.values()):
        raise RuntimeError("Todas las fuentes fallaron; se conserva el dashboard anterior")
    write_text_atomic(OUTPUT_FILE, html)
    save_state(state)
    print(f"\n✅ Dashboard generado: {OUTPUT_FILE} ({len(html):,} bytes)")

    if "--serve" in sys.argv or "--open" in sys.argv:
        webbrowser.open(f"file://{OUTPUT_FILE.resolve()}")
        print("   Abierto en el navegador.")


if __name__ == "__main__":
    main()
