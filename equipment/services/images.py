"""Find illustrative photos for equipment/components being explained.

Sources, in priority order:
- Google Images via the official Programmable Search Engine API (best
  relevance; free 100 queries/day) — used when GOOGLE_CSE_KEY and
  GOOGLE_CSE_ID are set in .env.
- Wikimedia Commons — huge library of medical device photos (free, no key).
- Openverse (WordPress) — CC-licensed image search (free, no key).

The AI inserts markers like ``[IMAGE: infusion pump peristaltic mechanism]``
in its answer; ``illustrate()`` replaces each marker with a markdown image
plus a source link, or removes the marker when nothing suitable is found.
"""
import os
import re
from concurrent.futures import ThreadPoolExecutor

import requests

TIMEOUT = 8
HEADERS = {"User-Agent": "Biomedly/1.0 (educational biomed repair assistant)"}
MAX_MARKERS = 12
_MARKER_RE = re.compile(r"\[IMAGE:\s*([^\]\n]{3,120})\]")

# Small in-process cache: common component queries repeat constantly.
_CACHE: dict[str, dict | None] = {}
_CACHE_MAX = 500


def _google(query: str) -> dict | None:
    """Google image search via the official Programmable Search Engine API."""
    key = os.getenv("GOOGLE_CSE_KEY", "").strip()
    cx = os.getenv("GOOGLE_CSE_ID", "").strip()
    if not (key and cx):
        return None
    try:
        r = requests.get(
            "https://www.googleapis.com/customsearch/v1",
            params={
                "key": key,
                "cx": cx,
                "q": query,
                "searchType": "image",
                "num": 3,
                "safe": "active",
                # Bias toward real equipment photos over clipart/diagrams/
                # icons/line-art, and away from tiny thumbnails — this is
                # the main lever for "more accurate" results.
                "imgType": "photo",
                "imgSize": "large",
            },
            timeout=TIMEOUT,
        )
        r.raise_for_status()
        items = r.json().get("items") or []
    except (requests.RequestException, ValueError):
        return None

    for item in items:
        info = item.get("image") or {}
        thumb = item.get("link") or info.get("thumbnailLink")
        if thumb:
            return {
                "thumb": thumb,
                "page": info.get("contextLink") or thumb,
                "source": item.get("displayLink") or "Google Images",
            }
    return None


def _wikimedia(query: str) -> dict | None:
    try:
        r = requests.get(
            "https://commons.wikimedia.org/w/api.php",
            params={
                "action": "query",
                "format": "json",
                "generator": "search",
                # intitle: keeps results precise — the filename must contain
                # the words, avoiding loose full-text matches (e.g. old book
                # scans that merely mention the term).
                "gsrsearch": f"filetype:bitmap intitle:{query}",
                "gsrlimit": 1,
                "gsrnamespace": 6,  # File:
                "prop": "imageinfo",
                "iiprop": "url",
                "iiurlwidth": 520,
            },
            headers=HEADERS,
            timeout=TIMEOUT,
        )
        r.raise_for_status()
        pages = (r.json().get("query") or {}).get("pages") or {}
        for page in pages.values():
            info = (page.get("imageinfo") or [{}])[0]
            thumb = info.get("thumburl")
            if thumb:
                return {
                    "thumb": thumb,
                    "page": info.get("descriptionurl") or "https://commons.wikimedia.org",
                    "source": "Wikimedia Commons",
                }
    except (requests.RequestException, ValueError):
        pass
    return None


def _openverse(query: str) -> dict | None:
    try:
        r = requests.get(
            "https://api.openverse.org/v1/images/",
            params={"q": query, "page_size": 1},
            headers=HEADERS,
            timeout=TIMEOUT,
        )
        r.raise_for_status()
        results = r.json().get("results") or []
        if results:
            item = results[0]
            thumb = item.get("thumbnail") or item.get("url")
            if thumb:
                return {
                    "thumb": thumb,
                    "page": item.get("foreign_landing_url") or item.get("url"),
                    "source": item.get("source") or "Openverse",
                }
    except (requests.RequestException, ValueError):
        pass
    return None


def _candidates(query: str) -> list[str]:
    """The query itself, then progressively simpler fallbacks."""
    words = query.split()
    options = [query]
    if len(words) > 2:
        options.append(" ".join(words[-2:]))  # trailing pair, e.g. "peristaltic mechanism"
        options.append(" ".join(words[:2]))   # leading pair, e.g. "infusion pump"
    return list(dict.fromkeys(options))


def find_image(query: str) -> dict | None:
    """Best photo for a query, simplifying the phrase until something matches.

    Precision beats coverage here: a wrong photo is worse than none, so only
    title-matched Wikimedia results and Openverse results are used.
    """
    key = query.strip().lower()
    if key in _CACHE:
        return _CACHE[key]

    result = None
    for candidate in _candidates(query):
        result = _google(candidate) or _wikimedia(candidate) or _openverse(candidate)
        if result:
            break

    if len(_CACHE) >= _CACHE_MAX:
        _CACHE.clear()
    _CACHE[key] = result
    return result


def illustrate(markdown: str) -> str:
    """Replace [IMAGE: ...] markers with real images (or drop them)."""
    markers = _MARKER_RE.findall(markdown)[:MAX_MARKERS]
    if not markers:
        return _MARKER_RE.sub("", markdown)

    # Fetch all candidate images in parallel to keep the request fast.
    unique = list(dict.fromkeys(m.strip() for m in markers))
    with ThreadPoolExecutor(max_workers=min(12, len(unique))) as pool:
        found = dict(zip(unique, pool.map(find_image, unique)))

    used = 0

    def _replace(match: re.Match) -> str:
        nonlocal used
        query = match.group(1).strip()
        image = found.get(query)
        if not image or used >= MAX_MARKERS:
            return ""
        used += 1
        return (
            f"\n![{query}]({image['thumb']})\n"
            f"*Illustration: [{image['source']}]({image['page']}) — "
            f"may differ from your exact unit.*\n"
        )

    return _MARKER_RE.sub(_replace, markdown)
