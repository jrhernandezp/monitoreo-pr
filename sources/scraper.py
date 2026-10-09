"""Web scraper for municipal news from various sources."""
import requests
from bs4 import BeautifulSoup
from datetime import datetime
import re
from sources.dates import parse_article_date
from typing import List, Dict
from sources.rss_feeds import MUNICIPIOS_NORESTE, mentions_municipio

# URLs to scrape (municipal section or search pages)
SCRAPE_TARGETS = {
    "El Nuevo Día": "https://www.elnuevodia.com/",
    "Carolina787": "https://www.carolina787.com/n",
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


def parse_date(text: str) -> str:
    """Parse a date string like 'May 8, 2026' or 'April 29, 2026' to YYYY-MM-DD."""
    months = {
        "january": "01", "february": "02", "march": "03", "april": "04",
        "may": "05", "june": "06", "july": "07", "august": "08",
        "september": "09", "october": "10", "november": "11", "december": "12"
    }
    text = text.strip()
    for eng, num in months.items():
        if eng in text.lower():
            parts = text.replace(",", "").split()
            for p in parts:
                if p.isdigit() and len(p) == 4:
                    day = parts[1].replace(",", "")
                    try:
                        value = f"{p}-{num}-{int(day):02d}"
                    except ValueError:
                        return ""
                    return value if parse_article_date(value) else ""
    parsed = parse_article_date(text)
    return parsed.strftime("%Y-%m-%d") if parsed else ""


def scrape_carolina787(max_articles: int = 30, status: dict = None) -> List[Dict]:
    """Scrape Carolina787.com news page."""
    source_name = "Carolina787 (Scraping)"
    articles = []
    def report(value):
        if status is not None:
            status[source_name] = value
    try:
        resp = requests.get(SCRAPE_TARGETS["Carolina787"], headers=HEADERS, timeout=15)
        if resp.status_code != 200:
            report(f"❌ HTTP {resp.status_code}")
            print(f"  ⚠ Carolina787 returned status {resp.status_code}")
            return []

        soup = BeautifulSoup(resp.text, "html.parser")
        report("✅ OK")
        links_found = set()

        # Find all article items in the Webflow collection list
        for item in soup.select(".w-dyn-item a[href*='/n/']"):
            href = item.get("href", "")
            if not href or href == "/n" or href in links_found:
                continue

            # Find title
            title_el = item.select_one(".news-titles")
            title = title_el.get_text(strip=True) if title_el else ""

            # Find date
            date_el = item.select_one(".fechas")
            date_text = date_el.get_text(strip=True) if date_el else ""
            fecha = parse_date(date_text)

            if title and len(title) > 10:
                links_found.add(href)
                full_url = href if href.startswith("http") else f"https://www.carolina787.com{href}"
                matched = mentions_municipio(title)
                if not matched:
                    matched = ["Carolina"]
                articles.append({
                    "titular": title,
                    "enlace": full_url,
                    "fuente": "Carolina787",
                    "fecha": fecha,
                    "municipios": matched,
                    "tipo": "Scraping",
                })
                if len(articles) >= max_articles:
                    break

    except requests.exceptions.Timeout:
        report("❌ Timeout")
        print("  ⚠ Carolina787 scraping timed out")
    except Exception as e:
        report(f"❌ {type(e).__name__}")
        print(f"  ⚠ Carolina787 scraping error: {e}")

    if status is not None and not articles and status.get(source_name, "").startswith("✅"):
        report("⚠️ Sin noticias reconocibles")
    return articles


def scrape_elnuevodia(max_articles: int = 30, status: dict = None) -> List[Dict]:
    """Scrape El Nuevo Día homepage for trending/local news."""
    source_name = "El Nuevo Día (Scraping)"
    articles = []
    def report(value):
        if status is not None:
            status[source_name] = value
    try:
        resp = requests.get(SCRAPE_TARGETS["El Nuevo Día"], headers=HEADERS, timeout=10)
        if resp.status_code != 200:
            report(f"❌ HTTP {resp.status_code}")
            print(f"  ⚠ END returned status {resp.status_code}")
            return []

        soup = BeautifulSoup(resp.text, "html.parser")
        report("✅ OK")

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
                            "fecha": published_date(a, href),
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
        report("❌ Timeout")
        print("  ⚠ END scraping timed out")
    except Exception as e:
        report(f"❌ {type(e).__name__}")
        print(f"  ⚠ END scraping error: {e}")

    if status is not None and not articles and status.get(source_name, "").startswith("✅"):
        report("⚠️ Sin noticias reconocibles")
    return articles


def published_date(tag, href):
    """Use publication metadata or a date in the URL, never the scrape time."""
    parent = tag.find_parent("article")
    time_tag = parent.find("time") if parent else None
    if time_tag:
        value = time_tag.get("datetime", "")
        dt = parse_article_date(value)
        if dt:
            return dt.strftime("%Y-%m-%d %H:%M")
    match = re.search(r"/(20\d{2})/?(\d{2})/?(\d{2})(?:/|$)", href)
    if match:
        value = "-".join(match.groups())
        return value if parse_article_date(value) else ""
    return ""


def scrape_all(max_total_seconds: int = 60, return_status: bool = False) -> List[Dict]:
    """Each request has a timeout; this also works on Windows and worker threads."""
    articles, statuses = [], {}
    for fetch in (scrape_elnuevodia, scrape_carolina787):
        articles.extend(fetch(status=statuses))
    return (articles, statuses) if return_status else articles
