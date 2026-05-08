#!/usr/bin/env python3
"""
Dashboard de Monitoreo Municipal — Noreste de Puerto Rico
Recolecta noticias de múltiples fuentes y genera un HTML autónomo.
"""
import os
import sys
import json
import webbrowser
from datetime import datetime
from pathlib import Path
from typing import List, Dict

from sources.rss_feeds import fetch_all as fetch_rss, MUNICIPIOS_NORESTE
from sources.newsapi_source import fetch_newsapi
from sources.scraper import scrape_all

BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"
STATE_FILE = DATA_DIR / "state.json"
OUTPUT_FILE = BASE_DIR / "index.html"


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

    # 1. RSS
    try:
        rss_articles = fetch_rss()
        all_articles.extend(rss_articles)
        source_status["RSS - Primera Hora"] = "✅ OK"
        source_status["RSS - Vocero"] = "✅ OK"
    except Exception as e:
        print(f"  ❌ RSS error: {e}")
        source_status["RSS - Primera Hora"] = f"❌ Error: {e}"
        source_status["RSS - Vocero"] = f"❌ Error: {e}"

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
    except Exception as e:
        print(f"  ❌ Scraping error: {e}")
        source_status["El Nuevo Día (Scraping)"] = f"❌ Error: {e}"

    # Deduplicate by link
    seen_links = set()
    unique_articles = []
    for a in all_articles:
        if a["enlace"] not in seen_links:
            seen_links.add(a["enlace"])
            unique_articles.append(a)

    return unique_articles, source_status


def filter_today_only(articles: List[Dict]) -> List[Dict]:
    """Keep only articles from today's date."""
    hoy = datetime.now().strftime("%Y-%m-%d")
    filtrados = [a for a in articles if a.get("fecha", "").startswith(hoy)]
    print(f"  🗓️  Filtro del día: {len(filtrados)}/{len(articles)} artículos de hoy ({hoy})")
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


def generate_html(articles: List[Dict], source_status: Dict, state: Dict) -> str:
    """Generate the complete HTML dashboard."""
    by_muni = articles_by_municipio(articles)
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
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
    source_rows = ""
    for name, status in source_status.items():
        status_class = "status-ok" if status == "✅ OK" else "status-error"
        source_rows += f"""
        <tr>
            <td>{name}</td>
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
<title>Monitoreo Municipal - Noreste PR</title>
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
.status-ok {{ color: #2e7d32; font-weight: 500; }}
.status-error {{ color: #c62828; font-weight: 500; }}
.footer {{ text-align: center; color: #999; font-size: 12px; margin-top: 30px; }}
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
    <h1>🗺️ Monitoreo Municipal</h1>
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
    print("🗺️  Dashboard de Monitoreo Municipal")
    print(f"   Noreste de Puerto Rico — {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("=" * 50)

    hoy = datetime.now().strftime("%Y-%m-%d")
    state = load_state()

    # Si el día cambió, resetear estado completamente (noticias frescas cada día)
    session_date = state.get("session_date", "")
    if session_date != hoy:
        print(f"\n📅 Nuevo día ({hoy}). Resetando estado — solo noticias frescas.")
        state = {"seen": [], "last_run": None, "source_status": {}, "session_date": hoy}
    else:
        print(f"\n📅 Mismo día ({hoy}). Manteniendo estado para detectar novedades.")

    print("\n📡 Recolectando noticias...")
    articles, source_status = collect_articles()

    # Filtrar solo noticias de HOY
    articles = filter_today_only(articles)
    articles = mark_new_articles(articles, state)

    print(f"📊 Total: {len(articles)} artículos de hoy")

    # Si no hay artículos, advertir pero no fallar
    if not articles:
        print("  ⚠️  No se encontraron noticias de hoy para los municipios del noreste.")

    # Update state
    state["seen"] = list(set(state.get("seen", []) + [a["enlace"] for a in articles]))
    state["last_run"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    state["source_status"] = source_status
    save_state(state)

    # Generate HTML
    html = generate_html(articles, source_status, state)
    OUTPUT_FILE.write_text(html, encoding="utf-8")
    print(f"\n✅ Dashboard generado: {OUTPUT_FILE}")

    # Optionally open in browser
    if "--serve" in sys.argv or "--open" in sys.argv:
        webbrowser.open(f"file://{OUTPUT_FILE.resolve()}")
        print("   Abierto en el navegador.")


if __name__ == "__main__":
    main()
