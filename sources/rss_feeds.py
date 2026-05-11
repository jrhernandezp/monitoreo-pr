"""RSS feed sources for municipal news monitoring."""
import feedparser
import re
import sys
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
    "Es Noticia": "https://www.esnoticiapr.com/feed/",
    "Telemundo PR": "https://www.telemundopr.com/rss",
    "El Vocero": "https://www.elvocero.com/rss/noticias",
    "Walo Radio": "https://waloradio.com/feed/",
    "El Oriental": "https://periodicoeloriental.com/feed/",
    "PR es La Isa": "https://www.puertoricolaisla.com/rss.xml",
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
    "NotiUno": GNSS.format("site:notiuno.com+Puerto+Rico"),
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
    "El Vocero": "📰 RSS Directo",
    "Walo Radio": "📰 RSS Directo",
    "El Oriental": "📰 RSS Directo",
    "PR es La Isa": "📰 RSS Directo",
    # Google News - medios adicionales
    "Primera Hora": "📰 Google News",
    "El Nuevo Día (GN)": "📰 Google News",
    "El Vocero (GN)": "📰 Google News",
    "WAPA TV": "📰 Google News",
    "NotiUno": "📰 Google News",
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
    """Check if text mentions any of the tracked municipalities."""
    text_lower = text.lower()
    found = []
    for m in MUNICIPIOS_NORESTE:
        if m.lower() in text_lower:
            found.append(m)
    for variant, canonical in VARIANTES.items():
        if variant.lower() in text_lower and canonical not in found:
            found.append(canonical)
    return found


def is_relevant_title(title: str) -> bool:
    """Quick pre-filter: skip clearly irrelevant international topics."""
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


def fetch_rss(source_name: str, feed_url: str, max_articles: int = 10) -> Tuple[List[Dict], str]:
    """Fetch and parse an RSS feed.
    
    Returns (articles, status_string).
    Status is 'ok' for success or the error message for failure.
    """
    try:
        feed = feedparser.parse(feed_url)
        articles = []
        cutoff = datetime.now() - timedelta(days=MAX_DAYS_OLD)

        for entry in feed.entries[:max_articles]:
            title = entry.get("title", "")
            if not title or not is_relevant_title(title):
                continue

            link = entry.get("link", "")
            raw_date = entry.get("published_parsed")

            # Parse date
            if raw_date:
                try:
                    dt = datetime(*raw_date[:6])
                    date_str = dt.strftime("%Y-%m-%d %H:%M")
                except Exception:
                    dt = datetime.now()
                    date_str = dt.strftime("%Y-%m-%d %H:%M")
            else:
                dt = datetime.now()
                date_str = dt.strftime("%Y-%m-%d %H:%M")

            # Skip old articles
            if dt < cutoff:
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

        if articles:
            return articles, "ok"
        # Feed responded but no relevant articles found
        feed_title = getattr(feed, 'feed', None)
        if feed_title is not None or len(feed.entries) > 0:
            return articles, "ok"
        return articles, "ok"  # Empty feed but reachable
    except Exception as e:
        return [], f"error: {e}"


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

    for emoji, feed_dict in fuentes:
        for name, url in feed_dict.items():
            print(f"  {emoji} {name}...", end=" ")
            sys.stdout.flush()
            articles, status = fetch_rss(name, url, max_per_feed)
            if articles:
                print(f"→ {len(articles)}")
                for a in articles:
                    print(f"       [{', '.join(a['municipios'])}] {a['titular'][:70]}")
            else:
                print(f"→ {status}")
            all_articles.extend(articles)
            # Guardar estado para el dashboard
            if status == "ok":
                source_status[name] = "✅ OK"
            else:
                source_status[name] = f"❌ {status}"

    return all_articles, source_status
