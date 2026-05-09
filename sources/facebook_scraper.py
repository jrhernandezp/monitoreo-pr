#!/usr/bin/env python3
"""
Facebook Municipal Scraper — Extrae posts públicos de páginas municipales 
usando la versión mobile de Facebook (m.facebook.com).

Sin API key. Sin App Review. Usa requests + BeautifulSoup.
"""
import sys
import re
import json
import time
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Dict, Optional

# ──────────────────────────────────────────────────────
# CONFIG: Páginas municipales del noreste de PR
# ──────────────────────────────────────────────────────
PAGINAS_MUNICIPALES = {
    "San Juan":        "SJCiudadCapital",
    "Carolina":        "Carolina",
    "Trujillo Alto":   "TrujilloAlto",
    "Caguas":          "Caguas",
    "Fajardo":         "Fajardo",
    "Humacao":         "Humacao",
    "Canóvanas":       "Canovanas",
    "Loíza":           "Loiza",
    "Río Grande":      "RioGrande",
    "Luquillo":        "Luquillo",
    "Ceiba":           "Ceiba",
    "Naguabo":         "Naguabo",
    "Cataño":          "Catano",
    "Vieques":         "Vieques",
    "Culebra":         "Culebra",
}

HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept-Language": "es-ES,es;q=0.9,en;q=0.8",
}

CACHE_DIR = Path(__file__).parent / "data" / "facebook_cache"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
CACHE_TTL = 1800  # 30 minutos


def get_cache_key(username: str) -> Path:
    return CACHE_DIR / f"{username}.html"


def load_cached(username: str) -> Optional[str]:
    cache_file = get_cache_key(username)
    if cache_file.exists():
        age = time.time() - cache_file.stat().st_mtime
        if age < CACHE_TTL:
            return cache_file.read_text(encoding="utf-8")
    return None


def save_cache(username: str, html: str):
    get_cache_key(username).write_text(html, encoding="utf-8")


def fetch_page_posts(username: str, max_posts: int = 10) -> List[Dict]:
    """Fetch public posts from a Facebook page via m.facebook.com."""
    url = f"https://m.facebook.com/{username}/posts"
    
    cached = load_cached(username)
    if cached:
        html = cached
    else:
        try:
            resp = requests.get(url, headers=HEADERS, timeout=15)
            if resp.status_code != 200:
                print(f"  ⚠ {username}: HTTP {resp.status_code}")
                return []
            html = resp.text
            save_cache(username, html)
        except Exception as e:
            print(f"  ❌ {username}: {e}")
            return []
    
    soup = BeautifulSoup(html, "html.parser")
    posts = []
    
    # m.facebook.com structure: articles or div.story_body_container
    for article in soup.find_all("article"):
        try:
            # Extract post text
            msg_div = article.find("div", {"data-ft": True})
            post_text = ""
            if msg_div:
                post_text = msg_div.get_text(strip=True)
            
            # Try other selectors for message
            if not post_text:
                for sel in ["p", "div._5rgt", "div.story_body_container"]:
                    elem = article.find(sel)
                    if elem:
                        post_text = elem.get_text(strip=True)[:500]
                        break
            
            if not post_text:
                continue
            
            # Extract link
            link = ""
            for a_tag in article.find_all("a"):
                href = a_tag.get("href", "")
                if "story.php" in href or "posts/" in href:
                    if href.startswith("/"):
                        href = "https://m.facebook.com" + href
                    link = href
                    break
            
            # Fallback: find any link that looks like a permalink
            if not link:
                for a_tag in article.find_all("a"):
                    href = a_tag.get("href", "")
                    if "facebook.com" in href and ("posts" in href or "photos" in href):
                        link = href
                        break
            
            if link:
                posts.append({
                    "texto": post_text[:500],
                    "enlace": link,
                    "fecha": datetime.now().strftime("%Y-%m-%d %H:%M"),
                })
                
                if len(posts) >= max_posts:
                    break
                    
        except Exception:
            continue
    
    return posts


def fetch_all(max_per_page: int = 5) -> List[Dict]:
    """Fetch posts from all municipal pages."""
    all_posts = []
    
    for municipio, username in PAGINAS_MUNICIPALES.items():
        print(f"  📘 {municipio} (@{username})...", end=" ", flush=True)
        posts = fetch_page_posts(username, max_per_page)
        if posts:
            for p in posts:
                p["municipio"] = municipio
                p["fuente"] = f"Facebook - {municipio}"
            all_posts.extend(posts)
            print(f"→ {len(posts)} posts")
        else:
            print("→ 0")
        time.sleep(1)  # Be gentle to FB
    
    return all_posts


if __name__ == "__main__":
    posts = fetch_all()
    print(f"\n📊 Total: {len(posts)} posts")
    for p in posts:
        print(f"  [{p['municipio']}] {p['texto'][:80]}")
