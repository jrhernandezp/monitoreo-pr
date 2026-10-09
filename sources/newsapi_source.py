"""News API source for municipal news monitoring."""
import os
import json
import urllib.request
import urllib.parse
import urllib.error
from datetime import datetime, timedelta
from typing import List, Dict
from sources.rss_feeds import MUNICIPIOS_NORESTE, mentions_municipio
from sources.dates import now_local, parse_article_date

NEWS_API_URL = "https://newsapi.org/v2/everything"

# Tracked municipalities for News API (those without dedicated RSS)
NEWSAPI_MUNICIPIOS = [
    "Loíza", "Río Grande", "Ceiba", "Naguabo",
    "Humacao", "Cataño", "Vieques", "Culebra",
    "Canóvanas", "Fajardo", "Luquillo",
]


def fetch_newsapi(api_key: str = None, days_back: int = 7, page_size: int = 50, return_status: bool = False) -> List[Dict]:
    """Fetch news from News API for tracked municipalities."""
    if not api_key:
        api_key = os.environ.get("NEWS_API_KEY", "")
    if not api_key:
        print("  ⚠ NEWS_API_KEY not set. Skipping News API.")
        return ([], "⚠️ Sin API key") if return_status else []

    all_articles = []
    errors = []
    since = (now_local() - timedelta(days=days_back)).strftime("%Y-%m-%d")

    for municipio in NEWSAPI_MUNICIPIOS:
        try:
            query = urllib.parse.quote(f'"{municipio}" Puerto Rico')
            url = f"{NEWS_API_URL}?q={query}&from={since}&sortBy=publishedAt&pageSize={page_size}&language=es"

            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0", "X-Api-Key": api_key})
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = json.loads(resp.read().decode())

            if data.get("status") != "ok":
                errors.append(str(data.get("code", "API error")))
                continue

            for article in data.get("articles", []):
                title = article.get("title", "") or ""
                description = article.get("description", "") or ""
                link = article.get("url", "")
                pub_date = article.get("publishedAt", "")
                source_name = (article.get("source") or {}).get("name") or "News API"

                dt = parse_article_date(pub_date)
                if not dt or not title.strip() or not link:
                    continue
                date_str = dt.strftime("%Y-%m-%d %H:%M")

                combined = f"{title} {description}"
                matched = mentions_municipio(combined)
                if matched:
                    all_articles.append({
                        "titular": title.strip(),
                        "enlace": link,
                        "fuente": source_name,
                        "fecha": date_str,
                        "municipios": matched,
                        "tipo": "NewsAPI",
                    })
        except urllib.error.HTTPError as e:
            errors.append(f"HTTP {e.code}")
            if e.code == 426:
                print(f"  ⚠ News API upgrade required (426) for '{municipio}'")
            else:
                print(f"  ⚠ News API HTTP error {e.code} for '{municipio}'")
        except Exception as e:
            errors.append(type(e).__name__)
            print(f"  ⚠ News API error for '{municipio}': {e}")

    print(f"     → {len(all_articles)} articles from News API")
    status = "⚠️ " + ", ".join(sorted(set(errors))) if errors else "✅ OK"
    return (all_articles, status) if return_status else all_articles
