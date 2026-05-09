"""Web scraper for municipal news from El Nuevo Día."""
import requests
from bs4 import BeautifulSoup
from datetime import datetime
from typing import List, Dict
from sources.rss_feeds import MUNICIPIOS_NORESTE, mentions_municipio

# URLs to scrape (municipal section or search pages)
SCRAPE_TARGETS = {
    "El Nuevo Día": "https://www.elnuevodia.com/",
}

# Municipios to scrape by name (those best covered by END)
SCRAPE_MUNICIPIOS = [
    "San Juan", "Carolina", "Caguas", "Bayamón",
    "Canóvanas", "Fajardo", "Loíza", "Río Grande",
    "Humacao",
]

HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}


def scrape_elnuevodia(max_articles: int = 30) -> List[Dict]:
    """Scrape El Nuevo Día homepage for trending/local news."""
    articles = []
    try:
        resp = requests.get(SCRAPE_TARGETS["El Nuevo Día"], headers=HEADERS, timeout=10)
        if resp.status_code != 200:
            print(f"  ⚠ END returned status {resp.status_code}")
            return []

        soup = BeautifulSoup(resp.text, "html.parser")

        # Try multiple selectors for article links
        links_found = set()
        for selector in [
            "h2 a", "h3 a", "h4 a",
            "article a[href*='/noticias/']",
            "a[href*='/locales/']",
            ".entry-title a",
            ".card a",
        ]:
            for a in soup.select(selector):
                href = a.get("href", "")
                title = a.get_text(strip=True)
                if href and title and len(title) > 15 and href not in links_found:
                    links_found.add(href)
                    matched = mentions_municipio(title)
                    if matched:
                        articles.append({
                            "titular": title,
                            "enlace": href if href.startswith("http") else f"https://www.elnuevodia.com{href}",
                            "fuente": "El Nuevo Día",
                            "fecha": datetime.now().strftime("%Y-%m-%d %H:%M"),
                            "municipios": matched,
                            "tipo": "Scraping",
                        })
                    if len(articles) >= max_articles:
                        break
                if len(articles) >= max_articles:
                    break
            if len(articles) >= max_articles:
                break

    except requests.exceptions.Timeout:
        print("  ⚠ END scraping timed out")
    except Exception as e:
        print(f"  ⚠ END scraping error: {e}")

    return articles


def scrape_all() -> List[Dict]:
    """Run all scrapers and return articles."""
    articles = []
    print("  🕸️  Scraping: El Nuevo Día...")
    end_articles = scrape_elnuevodia()
    print(f"     → {len(end_articles)} articles from END")
    articles.extend(end_articles)
    return articles
