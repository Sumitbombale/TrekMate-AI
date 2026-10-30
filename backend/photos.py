"""Trek photos from Wikimedia Commons (free, no API key needed).

Used by:
  - /api/chat    : attaches 1-2 photos when the question mentions a known trek
  - /api/photos  : photos for any search text (used by the Find a Trek cards)
Photos are freely licensed; the credit + licence are returned so the UI can show attribution.
"""
import logging
import re
from functools import lru_cache

import requests

logger = logging.getLogger(__name__)

API = "https://commons.wikimedia.org/w/api.php"
HEADERS = {"User-Agent": "TrekMate-MCA-Project/1.0 (student project)"}
OK_MIME = {"image/jpeg", "image/png", "image/webp"}
# File titles containing these words are usually maps/logos/diagrams, not scenery
SKIP_WORDS = ("map", "logo", "flag", "coat of arms", "locator", "diagram", "plan", "icon",
              "poster", "stamp", "banner", "sketch", "painting", "drawing", "chart")


def _clean(html: str) -> str:
    return re.sub(r"<[^>]+>", "", html or "").strip()


@lru_cache(maxsize=256)
def _fetch(query: str, n: int) -> tuple:
    r = requests.get(
        API,
        params={
            "action": "query", "format": "json",
            "generator": "search", "gsrsearch": f"{query} filetype:bitmap",
            "gsrnamespace": 6, "gsrlimit": 15,
            "prop": "imageinfo", "iiprop": "url|mime|extmetadata", "iiurlwidth": 800,
        },
        headers=HEADERS, timeout=10,
    )
    pages = r.json().get("query", {}).get("pages", {})
    ranked = sorted(pages.values(), key=lambda p: p.get("index", 99))
    out = []
    for p in ranked:
        info = (p.get("imageinfo") or [{}])[0]
        title = p.get("title", "")
        if info.get("mime") not in OK_MIME:
            continue
        if any(w in title.lower() for w in SKIP_WORDS):
            continue
        url = info.get("thumburl") or info.get("url") or ""
        if not url.startswith("https://upload.wikimedia.org/"):
            continue
        page = info.get("descriptionurl") or ""
        meta = info.get("extmetadata", {})
        out.append((
            url,
            title.replace("File:", "").rsplit(".", 1)[0],
            page if page.startswith("https://commons.wikimedia.org/") else "",
            _clean(meta.get("Artist", {}).get("value"))[:80],
            _clean(meta.get("LicenseShortName", {}).get("value"))[:40],
        ))
        if len(out) >= n:
            break
    return tuple(out)


def search_photos(query: str, n: int = 2) -> list:
    """Return up to n photos as dicts: url, title, page, credit, license. Never raises."""
    try:
        rows = _fetch(query.strip(), max(1, min(n, 4)))
    except Exception:
        logger.exception("Photo search failed for %r", query)
        return []
    return [{"url": u, "title": t, "page": pg, "credit": c, "license": lic} for u, t, pg, c, lic in rows]