#!/usr/bin/env python3
"""Recopila RSS públicos y prepara el Observador del Noreste para Pages."""
import json
import shutil
from pathlib import Path

from sources.rss_feeds import fetch_all
from sources.collector import (
    article_key, deduplicate, filter_recent, mark_new_articles,
    preserve_failed_sources,
)
from sources.dates import now_local
from sources.renderer import generate_html
from sources.state import (
    load_state, migrate_seen_keys, save_state, should_reset_weekly,
    write_text_atomic,
)

ROOT = Path(__file__).resolve().parent


def recover_public_state(state):
    """Recuperar respaldo publicado cuando Actions haya eliminado la caché."""
    if state.get("last_successful_collection"):
        return state
    try:
        public = json.loads((ROOT / "noticias.json").read_text(encoding="utf-8"))
        if public.get("schema_version") != 1 or not isinstance(public.get("articles"), list):
            return state
        cached = [a for a in public["articles"] if isinstance(a, dict)
                  and all(isinstance(a.get(k), str) for k in ("titular", "enlace", "fecha", "fuente"))]
        state["article_cache"] = cached
        state["seen"] = [article_key(a) for a in cached]
    except (OSError, ValueError, AttributeError):
        pass
    return state


def main():
    state = recover_public_state(load_state())
    migrate_seen_keys(state)
    now = now_local()
    if should_reset_weekly(state):
        state.update(seen=[], session_date=now.date().isoformat())
    state.setdefault("session_date", now.date().isoformat())

    raw, statuses = fetch_all()
    if not any(status == "✅ OK" for status in statuses.values()):
        raise RuntimeError("Todas las fuentes RSS fallaron; se conserva la publicación anterior")
    now = now_local()
    articles = filter_recent(deduplicate(raw), days=2)
    articles = preserve_failed_sources(articles, statuses, state)
    articles = mark_new_articles(articles, state)
    for article in articles:
        if article.get("conservada"):
            article["es_nueva"] = False
    articles.sort(key=lambda a: (a["fecha"], a["titular"]), reverse=True)

    # Acotar el estado a las noticias que siguen dentro de la ventana visible.
    state["seen"] = sorted({article_key(a) for a in articles})
    state["last_run"] = now.strftime("%Y-%m-%d %I:%M:%S %p")
    state["source_status"] = statuses
    state["last_successful_collection"] = now.isoformat()
    html = generate_html(articles, statuses, state, [])
    if "<!doctype html>" not in html.lower() or "</html>" not in html.lower():
        raise RuntimeError("El HTML generado está incompleto")
    public = json.dumps({
        "schema_version": 1,
        "generated_at": now.isoformat(),
        "interval_minutes": 15,
        "source_status": statuses,
        "articles": articles,
    }, ensure_ascii=False, indent=2) + "\n"

    assets = ("logo-observador.jpg", "icon.png", "privacidad.html")
    total = 2 * len(html.encode("utf-8")) + len(public.encode("utf-8"))
    total += sum((ROOT / name).stat().st_size for name in assets)
    if total > 1024 * 1024:
        raise RuntimeError("El sitio supera el presupuesto de 1 MiB; no se publica")

    # Preparar todo antes de sustituir las salidas o guardar los vistos.
    site = ROOT / "_site"
    if site.exists():
        shutil.rmtree(site)
    site.mkdir()
    for name in assets:
        shutil.copyfile(ROOT / name, site / name)
    write_text_atomic(site / "index.html", html)
    write_text_atomic(site / "dashboard.html", html)
    write_text_atomic(site / "noticias.json", public)
    write_text_atomic(site / ".nojekyll", "")
    write_text_atomic(ROOT / "index.html", html)
    write_text_atomic(ROOT / "dashboard.html", html)
    write_text_atomic(ROOT / "noticias.json", public)
    save_state(state)
    print(f"Publicación preparada: {len(articles)} noticias; {now.isoformat()}")


if __name__ == "__main__":
    main()
