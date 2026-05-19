"""HTML renderer — generates the dashboard from collected data using Jinja2 templates."""
from datetime import datetime
from pathlib import Path
from typing import Dict, List

from jinja2 import Template

from sources.collector import (
    articles_by_municipio,
    is_breaking,
    is_recent_breaking,
    time_ago,
    format_date_12h,
)
from sources.rss_feeds import MUNICIPIOS_NORESTE, CATEGORIAS

TEMPLATE_FILE = Path(__file__).parent.parent / "templates" / "dashboard.html"


def _group_by_time(articles: List[Dict]) -> List[Dict]:
    """Group articles into time buckets for display."""
    from datetime import datetime, timedelta

    now = datetime.now()
    hoy = now.strftime("%Y-%m-%d")
    ayer = (now - timedelta(days=1)).strftime("%Y-%m-%d")

    # Split into time buckets
    ultima_hora = []
    esta_manana = []
    ayer_group = []
    otros = []

    for a in articles:
        fecha = a.get("fecha", "")
        if not fecha:
            otros.append(a)
            continue

        try:
            dt = datetime.strptime(fecha[:16], "%Y-%m-%d %H:%M")
            diff_h = (now - dt).total_seconds() / 3600

            if fecha.startswith(hoy) and diff_h < 1:
                ultima_hora.append(a)
            elif fecha.startswith(hoy):
                esta_manana.append(a)
            elif fecha.startswith(ayer):
                ayer_group.append(a)
            else:
                otros.append(a)
        except ValueError:
            otros.append(a)

    groups = []
    if ultima_hora:
        groups.append({"label": "⚡ Última hora", "articles": ultima_hora})
    if esta_manana:
        groups.append({"label": "🌅 Hoy", "articles": esta_manana})
    if ayer_group:
        groups.append({"label": "📅 Ayer", "articles": ayer_group})
    if otros:
        groups.append({"label": "📋 Anteriores", "articles": otros})

    return groups


def _build_source_badges(source_status: Dict[str, str]) -> List[Dict]:
    """Build compact source status badges."""
    badges = []
    for name, status in source_status.items():
        if "✅" in status:
            cls = "ok"
            icon = "🟢"
            text = "OK"
        elif "⚠️" in status or "cache" in status.lower():
            cls = "warn"
            icon = "🟡"
            text = status.split("⚠️ ")[-1] if "⚠️ " in status else status[:30]
        else:
            cls = "err"
            icon = "🔴"
            text = "Error"
        badges.append({"name": name, "class": cls, "icon": icon, "text": text})
    return badges


def _build_facebook_html(facebook_data: list) -> str:
    """Generate HTML for the Facebook posts section."""
    if not facebook_data:
        return ""

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
            if len(texto) > 200:
                texto = texto[:197] + "..."
            posts_html += f"""
            <div class="fb-post">
                <div class="fb-post-fecha">🕐 {fecha}</div>
                <div class="fb-post-texto">{texto}</div>
            </div>"""

        if posts_html:
            cards.append(f"""
        <div class="fb-card">
            <div class="fb-card-header">📘 {fuente}</div>
            <div class="fb-card-body">{posts_html}</div>
        </div>""")

    if not cards:
        return ""

    return f'<div class="fb-grid">{"".join(cards)}</div>'


def generate_html(
    articles: List[Dict],
    source_status: Dict[str, str],
    state: Dict,
    facebook_data: list = None,
) -> str:
    """Generate the complete HTML dashboard using Jinja2 template."""
    by_muni = articles_by_municipio(articles)
    now = datetime.now().strftime("%Y-%m-%d %I:%M:%S %p")
    total = len(articles)
    nuevas = sum(1 for a in articles if a.get("es_nueva"))
    last_run = state.get("last_run", "Nunca")
    municipios_activos = sum(1 for v in by_muni.values() if v)

    # Municipality list with counts
    municipios_list = []
    for m in MUNICIPIOS_NORESTE:
        municipios_list.append({"name": m, "count": len(by_muni.get(m, []))})

    # Time groups
    articles_sorted = sorted(articles, key=lambda a: a.get("fecha", ""), reverse=True)
    # Add time_ago to each article
    for a in articles_sorted:
        a["time_ago"] = time_ago(a.get("fecha", ""))
    time_groups = _group_by_time(articles_sorted)

    # Breaking news (only from last 4 hours)
    breaking = [a for a in articles_sorted if is_recent_breaking(a, max_age_hours=4)]
    breaking_list = []
    for b in breaking[:5]:  # Max 5 breaking
        breaking_list.append({
            "titular": b["titular"],
            "enlace": b["enlace"],
            "municipios": b.get("municipios", []),
            "time_ago": b.get("time_ago", ""),
        })

    # Source badges
    source_badges = _build_source_badges(source_status)
    sources_ok = sum(1 for s in source_status.values() if "✅" in s)
    sources_total = len(source_status)

    # Facebook
    facebook_html = _build_facebook_html(facebook_data or [])

    # Render template
    template_content = TEMPLATE_FILE.read_text(encoding="utf-8")
    template = Template(template_content)
    html = template.render(
        now=now,
        total=total,
        nuevas=nuevas,
        municipios_activos=municipios_activos,
        last_run=last_run,
        municipios_list=municipios_list,
        time_groups=time_groups,
        breaking=breaking_list,
        facebook_html=facebook_html,
        source_badges=source_badges,
        sources_ok=sources_ok,
        sources_total=sources_total,
    )

    return html
