"""RSS feed sources for municipal news monitoring."""
import feedparser
import re
from datetime import datetime, timedelta
from typing import List, Dict

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
}

# ============================================================
# GOOGLE NEWS — Búsquedas por municipio (15 noreste)
# ============================================================
RSS_MUNICIPIOS = {
    # Grandes
    "San Juan": GNSS.format("\"San+Juan\"+municipio+Puerto+Rico"),
    "Carolina": GNSS.format("Carolina+Puerto+Rico+municipio"),
    "Caguas": GNSS.format("Caguas+Puerto+Rico+municipio"),
    "Fajardo": GNSS.format("Fajardo+Puerto+Rico"),
    "Humacao": GNSS.format("Humacao+Puerto+Rico"),
    # Medianos
    "Trujillo Alto": GNSS.format("\"Trujillo+Alto\"+Puerto+Rico"),
    "Canóvanas": GNSS.format("Canovanas+Puerto+Rico"),
    "Loíza": GNSS.format("Loiza+Puerto+Rico"),
    "Río Grande": GNSS.format("\"Rio+Grande\"+Puerto+Rico"),
    "Luquillo": GNSS.format("Luquillo+Puerto+Rico"),
    "Ceiba": GNSS.format("Ceiba+Puerto+Rico+municipio"),
    # Pequeños
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
# GOOGLE NEWS — Medios y periodistas de PR
# ============================================================
RSS_MEDIOS = {
    "Primera Hora": GNSS.format("site:primerahora.com+Puerto+Rico"),
    "El Nuevo Día (GN)": GNSS.format("site:elnuevodia.com+Puerto+Rico"),
    "El Vocero (GN)": GNSS.format("site:elvocero.com+Puerto+Rico"),
    "WAPA TV": GNSS.format("site:wapa.tv+noticias"),
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


def fetch_rss(source_name: str, feed_url: str, max_articles: int = 10) -> List[Dict]:
    """Fetch and parse an RSS feed, returning only recent articles about tracked municipalities."""
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

            # --- Buscar municipio en título ---
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
        return articles
    except Exception as e:
        print(f"  ⚠ Error: {source_name}: {e}")
        return []


def fetch_all(max_per_feed: int = 8) -> List[Dict]:
    """Fetch all sources: periódicos, municipios, Facebook, gobierno, medios."""
    all_articles = []
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
            articles = fetch_rss(name, url, max_per_feed)
            if articles:
                print(f"→ {len(articles)}")
                for a in articles:
                    print(f"       [{', '.join(a['municipios'])}] {a['titular'][:70]}")
            else:
                print("→ 0")
            all_articles.extend(articles)

    return all_articles


import sys
