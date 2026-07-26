"""iFixit public API client.

iFixit hosts the world's largest open medical-equipment repair library
(https://www.ifixit.com/biomed). Docs: https://www.ifixit.com/api-docs
No API key is required for read-only access. Content is CC BY-NC-SA —
always shown with attribution and a link back.
"""
import re

import requests

BASE = "https://www.ifixit.com/api/2.0"
TIMEOUT = 12
HEADERS = {"User-Agent": "Biomedly/1.0 (educational biomed repair assistant)"}


def _quote(text: str) -> str:
    return requests.utils.quote(text, safe="")


def _text_list(items) -> list[str]:
    """iFixit fields are sometimes strings, sometimes objects — normalize."""
    out = []
    for item in items or []:
        if isinstance(item, str):
            out.append(item)
        elif isinstance(item, dict):
            text = item.get("text") or item.get("title") or item.get("name") or ""
            if text:
                out.append(str(text))
    return out


def _sanitize_html(html: str) -> str:
    """Strip active content from iFixit-rendered HTML before embedding."""
    if not html:
        return ""
    html = re.sub(r"(?is)<(script|style|iframe|object|embed)[^>]*>.*?</\1>", "", html)
    html = re.sub(r"(?is)<(script|style|iframe|object|embed)[^>]*/?>", "", html)
    html = re.sub(r"(?i)\son\w+\s*=\s*\"[^\"]*\"", "", html)
    html = re.sub(r"(?i)\son\w+\s*=\s*'[^']*'", "", html)
    html = re.sub(r"(?i)javascript\s*:", "", html)
    return html


def search_guides(query: str, limit: int = 8) -> list[dict]:
    """Search iFixit repair guides for a piece of equipment."""
    try:
        r = requests.get(
            f"{BASE}/search/{_quote(query)}",
            params={"filter": "guide", "limit": limit},
            headers=HEADERS,
            timeout=TIMEOUT,
        )
        r.raise_for_status()
        results = r.json().get("results", [])
    except (requests.RequestException, ValueError):
        return []

    guides = []
    for item in results:
        image = item.get("image") or {}
        guides.append({
            "guideid": item.get("guideid"),
            "title": item.get("title", ""),
            "url": item.get("url", ""),
            "summary": item.get("summary") or "",
            "image": image.get("thumbnail") or image.get("standard") or "",
            "difficulty": item.get("difficulty") or "",
            "category": item.get("category") or "",
        })
    return guides


def search_devices(query: str, limit: int = 6) -> list[dict]:
    """Search iFixit device/category wiki pages (device overviews)."""
    try:
        r = requests.get(
            f"{BASE}/search/{_quote(query)}",
            params={"filter": "device", "limit": limit},
            headers=HEADERS,
            timeout=TIMEOUT,
        )
        r.raise_for_status()
        results = r.json().get("results", [])
    except (requests.RequestException, ValueError):
        return []

    devices = []
    for item in results:
        image = item.get("image") or {}
        devices.append({
            "title": item.get("title", ""),
            "url": item.get("url", ""),
            "summary": item.get("summary") or "",
            "image": image.get("thumbnail") or image.get("standard") or "",
        })
    return devices


def _titles_match_query(query: str, titles: list[str]) -> bool:
    """True only if some result title contains every word of the query —
    iFixit's search is fuzzy (e.g. 'Acuson X700' returns the X300), so a
    non-empty result list does NOT mean the exact model exists.
    """
    words = [w.lower() for w in query.split() if w]
    return any(
        all(w in title.lower() for w in words)
        for title in titles
    )


def search_with_fallback(query: str) -> dict:
    """Search devices+guides; when nothing matches, progressively simplify
    the query (drop trailing words, e.g. a model number iFixit doesn't have)
    so the closest relatives still show — clearly flagged as inexact.
    """
    devices = search_devices(query)
    guides = search_guides(query)
    effective = query

    words = query.split()
    while not devices and not guides and len(words) > 1:
        words = words[:-1]
        effective = " ".join(words)
        devices = search_devices(effective)
        guides = search_guides(effective)

    exact = _titles_match_query(
        query,
        [d["title"] for d in devices] + [g["title"] for g in guides],
    )
    return {
        "devices": devices,
        "guides": guides,
        "effective_query": effective,
        "exact": exact,
    }


def get_device(title: str) -> dict | None:
    """Full device wiki page: description, image, tools, and its guides."""
    try:
        r = requests.get(
            f"{BASE}/wikis/CATEGORY/{_quote(title)}",
            headers=HEADERS,
            timeout=TIMEOUT,
        )
        if r.status_code != 200:
            return None
        data = r.json()
    except (requests.RequestException, ValueError):
        return None

    guides = []
    for g in data.get("guides") or []:
        image = g.get("image") or {}
        guides.append({
            "guideid": g.get("guideid"),
            "title": g.get("title", ""),
            "url": g.get("url", ""),
            "image": image.get("thumbnail") or image.get("standard") or "",
            "difficulty": g.get("difficulty") or "",
            "time": g.get("time_required") or "",
            "type": g.get("type") or "",
        })

    # Service manuals / reference PDFs — the core of iFixit's medical library.
    documents = []
    for doc in data.get("documents") or []:
        guid = doc.get("guid")
        if not guid:
            continue
        doc_image = doc.get("image") or {}
        documents.append({
            "title": (doc.get("title") or doc.get("filename") or "Document")
                     .removesuffix(".pdf"),
            "url": f"https://documents.cdn.ifixit.com/{guid}.pdf",
            "pages": doc.get("pages") or 0,
            "size_mb": round((doc.get("size") or 0) / (1024 * 1024), 1),
            "thumb": doc_image.get("thumbnail") or "",
        })

    # Family categories (e.g. "Baxter Infusion Pump") keep guides/documents
    # on their child models — expose them for navigation.
    children = []
    for child in data.get("children") or []:
        if isinstance(child, str):
            children.append({"title": child, "image": ""})
        elif isinstance(child, dict) and child.get("title"):
            child_image = child.get("image") or {}
            children.append({
                "title": child["title"],
                "image": child_image.get("thumbnail") or "",
            })

    image = data.get("image") or {}
    raw_title = data.get("title", title)
    return {
        "title": data.get("display_title") or raw_title,
        "summary": data.get("summary") or "",
        "contents": _sanitize_html(data.get("contents_rendered") or ""),
        "image": image.get("standard") or image.get("medium") or image.get("thumbnail") or "",
        "url": f"https://www.ifixit.com/Device/{_quote(raw_title.replace(' ', '_'))}",
        "guides": guides,
        "documents": documents,
        "children": children[:24],
        "tools": _text_list(data.get("tools"))[:12],
        "flags": _text_list(data.get("flags"))[:4],
    }


def get_guide(guideid: int) -> dict | None:
    """Full repair guide with step-by-step text and images."""
    try:
        r = requests.get(
            f"{BASE}/guides/{int(guideid)}",
            headers=HEADERS,
            timeout=TIMEOUT,
        )
        if r.status_code != 200:
            return None
        data = r.json()
    except (requests.RequestException, ValueError):
        return None

    steps = []
    for s in data.get("steps") or []:
        lines = [
            _sanitize_html(l.get("text_rendered") or "")
            for l in (s.get("lines") or [])
        ]
        images = []
        media = s.get("media") or {}
        if media.get("type") == "image":
            for m in media.get("data") or []:
                if isinstance(m, dict):
                    url = m.get("standard") or m.get("medium") or m.get("thumbnail")
                    if url:
                        images.append(url)
        steps.append({
            "title": s.get("title") or "",
            "lines": [l for l in lines if l],
            "images": images[:3],
        })

    image = data.get("image") or {}
    return {
        "guideid": data.get("guideid"),
        "title": data.get("title", ""),
        "url": data.get("url", ""),
        "image": image.get("standard") or image.get("thumbnail") or "",
        "difficulty": data.get("difficulty") or "",
        "time": data.get("time_required") or "",
        "intro": _sanitize_html(data.get("introduction_rendered") or ""),
        "conclusion": _sanitize_html(data.get("conclusion_rendered") or ""),
        "tools": _text_list(data.get("tools"))[:12],
        "parts": _text_list(data.get("parts"))[:12],
        "steps": steps,
    }
