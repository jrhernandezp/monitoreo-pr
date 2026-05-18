"""Web scraper for municipal news from various sources."""
import requests
from bs4 import BeautifulSoup
from datetime import datetime
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
                    return f"{p}-{num}-{int(day):02d}"
    return datetime.now().strftime("%Y-%m-%d")


def scrape_carolina787(max_articles: int = 30) -> List[Dict]:
    """Scrape Carolina787.com news page."""
    articles = []
    try:
        resp = requests.get(SCRAPE_TARGETS["Carolina787"], headers=HEADERS, timeout=15)
        if resp.status_code != 200:
            print(f"  ⚠ Carolina787 returned status {resp.status_code}")
            return []

        soup = BeautifulSoup(resp.text, "html.parser")
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
        print("  ⚠ Carolina787 scraping timed out")
    except Exception as e:
        print(f"  ⚠ Carolina787 scraping error: {e}")

    return articles


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


def scrape_all(max_total_seconds: int = 60) -> List[Dict]:
    """Run all scrapers and return articles. Hard timeout via alarm signal."""
    import signal

    articles = []

    def _timeout_handler(signum, frame):
        raise TimeoutError(f"scrape_all exceeded {max_total_seconds}s")

    old_handler = signal.signal(signal.SIGALRM, _timeout_handler)
    signal.alarm(max_total_seconds)

    try:
        print("  🕸️  Scraping: El Nuevo Día...")
        try:
            end_articles = scrape_elnuevodia()
            print(f"     → {len(end_articles)} articles from END")
            articles.extend(end_articles)
        except Exception as e:
            print(f"     ⚠ END error: {e}")

        print("  🕸️  Scraping: Carolina787...")
        try:
            c787_articles = scrape_carolina787()
            print(f"     → {len(c787_articles)} articles from Carolina787")
            articles.extend(c787_articles)
        except Exception as e:
            print(f"     ⚠ Carolina787 error: {e}")

    except TimeoutError:
        print(f"  ⏰ scrape_all timeout ({max_total_seconds}s) — returning {len(articles)} articles collected so far")
    finally:
        signal.alarm(0)
        signal.signal(signal.SIGALRM, old_handler)

    return articles
