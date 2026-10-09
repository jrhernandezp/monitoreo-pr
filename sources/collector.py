"""Article collector — orchestrates all sources and deduplicates."""
import os
import re
import unicodedata
from urllib.parse import urlsplit, urlunsplit, parse_qsl, urlencode
from datetime import datetime, timedelta
from typing import Dict, List, Tuple

from sources.rss_feeds import fetch_all as fetch_rss, MUNICIPIOS_NORESTE, CATEGORIAS
from sources.newsapi_source import fetch_newsapi
from sources.scraper import scrape_all
from sources.facebook import collect_facebook_posts
from sources.dates import now_local, parse_article_date


def article_key(article: dict) -> str:
    """Full normalized title and source; preserve compatibility with stored keys."""
    return f'{article.get("titular", "")}|{article.get("fuente", "")}'


def canonical_link(link):
    if not isinstance(link, str):
        return ""
    try:
        parsed = urlsplit(link.strip())
        if parsed.scheme.lower() not in {"http", "https"} or not parsed.netloc:
            return ""
        query = [(k, v) for k, v in parse_qsl(parsed.query, keep_blank_values=True)
                 if not k.lower().startswith("utm_") and k.lower() not in {"fbclid", "gclid"}]
        return urlunsplit((parsed.scheme.lower(), parsed.netloc.lower(), parsed.path, urlencode(query), ""))
    except ValueError:
        return ""


def deduplicate(articles):
    unique, links, titles = [], {}, {}
    for raw in articles:
        article = dict(raw)
        link = canonical_link(article.get("enlace"))
        title = article.get("titular", "").strip()
        if not title or not link:
            continue
        article["enlace"] = link
        article["titular"] = title
        title_key = " ".join(unicodedata.normalize("NFKC", title).casefold().split())
        # Exact normalized headlines only: distinct reports about an event stay separate.
        existing = links.get(link) or titles.get(title_key)
        if existing is not None:
            municipios = list(dict.fromkeys(existing.get("municipios", []) + article.get("municipios", [])))
            # Keep the publisher's direct URL when also found through Google News.
            if urlsplit(existing["enlace"]).hostname == "news.google.com" and urlsplit(link).hostname != "news.google.com":
                existing.update(article)
            existing["municipios"] = municipios
            links[link] = titles[title_key] = existing
            continue
        links[link] = titles[title_key] = article
        unique.append(article)
    return unique


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
        newsapi_articles, newsapi_status = fetch_newsapi(return_status=True)
        all_articles.extend(newsapi_articles)
        source_status["News API"] = newsapi_status
    except Exception as e:
        print(f"  ❌ News API error: {e}")
        source_status["News API"] = f"❌ Error: {e}"

    # 3. Scraping
    try:
        scraped_articles, scrape_status = scrape_all(return_status=True)
        all_articles.extend(scraped_articles)
        source_status.update(scrape_status)
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

    return deduplicate(all_articles), source_status, facebook_data


def filter_recent(articles: List[Dict], days: int = 2) -> List[Dict]:
    """Keep all calendar days in the range, excluding unknown or future dates."""
    if days < 1:
        raise ValueError("days must be positive")
    now = now_local()
    cutoff = now.date() - timedelta(days=days - 1)
    filtered = []
    for article in articles:
        published = parse_article_date(article.get("fecha"))
        if published and cutoff <= published.date() <= now.date() and published <= now:
            filtered.append(article)
    print(f"  🗓️ Últimos {days} días: {len(filtered)}/{len(articles)} artículos")
    return filtered


def mark_new_articles(articles: List[Dict], state: Dict) -> List[Dict]:
    """Mark articles as NEW if not seen before."""
    seen = set(state.get("seen", []))
    for a in articles:
        a["es_nueva"] = article_key(a) not in seen and f'{a.get("titular", "")[:100]}|{a.get("fuente", "")}' not in seen
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


def is_recent_breaking(article: Dict, max_age_hours: int = 4) -> bool:
    """Detect if an article is breaking news and from the last N hours."""
    if not is_breaking(article):
        return False
    
    value = article.get("fecha", "")
    if len(value) <= 10:
        return False
    published = parse_article_date(value)
    if published is None:
        return False
    hours = (now_local() - published).total_seconds() / 3600
    return 0 <= hours <= max_age_hours


def time_ago(date_str: str) -> str:
    """Relative time for known timestamps; keep date-only values unchanged."""
    if not date_str or len(date_str) <= 10:
        return date_str or ""
    published = parse_article_date(date_str)
    if published is None:
        return date_str
    seconds = (now_local() - published).total_seconds()
    if seconds < 0:
        return "Fecha futura"
    minutes = int(seconds / 60)
    if minutes < 1:
        return "ahora mismo"
    if minutes < 60:
        return f"hace {minutes}min"
    if minutes < 1440:
        return f"hace {minutes // 60}h"
    return f"hace {minutes // 1440}d" if minutes < 10080 else date_str[:10]


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
