"""News API source for municipal news monitoring."""
import os
import json
import urllib.request
import urllib.error
from datetime import datetime, timedelta
from typing import List, Dict
from sources.rss_feeds import MUNICIPIOS_NORESTE, mentions_municipio

NEWS_API_URL = "https://newsapi.org/v2/everything"

# Tracked municipalities for News API (those without dedicated RSS)
NEWSAPI_MUNICIPIOS = [
    "Loíza", "Río Grande", "Ceiba", "Naguabo",
    "Humacao", "Cataño", "Vieques", "Culebra",
    "Canóvanas", "Fajardo", "Luquillo",
]


def fetch_newsapi(api_key: str = None, days_back: int = 7, page_size: int = 50) -> List[Dict]:
    """Fetch news from News API for tracked municipalities."""
    if not api_key:
        api_key = os.environ.get("NEWS_API_KEY", "")
    if not api_key:
        print("  ⚠ NEWS_API_KEY not set. Skipping News API.")
        return []

    all_articles = []
    since = (datetime.now() - timedelta(days=days_back)).strftime("%Y-%m-%d")

    for municipio in NEWSAPI_MUNICIPIOS:
        try:
            query = urllib.parse.quote(f'"{municipio}" Puerto Rico')
            url = f"{NEWS_API_URL}?q={query}&from={since}&sortBy=publishedAt&pageSize={page_size}&apiKey={api_key}&language=es"

            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = json.loads(resp.read().decode())

            if data.get("status") != "ok":
                continue

            for article in data.get("articles", []):
                title = article.get("title", "") or ""
                description = article.get("description", "") or ""
                link = article.get("url", "")
                pub_date = article.get("publishedAt", "")
                source_name = article.get("source", {}).get("name", "News API")

                if pub_date:
                    try:
                        dt = datetime.fromisoformat(pub_date.replace("Z", "+00:00"))
                        date_str = dt.strftime("%Y-%m-%d %H:%M")
                    except Exception:
                        date_str = pub_date[:16] if len(pub_date) >= 16 else datetime.now().strftime("%Y-%m-%d %H:%M")
                else:
                    date_str = datetime.now().strftime("%Y-%m-%d %H:%M")

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
            if e.code == 426:
                print(f"  ⚠ News API upgrade required (426) for '{municipio}'")
            else:
                print(f"  ⚠ News API HTTP error {e.code} for '{municipio}'")
        except Exception as e:
            print(f"  ⚠ News API error for '{municipio}': {e}")

    print(f"     → {len(all_articles)} articles from News API")
    return all_articles
