#!/usr/bin/env python3
"""
Dashboard de Observador del Noreste — Noreste de Puerto Rico
Recolecta noticias de múltiples fuentes y genera un HTML autónomo.
"""
import os
import sys
import json
import subprocess
import webbrowser
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict

from sources.rss_feeds import fetch_all as fetch_rss, MUNICIPIOS_NORESTE, CATEGORIAS
from sources.newsapi_source import fetch_newsapi
from sources.scraper import scrape_all

BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"
STATE_FILE = DATA_DIR / "state.json"
OUTPUT_FILE = BASE_DIR / "index.html"

# Facebook scraper paths
FACEBOOK_SCRAPER = Path.home() / ".hermes" / "scripts" / "facebook_scraper.py"
FACEBOOK_PYTHON = Path.home() / ".hermes" / "tools-venv" / "bin" / "python3"


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


def collect_articles() -> tuple:
    """Collect articles from all sources and return with source status."""
    all_articles = []
    source_status = {}

    # 1. RSS + Google News (all sources from rss_feeds.py)
    try:
        rss_articles, rss_statuses = fetch_rss()
        all_articles.extend(rss_articles)
        # Add all per-source status from rss_feeds
        source_status.update(rss_statuses)
    except Exception as e:
        print(f"  ❌ RSS/News error: {e}")
        source_status["RSS - General"] = f"❌ Error: {e}"

    # 2. News API
    try:
        newsapi_articles = fetch_newsapi()
        all_articles.extend(newsapi_articles)
        source_status["News API"] = "✅ OK"
    except Exception as e:
        print(f"  ❌ News API error: {e}")
        source_status["News API"] = f"❌ Error: {e}"

    # 3. Scraping
    try:
        scraped_articles = scrape_all()
        all_articles.extend(scraped_articles)
        source_status["El Nuevo Día (Scraping)"] = "✅ OK"
        source_status["Carolina787 (Scraping)"] = "✅ OK"
    except Exception as e:
        print(f"  ❌ Scraping error: {e}")
        source_status["El Nuevo Día (Scraping)"] = f"❌ Error: {e}"
        source_status["Carolina787 (Scraping)"] = f"❌ Error: {e}"

    # Deduplicate by link
    seen_links = set()
    unique_articles = []
    for a in all_articles:
        if a["enlace"] not in seen_links:
            seen_links.add(a["enlace"])
            unique_articles.append(a)

    return unique_articles, source_status


def collect_facebook_posts() -> tuple:
    """Run Facebook scraper via subprocess and return (facebook_data, source_status)."""
    print("  📘 Scraping Facebook...")
    source_status = {}

    if not FACEBOOK_SCRAPER.exists():
        msg = f"Facebook scraper no encontrado en {FACEBOOK_SCRAPER}"
        print(f"    ❌ {msg}")
        source_status["Facebook (28 páginas)"] = f"❌ Error: {msg}"
        return [], source_status

    if not FACEBOOK_PYTHON.exists():
        msg = f"tools-venv python no encontrado en {FACEBOOK_PYTHON}"
        print(f"    ❌ {msg}")
        source_status["Facebook (28 páginas)"] = f"❌ Error: {msg}"
        return [], source_status

    try:
        result = subprocess.run(
            [str(FACEBOOK_PYTHON), str(FACEBOOK_SCRAPER), "--json"],
            capture_output=True,
            text=True,
            timeout=180,
        )
        if result.returncode != 0:
            error_msg = result.stderr.strip()[:200] or "Unknown error"
            print(f"    ❌ Facebook scraper exited with code {result.returncode}: {error_msg}")
            source_status["Facebook (28 páginas)"] = f"❌ Error: código {result.returncode}"
            return [], source_status

        facebook_data = json.loads(result.stdout)
        if not isinstance(facebook_data, list):
            print(f"    ❌ Facebook scraper returned unexpected format")
            source_status["Facebook (28 páginas)"] = "❌ Error: formato inesperado"
            return [], source_status

        paginas_con_posts = sum(1 for r in facebook_data if r.get("posts"))
        total_posts = sum(len(r.get("posts", [])) for r in facebook_data)
        print(f"    ✅ {paginas_con_posts} páginas con posts ({total_posts} posts totales)")
        source_status["Facebook (28 páginas)"] = f"✅ OK ({paginas_con_posts} páginas, {total_posts} posts)"
        return facebook_data, source_status

    except subprocess.TimeoutExpired:
        print("    ❌ Facebook scraper timed out after 180s")
        source_status["Facebook (28 páginas)"] = "❌ Error: timeout (180s)"
        return [], source_status
    except json.JSONDecodeError as e:
        print(f"    ❌ Facebook scraper: JSON inválido - {e}")
        source_status["Facebook (28 páginas)"] = f"❌ Error: JSON inválido"
        return [], source_status
    except Exception as e:
        print(f"    ❌ Facebook scraper exception: {e}")
        source_status["Facebook (28 páginas)"] = f"❌ Error: {e}"
        return [], source_status


def filter_today_only(articles: List[Dict]) -> List[Dict]:
    """Keep only articles from the last 2 days (yesterday + today)."""
    hoy = datetime.now().strftime("%Y-%m-%d")
    ayer = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
    filtrados = [a for a in articles if a.get("fecha", "").startswith(hoy) or a.get("fecha", "").startswith(ayer)]
    print(f"  🗓️  Filtro últimos 2 días ({ayer} - {hoy}): {len(filtrados)}/{len(articles)} artículos")
    return filtrados


def mark_new_articles(articles: List[Dict], state: Dict) -> List[Dict]:
    """Mark articles as NEW if not seen before."""
    seen = set(state.get("seen", []))
    for a in articles:
        a["es_nueva"] = a["enlace"] not in seen
    return articles


def articles_by_municipio(articles: List[Dict]) -> Dict[str, List[Dict]]:
    """Group articles by municipality."""
    by_muni = {m: [] for m in MUNICIPIOS_NORESTE}
    for a in articles:
        for m in a.get("municipios", []):
            if m in by_muni:
                by_muni[m].append(a)
    return by_muni


def generate_facebook_html(facebook_data: list) -> str:
    """Generate HTML for the Facebook posts section."""
    if not facebook_data:
        return '<div class="facebook-empty">No se encontraron posts de Facebook.</div>'

    cards = []
    for r in facebook_data:
        fuente = r.get("fuente", "Desconocido")
        posts = r.get("posts", [])
        if not posts:
            continue

        posts_html = ""
        for p in posts:
            fecha = p.get("fecha", "")
            texto = p.get("texto", "").strip()
            if not texto:
                continue
            # Truncate long text
            if len(texto) > 250:
                texto = texto[:247] + "..."
            posts_html += f"""
            <div class="fb-post">
                <div class="fb-post-fecha">🕐 {fecha}</div>
                <div class="fb-post-texto">{texto}</div>
            </div>"""

        if posts_html:
            cards.append(f"""
        <div class="fb-card">
            <div class="fb-card-header">📘 {fuente}</div>
            <div class="fb-card-body">
                {posts_html}
            </div>
        </div>""")

    if not cards:
        return '<div class="facebook-empty">No se encontraron posts de Facebook.</div>'

    return f"""
    <div class="fb-grid">
        {''.join(cards)}
    </div>"""


def generate_html(articles: List[Dict], source_status: Dict, state: Dict, facebook_data: list = None) -> str:
    """Generate the complete HTML dashboard."""
    by_muni = articles_by_municipio(articles)
    now = datetime.now().strftime("%Y-%m-%d %I:%M:%S %p")
    total = len(articles)
    nuevas = sum(1 for a in articles if a.get("es_nueva"))
    last_run = state.get("last_run", "Nunca")

    # Build municipality cards HTML
    cards_html = ""
    for m in MUNICIPIOS_NORESTE:
        count = len(by_muni[m])
        active_class = "active" if count > 0 else "inactive"
        cards_html += f"""
        <div class="muni-card {active_class}" onclick="filtrarPor('{m}')">
            <div class="muni-name">{m}</div>
            <div class="muni-count">{count}</div>
        </div>"""

    # Build articles table HTML
    articles_sorted = sorted(articles, key=lambda a: a["fecha"], reverse=True)
    table_rows = ""
    for a in articles_sorted:
        new_badge = '<span class="badge-nuevo">NUEVO</span>' if a.get("es_nueva") else ""
        municipios_str = ", ".join(a["municipios"])
        table_rows += f"""
        <tr class="article-row" data-municipios="{municipios_str}">
            <td><span class="muni-tag">{municipios_str}</span></td>
            <td class="titular-cell">{new_badge} <a href="{a['enlace']}" target="_blank">{a['titular']}</a></td>
            <td>{a['fuente']}</td>
            <td>{a['fecha']}</td>
        </tr>"""

    # Build source status HTML
    facebook_html = generate_facebook_html(facebook_data or [])
    facebook_section = ""
    if facebook_data and any(r.get("posts") for r in facebook_data):
        facebook_section = f"""
<div class="section" id="facebookSection">
    <h2>📘 Facebook — Posts Recientes</h2>
    {facebook_html}
</div>"""
    source_rows = ""
    # Group by category
    grupos = {}
    for name, status in source_status.items():
        cat = CATEGORIAS.get(name, "📡 Otros")
        if cat not in grupos:
            grupos[cat] = []
        ok = "✅" in status
        grupos[cat].append((name, status, ok))

    # Sort categories with most important first
    orden_cat = ["📰 RSS Directo", "📰 Google News", "🏛️ Municipios", "🏛️ Gobierno", "📘 Facebook", "📡 Otros", "News API", "El Nuevo Día (Scraping)", "Carolina787 (Scraping)"]
    for cat in orden_cat:
        if cat not in grupos:
            continue
        items = grupos[cat]
        total = len(items)
        ok_count = sum(1 for _, _, ok in items if ok)
        # Add category header
        source_rows += f"""
        <tr class="source-category">
            <td colspan="2"><strong>{cat}</strong> <span class="source-summary">({ok_count}/{total} OK)</span></td>
        </tr>"""
        for name, status, _ in items:
            status_class = "status-ok" if status == "✅ OK" else "status-error"
            source_rows += f"""
        <tr>
            <td style="padding-left:24px;font-size:12px;">{name}</td>
            <td class="{status_class}">{status}</td>
        </tr>"""

    html = f"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<meta http-equiv="Cache-Control" content="no-cache, no-store, must-revalidate">
<meta http-equiv="Pragma" content="no-cache">
<meta http-equiv="Expires" content="0">
<title>Observador del Noreste - Noreste PR</title>
<link rel="icon" type="image/jpeg" href="logo-observador.jpg">
<style>
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
body {{
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
    background: #f0f2f5;
    color: #333;
    padding: 20px;
}}
.header {{
    background: linear-gradient(135deg, #1a237e, #283593);
    color: white;
    padding: 25px 30px;
    border-radius: 12px;
    margin-bottom: 25px;
}}
.header-top {{
    display: flex;
    align-items: center;
    gap: 15px;
    flex-wrap: wrap;
}}
.header-logo {{
    width: 60px;
    height: 60px;
    border-radius: 12px;
    object-fit: cover;
    flex-shrink: 0;
}}
@media (max-width: 600px) {{
    .header-logo {{
        width: 40px;
        height: 40px;
    }}
}}
.header h1 {{ font-size: 28px; margin-bottom: 5px; }}
.header .sub {{ color: #aab6fe; font-size: 14px; }}
.stats {{
    display: flex;
    gap: 20px;
    margin-top: 15px;
    flex-wrap: wrap;
}}
.stat-box {{
    background: rgba(255,255,255,0.1);
    padding: 10px 20px;
    border-radius: 8px;
    text-align: center;
}}
.stat-box .num {{ font-size: 24px; font-weight: bold; }}
.stat-box .label {{ font-size: 12px; color: #aab6fe; }}
.muni-grid {{
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(130px, 1fr));
    gap: 10px;
    margin-bottom: 25px;
}}
.muni-card {{
    background: white;
    border-radius: 10px;
    padding: 15px 10px;
    text-align: center;
    cursor: pointer;
    transition: all 0.2s;
    border: 2px solid transparent;
    box-shadow: 0 1px 3px rgba(0,0,0,0.1);
}}
.muni-card:hover {{ transform: translateY(-2px); box-shadow: 0 4px 12px rgba(0,0,0,0.15); }}
.muni-card.active {{ border-color: #1a237e; }}
.muni-card.active .muni-count {{
    background: #1a237e;
    color: white;
}}
.muni-card.inactive {{ opacity: 0.5; }}
.muni-name {{ font-size: 13px; font-weight: 600; margin-bottom: 8px; }}
.muni-count {{
    display: inline-block;
    background: #e0e0e0;
    color: #555;
    font-size: 18px;
    font-weight: bold;
    width: 36px;
    height: 36px;
    line-height: 36px;
    border-radius: 50%;
}}
.section {{ margin-bottom: 25px; }}
.section h2 {{ font-size: 18px; color: #1a237e; margin-bottom: 10px; }}
.toolbar {{
    display: flex;
    gap: 10px;
    margin-bottom: 10px;
    flex-wrap: wrap;
}}
.btn {{
    padding: 8px 16px;
    border: none;
    border-radius: 6px;
    cursor: pointer;
    font-size: 13px;
    transition: all 0.2s;
}}
.btn-primary {{ background: #1a237e; color: white; }}
.btn-primary:hover {{ background: #283593; }}
.btn-secondary {{ background: #e0e0e0; color: #333; }}
.btn-secondary:hover {{ background: #bdbdbd; }}
table {{ width: 100%; border-collapse: collapse; background: white; border-radius: 10px; overflow: hidden; }}
th, td {{ padding: 10px 12px; text-align: left; border-bottom: 1px solid #e0e0e0; }}
th {{ background: #f5f5f5; font-size: 12px; text-transform: uppercase; color: #666; }}
tr:hover {{ background: #fafafa; }}
.titular-cell a {{ color: #1a237e; text-decoration: none; font-weight: 500; }}
.titular-cell a:hover {{ text-decoration: underline; }}
.badge-nuevo {{
    display: inline-block;
    background: #e53935;
    color: white;
    font-size: 10px;
    font-weight: bold;
    padding: 2px 6px;
    border-radius: 3px;
    margin-right: 5px;
    vertical-align: middle;
}}
.muni-tag {{
    display: inline-block;
    background: #e8eaf6;
    color: #1a237e;
    font-size: 11px;
    padding: 3px 8px;
    border-radius: 4px;
    font-weight: 500;
}}
.source-table {{ max-width: 500px; }}
.source-category td {{ background: #f5f5f5; border-bottom: 2px solid #e0e0e0; }}
.source-summary {{ font-weight: normal; font-size: 11px; color: #666; }}
.status-ok {{ color: #2e7d32; font-weight: 500; }}
.status-error {{ color: #c62828; font-weight: 500; }}
.footer {{ text-align: center; color: #999; font-size: 12px; margin-top: 30px; }}

/* --- Facebook Section --- */
.fb-grid {{
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(340px, 1fr));
    gap: 15px;
}}
.fb-card {{
    background: white;
    border-radius: 10px;
    box-shadow: 0 1px 3px rgba(0,0,0,0.1);
    overflow: hidden;
    border-left: 4px solid #1877f2;
}}
.fb-card-header {{
    background: linear-gradient(135deg, #1877f2, #166fe5);
    color: white;
    padding: 10px 14px;
    font-size: 14px;
    font-weight: 600;
}}
.fb-card-body {{
    padding: 10px 14px;
}}
.fb-post {{
    padding: 8px 0;
    border-bottom: 1px solid #f0f0f0;
}}
.fb-post:last-child {{
    border-bottom: none;
}}
.fb-post-fecha {{
    font-size: 11px;
    color: #999;
    margin-bottom: 4px;
}}
.fb-post-texto {{
    font-size: 13px;
    color: #333;
    line-height: 1.5;
    display: -webkit-box;
    -webkit-line-clamp: 3;
    -webkit-box-orient: vertical;
    overflow: hidden;
    word-break: break-word;
}}
.facebook-empty {{
    color: #999;
    font-style: italic;
    padding: 20px;
    text-align: center;
    background: white;
    border-radius: 10px;
    box-shadow: 0 1px 3px rgba(0,0,0,0.1);
}}
@media (max-width: 600px) {{
    .muni-grid {{ grid-template-columns: repeat(3, 1fr); }}
    .header h1 {{ font-size: 22px; }}
    .stats {{ gap: 10px; }}
    .stat-box {{ flex: 1; min-width: 80px; }}
}}
</style>
</head>
<body>

<div class="header">
    <div class="header-top">
        <img src="logo-observador.jpg" alt="Observador del Noreste" class="header-logo">
        <h1>🗺️ Observador del Noreste</h1>
    </div>
    <div class="sub">Noreste de Puerto Rico — {now}</div>
    <div class="stats">
        <div class="stat-box"><div class="num">{total}</div><div class="label">Total Noticias</div></div>
        <div class="stat-box"><div class="num" style="color:#ff5252">{nuevas}</div><div class="label">Nuevas</div></div>
        <div class="stat-box"><div class="num">{len(articles)}</div><div class="label">Municipios</div></div>
        <div class="stat-box" style="font-size:11px;"><div class="num" style="font-size:14px;">Último scrape</div><div class="label">{last_run}</div></div>
    </div>
</div>

<div class="section">
    <h2>Municipios del Noreste</h2>
    <div class="muni-grid" id="muniGrid">
        {cards_html}
    </div>
</div>

<div class="section">
    <h2>Noticias Recientes</h2>
    <div class="toolbar">
        <button class="btn btn-primary" onclick="filtrarPor('todos')">📋 Ver Todos</button>
        <span style="font-size:13px;color:#666;line-height:34px;" id="filtroLabel"></span>
    </div>
    <div style="overflow-x:auto;">
        <table>
            <thead><tr><th>Municipio</th><th>Titular</th><th>Fuente</th><th>Fecha</th></tr></thead>
            <tbody id="articlesBody">
                {table_rows}
            </tbody>
        </table>
    </div>
</div>

    {facebook_section}

<div class="section">
    <h2>📡 Estado de Fuentes</h2>
    <table class="source-table">
        <thead><tr><th>Fuente</th><th>Estado</th></tr></thead>
        <tbody>
            {source_rows}
        </tbody>
    </table>
</div>

<div class="footer">
    Generado por Hermes Agent — {now}
</div>

<script>
function filtrarPor(municipio) {{
    const rows = document.querySelectorAll('.article-row');
    const label = document.getElementById('filtroLabel');
    if (municipio === 'todos') {{
        rows.forEach(r => r.style.display = '');
        label.textContent = 'Mostrando todos los municipios';
        return;
    }}
    label.textContent = 'Filtrando: ' + municipio;
    rows.forEach(r => {{
        const municipios = r.getAttribute('data-municipios') || '';
        r.style.display = municipios.includes(municipio) ? '' : 'none';
    }});
}}
// Highlight active card on click
document.querySelectorAll('.muni-card').forEach(card => {{
    card.addEventListener('click', function() {{
        document.querySelectorAll('.muni-card').forEach(c => c.style.borderColor = 'transparent');
        if (!this.classList.contains('inactive')) {{
            this.style.borderColor = '#e53935';
        }}
    }});
}});
</script>
</body>
</html>"""
    return html


def main():
    print("=" * 50)
    print("🗺️  Dashboard de Observador del Noreste")
    print(f"   Noreste de Puerto Rico — {datetime.now().strftime('%Y-%m-%d %I:%M %p')}")
    print("=" * 50)

    hoy = datetime.now().strftime("%Y-%m-%d")
    state = load_state()

    # Reset semanal (cada lunes) en vez de diario
    # para mantener badges NUEVO en artículos de ayer
    session_date = state.get("session_date", "")
    today_weekday = datetime.now().weekday()
    session_weekday = session_date[:10] if session_date else ""
    # Resetear si pasaron 7+ días desde último reset
    if session_date:
        try:
            last_reset = datetime.strptime(session_date[:10], "%Y-%m-%d")
            days_since = (datetime.now() - last_reset).days
            if days_since >= 7:
                print(f"\n📅 Reset semanal ({days_since} días desde último reset).")
                state = {"seen": [], "last_run": None, "source_status": {}, "session_date": hoy}
            else:
                print(f"\n📅 Estado activo ({days_since} días desde reset).")
        except:
            state = {"seen": [], "last_run": None, "source_status": {}, "session_date": hoy}
    else:
        state["session_date"] = hoy

    print("📡 Recolectando noticias...")
    articles, source_status = collect_articles()

    # 4. Facebook (via subprocess to tools-venv)
    facebook_data, fb_status = collect_facebook_posts()
    source_status.update(fb_status)

    # Filtrar Facebook del estado de fuentes visible (monitoreo en segundo plano)
    source_status = {k: v for k, v in source_status.items() if "Facebook" not in k}

    # Filtrar solo noticias de HOY
    articles = filter_today_only(articles)
    articles = mark_new_articles(articles, state)

    print(f"📊 Total: {len(articles)} artículos de hoy")

    # Si no hay artículos, advertir pero no fallar
    if not articles:
        print("  ⚠️  No se encontraron noticias de hoy para los municipios del noreste.")

    # Update state
    state["seen"] = list(set(state.get("seen", []) + [a["enlace"] for a in articles]))
    state["last_run"] = datetime.now().strftime("%Y-%m-%d %I:%M:%S %p")
    state["source_status"] = source_status
    save_state(state)

    # Generate HTML
    html = generate_html(articles, source_status, state, facebook_data)
    OUTPUT_FILE.write_text(html, encoding="utf-8")
    print(f"\n✅ Dashboard generado: {OUTPUT_FILE}")

    # Optionally open in browser
    if "--serve" in sys.argv or "--open" in sys.argv:
        webbrowser.open(f"file://{OUTPUT_FILE.resolve()}")
        print("   Abierto en el navegador.")


if __name__ == "__main__":
    main()
