"""Article collector — orchestrates all sources and deduplicates."""
import sys
from datetime import datetime, timedelta
from typing import Dict, List, Tuple

from sources.rss_feeds import fetch_all as fetch_rss, MUNICIPIOS_NORESTE, CATEGORIAS
from sources.newsapi_source import fetch_newsapi
from sources.scraper import scrape_all
from sources.facebook import collect_facebook_posts
from sources.state import load_state, save_state, migrate_seen_keys, should_reset_weekly


def article_key(article: dict) -> str:
    """Generate a stable dedup key from title+source (not URL)."""
    return f'{article.get("titular", "")[:100]}|{article.get("fuente", "")}'


def collect_all() -> Tuple[List[Dict], Dict[str, str], List[Dict]]:
    """Collect articles from all sources. Returns (articles, source_status, facebook_data)."""
    all_articles = []
    source_status = {}

    # 1. RSS + Google News
    try:
        rss_articles, rss_statuses = fetch_rss()
        all_articles.extend(rss_articles)
        source_status.update(rss_statuses)
    except Exception as e:
        print(f"  ❌ RSS/News error: {e}")
        source_status["RSS - General"] = f"❌ Error: {e}"

    # 2. News API
    try:
        newsapi_articles = fetch_newsapi()
        all_articles.extend(newsapi_articles)
        source_status["News API"] = "✅ OK" if newsapi_articles else "✅ OK (0 results)"
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

    # 4. Facebook (via subprocess)
    try:
        facebook_data, fb_status = collect_facebook_posts()
        source_status.update(fb_status)
    except Exception as e:
        print(f"  ⚠️ Facebook omitido: {e}")
        source_status["Facebook"] = f"⚠️ Omitido: {str(e)[:80]}"
        facebook_data = []

    # Deduplicate by link
    seen_links = set()
    unique_articles = []
    for a in all_articles:
        if a["enlace"] not in seen_links:
            seen_links.add(a["enlace"])
            unique_articles.append(a)

    return unique_articles, source_status, facebook_data


def filter_recent(articles: List[Dict], days: int = 2) -> List[Dict]:
    """Keep only articles from the last N days."""
    hoy = datetime.now().strftime("%Y-%m-%d")
    ayer = (datetime.now() - timedelta(days=days - 1)).strftime("%Y-%m-%d")
    filtrados = [a for a in articles if a.get("fecha", "").startswith(hoy) or a.get("fecha", "").startswith(ayer)]
    print(f"  🗓️  Filtro últimos {days} días ({ayer} - {hoy}): {len(filtrados)}/{len(articles)} artículos")
    return filtrados


def mark_new_articles(articles: List[Dict], state: Dict) -> List[Dict]:
    """Mark articles as NEW if not seen before."""
    seen = set(state.get("seen", []))
    for a in articles:
        a["es_nueva"] = article_key(a) not in seen
    return articles


def articles_by_municipio(articles: List[Dict]) -> Dict[str, List[Dict]]:
    """Group articles by municipality."""
    from sources.rss_feeds import MUNICIPIOS_NORESTE
    by_muni = {m: [] for m in MUNICIPIOS_NORESTE}
    for a in articles:
        for m in a.get("municipios", []):
            if m in by_muni:
                by_muni[m].append(a)
    return by_muni


def is_breaking(article: Dict) -> bool:
    """Detect if an article is breaking news (urgent/important)."""
    text = f"{article.get('titular', '')} {article.get('municipios', [])}".lower()
    breaking_keywords = [
        "asesinato", "homicidio", "tiroteo", "balacera", "secuestro",
        "emergencia", "huracán", "tormenta", "inundación", "terremoto",
        "corte de agua", "sin agua", "apagón", "explosión", "colapso",
        "muerto", "muerte", "fallecido", "cadáver", "cuerpo hallado",
        "desaparecido", "rescate", "evacuación", "incendio",
    ]
    return any(kw in text for kw in breaking_keywords)


def time_ago(date_str: str) -> str:
    """Convert a date string to a human-readable 'time ago' string."""
    if not date_str:
        return ""
    for fmt in ["%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"]:
        try:
            dt = datetime.strptime(date_str, fmt)
            now = datetime.now()
            diff = now - dt
            if diff.total_seconds() < 0:
                return "ahora"
            minutes = int(diff.total_seconds() / 60)
            if minutes < 1:
                return "ahora mismo"
            if minutes < 60:
                return f"hace {minutes}min"
            hours = minutes // 60
            if hours < 24:
                return f"hace {hours}h"
            days = hours // 24
            if days < 7:
                return f"hace {days}d"
            return date_str[:10]
        except ValueError:
            continue
    return date_str


def format_date_12h(date_str: str) -> str:
    """Convert date string from 24h to 12h format."""
    if not date_str or " " not in date_str:
        return date_str
    for fmt_in, fmt_out in [
        ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %I:%M:%S %p"),
        ("%Y-%m-%d %H:%M", "%Y-%m-%d %I:%M %p"),
    ]:
        try:
            return datetime.strptime(date_str, fmt_in).strftime(fmt_out)
        except ValueError:
            continue
    return date_str
