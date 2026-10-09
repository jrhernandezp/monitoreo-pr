"""RSS feed sources for municipal news monitoring."""
import feedparser
import urllib.request
from urllib.parse import urlsplit
import io
import re
import sys
import calendar
import unicodedata
from concurrent.futures import ThreadPoolExecutor
from datetime import timezone
from html import unescape
from sources.dates import now_local, PUERTO_RICO
from datetime import datetime, timedelta
from typing import List, Dict, Tuple

# Solo noticias de los últimos N días
MAX_DAYS_OLD = 14

# La URL base de Google News Search RSS
GNSS = "https://news.google.com/rss/search?q={}&hl=es-419&gl=PR&ceid=PR:es-419"

# ============================================================
# RSS DIRECTO DE PERIÓDICOS (verificados que funcionan)
# ============================================================
RSS_PERIODICOS = {
    "El Nuevo Día": "https://www.elnuevodia.com/arc/outboundfeeds/rss/?outputType=xml",
    "NotiCel": "https://www.noticel.com/rss",
    "Radio Isla": "https://radioisla.tv/feed/",
    "Es Noticia": ("https://www.esnoticiapr.com/feed/", {"User-Agent": "Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)"}, True),
    "Telemundo PR": "https://www.telemundopr.com/rss",
    # El Vocero RSS roto (404) — usando Google News en su lugar
    "Walo Radio": "https://waloradio.com/feed/",
    "El Oriental": "https://periodicoeloriental.com/feed/",
    "PR es La Isa": "https://www.puertoricolaisla.com/rss.xml",
    "NELPR": "https://nelpr.com/feed/",
}

# ============================================================
# GOOGLE NEWS — Búsquedas por municipio (15 noreste)
# ============================================================
RSS_MUNICIPIOS = {
    "San Juan": GNSS.format("\"San+Juan\"+municipio+Puerto+Rico"),
    "Carolina": GNSS.format("Carolina+Puerto+Rico+municipio"),
    "Caguas": GNSS.format("Caguas+Puerto+Rico+municipio"),
    "Fajardo": GNSS.format("Fajardo+Puerto+Rico"),
    "Humacao": GNSS.format("Humacao+Puerto+Rico"),
    "Trujillo Alto": GNSS.format("\"Trujillo+Alto\"+Puerto+Rico"),
    "Canóvanas": GNSS.format("Canovanas+Puerto+Rico"),
    "Loíza": GNSS.format("Loiza+Puerto+Rico"),
    "Río Grande": GNSS.format("\"Rio+Grande\"+Puerto+Rico"),
    "Luquillo": GNSS.format("Luquillo+Puerto+Rico"),
    "Ceiba": GNSS.format("Ceiba+Puerto+Rico+municipio"),
    "Naguabo": GNSS.format("Naguabo+Puerto+Rico"),
    "Cataño": GNSS.format("Catano+Puerto+Rico"),
    "Vieques": GNSS.format("Vieques+Puerto+Rico"),
    "Culebra": GNSS.format("Culebra+Puerto+Rico"),
}

# ============================================================
# GOOGLE NEWS — Facebook (municipios)
# Posts de las páginas oficiales de alcaldías que Google indexa
# ============================================================
RSS_FACEBOOK_MUNI = {
    "FB - San Juan": GNSS.format("site:facebook.com+SJCiudadCapital+San+Juan"),
    "FB - Carolina": GNSS.format("site:facebook.com+somoscarolina+Carolina"),
    "FB - Trujillo Alto": GNSS.format("site:facebook.com+trujilloalto+municipio"),
    "FB - Canóvanas": GNSS.format("site:facebook.com+canovanas+municipio"),
    "FB - Loíza": GNSS.format("site:facebook.com+loiza+municipio"),
    "FB - Río Grande": GNSS.format("site:facebook.com+riogrande+Puerto+Rico"),
    "FB - Luquillo": GNSS.format("site:facebook.com+luquillo+municipio"),
    "FB - Fajardo": GNSS.format("site:facebook.com+fajardo+municipio"),
    "FB - Ceiba": GNSS.format("site:facebook.com+ceiba+Puerto+Rico"),
    "FB - Naguabo": GNSS.format("site:facebook.com+naguabo+municipio"),
    "FB - Humacao": GNSS.format("site:facebook.com+humacao+municipio"),
    "FB - Caguas": GNSS.format("site:facebook.com+caguas+Puerto+Rico"),
    "FB - Cataño": GNSS.format("site:facebook.com+catano+municipio"),
    "FB - Vieques": GNSS.format("site:facebook.com+vieques+municipio"),
    "FB - Culebra": GNSS.format("site:facebook.com+culebra+Puerto+Rico"),
}

# ============================================================
# GOOGLE NEWS — Gobierno y políticos de PR
# ============================================================
RSS_GOBIERNO = {
    "Gobierno PR": GNSS.format("site:facebook.com+gobiernodepuertorico"),
    "Senado PR": GNSS.format("site:facebook.com+SenadoDePuertoRico"),
    "Cámara PR": GNSS.format("site:facebook.com+camaraconpr"),
    "Junta Gobierno": GNSS.format("site:facebook.com+JGOPR51"),
    "William Miranda": GNSS.format("site:facebook.com+williammirandatorresalcalde"),
    "Limarys Román": GNSS.format("site:facebook.com+limarys.roman.2025"),
}

# ============================================================
# GOOGLE NEWS — Medios, periodistas, y sitios sin RSS
# ============================================================
RSS_MEDIOS = {
    "Primera Hora": GNSS.format("site:primerahora.com+Puerto+Rico"),
    "El Nuevo Día (GN)": GNSS.format("site:elnuevodia.com+Puerto+Rico"),
    "El Vocero (GN)": GNSS.format("site:elvocero.com+Puerto+Rico"),
    "WAPA TV": GNSS.format("site:wapa.tv+noticias"),
    "NotiUno": "https://www.notiuno.com/search/?f=rss&t=article&l=10&s=start_time&sd=desc",
    "WKAQ 580": GNSS.format("site:wkaq580.com+Puerto+Rico"),
    "TeleOnce": GNSS.format("site:teleonce.com+Puerto+Rico"),
    "Xposed Magazine": GNSS.format("site:xposedmagazinenews24.com+Puerto+Rico"),
    "NotiCentro WAPA": GNSS.format("site:facebook.com+noticentrowapa"),
    "Telenoticias": GNSS.format("site:facebook.com+telenoticiaspr"),
    "Telemundo FB": GNSS.format("site:facebook.com+telemundo+PR+noticias"),
    "Las Noticias T11": GNSS.format("site:facebook.com+LasNoticiasT11"),
    "Moluscotv": GNSS.format("site:facebook.com+Moluscotv"),
    "Jay Fonseca": GNSS.format("site:facebook.com+JayFonsecaPR"),
    "Última Hora PR": GNSS.format("site:facebook.com+ultimahorapr2020"),
    "Noticias En Línea": GNSS.format("site:facebook.com+noticiasenlineapr"),
    "En Contacto 787": GNSS.format("site:facebook.com+encontacto787tv"),
}

# ============================================================
# CATEGORÍAS para la tabla de estado de fuentes
# Mapea cada fuente a su categoría visible en el dashboard
# ============================================================
CATEGORIAS = {
    # RSS directo
    "El Nuevo Día": "📰 RSS Directo",
    "NotiCel": "📰 RSS Directo",
    "Radio Isla": "📰 RSS Directo",
    "Es Noticia": "📰 RSS Directo",
    "Telemundo PR": "📰 RSS Directo",
    # El Vocero RSS directo removido (404) — cubierto por Google News
    "Walo Radio": "📰 RSS Directo",
    "El Oriental": "📰 RSS Directo",
    "PR es La Isa": "📰 RSS Directo",
    "NELPR": "📰 RSS Directo",
    # Google News - medios adicionales
    "Primera Hora": "📰 Google News",
    "El Nuevo Día (GN)": "📰 Google News",
    "El Vocero (GN)": "📰 Google News",
    "WAPA TV": "📰 Google News",
    "NotiUno": "📻 NotiUno",
    "WKAQ 580": "📰 Google News",
    "TeleOnce": "📰 Google News",
    "Xposed Magazine": "📰 Google News",
    "NotiCentro WAPA": "📰 Google News",
    "Telenoticias": "📰 Google News",
    "Telemundo FB": "📰 Google News",
    "Las Noticias T11": "📰 Google News",
    "Moluscotv": "📰 Google News",
    "Jay Fonseca": "📰 Google News",
    "Última Hora PR": "📰 Google News",
    "Noticias En Línea": "📰 Google News",
    "En Contacto 787": "📰 Google News",
    # Gobierno
    "Gobierno PR": "🏛️ Gobierno",
    "Senado PR": "🏛️ Gobierno",
    "Cámara PR": "🏛️ Gobierno",
    "Junta Gobierno": "🏛️ Gobierno",
    "William Miranda": "🏛️ Gobierno",
    "Limarys Román": "🏛️ Gobierno",
    # Facebook
    "FB - San Juan": "📘 Facebook",
    "FB - Carolina": "📘 Facebook",
    "FB - Trujillo Alto": "📘 Facebook",
    "FB - Canóvanas": "📘 Facebook",
    "FB - Loíza": "📘 Facebook",
    "FB - Río Grande": "📘 Facebook",
    "FB - Luquillo": "📘 Facebook",
    "FB - Fajardo": "📘 Facebook",
    "FB - Ceiba": "📘 Facebook",
    "FB - Naguabo": "📘 Facebook",
    "FB - Humacao": "📘 Facebook",
    "FB - Caguas": "📘 Facebook",
    "FB - Cataño": "📘 Facebook",
    "FB - Vieques": "📘 Facebook",
    "FB - Culebra": "📘 Facebook",
    # Municipios (Google News)
    "San Juan": "🏛️ Municipios",
    "Carolina": "🏛️ Municipios",
    "Caguas": "🏛️ Municipios",
    "Fajardo": "🏛️ Municipios",
    "Humacao": "🏛️ Municipios",
    "Trujillo Alto": "🏛️ Municipios",
    "Canóvanas": "🏛️ Municipios",
    "Loíza": "🏛️ Municipios",
    "Río Grande": "🏛️ Municipios",
    "Luquillo": "🏛️ Municipios",
    "Ceiba": "🏛️ Municipios",
    "Naguabo": "🏛️ Municipios",
    "Cataño": "🏛️ Municipios",
    "Vieques": "🏛️ Municipios",
    "Culebra": "🏛️ Municipios",
}

# ============================================================
# LISTA COMPLETA DE MUNICIPIOS NORESTE
# ============================================================
MUNICIPIOS_NORESTE = [
    "San Juan", "Carolina", "Trujillo Alto", "Caguas", "Luquillo",
    "Canóvanas", "Fajardo", "Loíza", "Río Grande", "Ceiba",
    "Naguabo", "Humacao", "Cataño", "Vieques", "Culebra",
]

VARIANTES = {
    "Loiza": "Loíza",
    "Rio Grande": "Río Grande",
    "Canovanas": "Canóvanas",
    "Catano": "Cataño",
}


def mentions_municipio(text: str) -> List[str]:
    """Match whole municipality names with or without accents."""
    def plain(value):
        return "".join(c for c in unicodedata.normalize("NFD", value.casefold())
                       if not unicodedata.combining(c))
    text = plain(text or "")
    # These names refer to US states or a fair, not the Puerto Rico municipality.
    text = re.sub(r"\b(?:(?:north|south)\s+carolina|carolina\s+(?:del\s+)?(?:norte|sur)|carolina\s+classic\s+fair)\b", "", text)
    # Remove explicit foreign places and artist/team names, preserving other local mentions.
    for pattern in [
        r"\bcarolina\s+(?:panthers|hurricanes)\b",
        r"\bsoge\s+culebra\b",
        r"\brio\s+grande\s+(?:do\s+(?:sul|norte)|del\s+sur)\b",
        r"\b(?:la\s+)?ceiba\s*,?\s*(?:en\s+)?honduras\b",
        r"\bsan\s+juan\s*,?\s*(?:(?:en|de)\s+)?(?:argentina|republica\s+dominicana)\b",
        r"\brio\s+grande\s*,?\s*(?:(?:en|de)\s+)?(?:texas|nuevo\s+mexico|new\s+mexico|argentina|brasil)\b",
    ]:
        text = re.sub(pattern, "", text)
    return [m for m in MUNICIPIOS_NORESTE
            if re.search(r"(?<!\w)" + re.escape(plain(m)) + r"(?!\w)", text)]


def is_relevant_title(title: str) -> bool:
    """Quick pre-filter: skip clearly irrelevant international topics."""
    if mentions_municipio(title):
        return True
    title_lower = title.lower()
    skip_words = [
        "real madrid", "champions league", "premier league",
        "nfl", "messi", "cristiano",
        "iran", "israel", "hamas", "china", "rusia",
        "ucrania", "cuba", "venezuela",
    ]
    for word in skip_words:
        if word in title_lower:
            return False
    return True


def fetch_rss(source_name: str, feed_url: str, max_articles: int = 10, extra_headers: dict = None, use_curl: bool = False) -> Tuple[List[Dict], str]:
    """Fetch and parse an RSS feed.
    
    Returns (articles, status_string).
    Status is 'ok' for success or the error message for failure.
    """
    import time as _time
    
    def _do_fetch():
        try:
            if use_curl:
                import subprocess as sp
                curl_cmd = ['curl', '-fsSL', '--max-time', '10']
                if extra_headers:
                    for k, v in extra_headers.items():
                        curl_cmd += ['-H', f'{k}: {v}']
                else:
                    curl_cmd += ['-H', 'User-Agent: Mozilla/5.0']
                curl_cmd.append(feed_url)
                result = sp.run(curl_cmd, capture_output=True, text=True, timeout=15)
                if result.returncode != 0:
                    return None, f"curl error: exit {result.returncode}"
                feed = feedparser.parse(result.stdout)
            else:
                headers = {'User-Agent': 'Mozilla/5.0'}
                if extra_headers:
                    headers.update(extra_headers)
                req = urllib.request.Request(feed_url, headers=headers)
                with urllib.request.urlopen(req, timeout=10) as resp:
                    feed_data = resp.read()
                feed = feedparser.parse(io.BytesIO(feed_data))
        except Exception as e:
            return None, f"timeout/error: {e}"
        return feed, None

    # Retry with exponential backoff for rate limits
    feed = None
    last_error = None
    for attempt in range(2):
        feed, err = _do_fetch()
        if err is None:
            break
        last_error = err
        if attempt < 1:
            _time.sleep(2 ** attempt)  # 1s, 2s backoff
    else:
        return [], f"rate-limited/error: {last_error}"

    articles = []
    cutoff = now_local() - timedelta(days=MAX_DAYS_OLD)

    if not feed.entries and not getattr(feed, "version", ""):
        return [], "respuesta inválida: no es un feed RSS/Atom"

    for entry in feed.entries[:200]:
        title = unescape(re.sub(r"<[^>]+>", "", entry.get("title", "")))
        if urlsplit(feed_url).hostname == "news.google.com":
            publisher = (entry.get("source") or {}).get("title", "").strip()
            suffix = " - " + publisher
            if publisher and title.endswith(suffix):
                title = title[:-len(suffix)].rstrip()
        if not title or not is_relevant_title(title):
            continue

        link = entry.get("link", "")
        raw_date = entry.get("published_parsed") or entry.get("updated_parsed")

            # Parse date
        if raw_date:
            try:
                dt = datetime.fromtimestamp(calendar.timegm(raw_date), timezone.utc).astimezone(PUERTO_RICO)
                date_str = dt.strftime("%Y-%m-%d %H:%M")
            except Exception:
                continue
        else:
            continue

            # Skip old articles
        if dt < cutoff or dt > now_local():
            continue

            # Buscar municipio en título
        municipios = mentions_municipio(title)

            # Si no encontró, buscar en descripción
        if not municipios:
            summary = entry.get("summary", "") or entry.get("description", "")
            clean_text = re.sub(r'<[^>]+>', ' ', summary)[:300]
            municipios = mentions_municipio(clean_text)

        if municipios:
            articles.append({
                "titular": title.strip(),
                "enlace": link,
                "fuente": source_name,
                "fecha": date_str,
                "municipios": municipios,
                "tipo": "RSS",
            })

            if len(articles) >= max_articles:
                break

    if articles:
        return articles, "ok"
        # Feed responded but no relevant articles found
    feed_title = getattr(feed, 'feed', None)
    if feed_title is not None or len(feed.entries) > 0:
        return articles, "ok"
    return articles, "ok"  # Empty feed but reachable


def fetch_all(max_per_feed: int = 8) -> Tuple[List[Dict], Dict[str, str]]:
    """Fetch all sources and return (articles, source_status).
    
    source_status maps source name -> status string for the dashboard table.
    """
    all_articles = []
    source_status = {}

    fuentes = [
        ("📰 Periódicos", RSS_PERIODICOS),
        ("🏛️ Municipios", RSS_MUNICIPIOS),
        ("📘 Facebook Mun.", RSS_FACEBOOK_MUNI),
        ("🏛️ Gobierno", RSS_GOBIERNO),
        ("📺 Medios", RSS_MEDIOS),
    ]

    tasks = []
    for _, feed_dict in fuentes:
        for name, entry in feed_dict.items():
            if isinstance(entry, tuple):
                url = entry[0]
                headers = entry[1] if len(entry) > 1 else None
                curl = entry[2] if len(entry) > 2 else False
            else:
                url, headers, curl = entry, None, False
            tasks.append((name, url, headers, curl))

    def collect(task):
        name, url, headers, curl = task
        try:
            articles, status = fetch_rss(name, url, max_per_feed, headers, curl)
        except Exception as exc:
            articles, status = [], f"error: {type(exc).__name__}"
        return name, articles, status

    # Bound concurrency and preserve source ordering for deterministic output.
    with ThreadPoolExecutor(max_workers=6) as pool:
        for name, articles, status in pool.map(collect, tasks):
            print(f"  📡 {name}: {len(articles)} artículos ({status})")
            all_articles.extend(articles)
            source_status[name] = "✅ OK" if status == "ok" else f"❌ {status}"
    return all_articles, source_status
