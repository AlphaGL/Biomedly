"""Find service/user manuals for an exact equipment model.

Order:
1. iFixit's own attached documents (``ifixit.get_device`` — surfaced
   separately on the device page already).
2. Google Programmable Search, web mode, PDF-restricted — finds manuals for
   models iFixit doesn't have at all (this is the gap: a search engine
   covers every manufacturer's site, not just what iFixit's community has
   uploaded). Requires GOOGLE_CSE_KEY + GOOGLE_CSE_ID in .env.
3. Always available: a ready-made Google search URL that needs no API key
   and no quota — so the feature never dead-ends even before those keys
   are configured.
"""
from __future__ import annotations

import os

import requests

TIMEOUT = 10
HEADERS = {"User-Agent": "Biomedly/1.0 (educational biomed repair assistant)"}
MANUAL_TERMS = "service manual OR user manual OR operator manual"


def google_search_url(model: str) -> str:
    """Plain Google search link — always available, no API key needed."""
    query = f'"{model}" {MANUAL_TERMS} filetype:pdf'
    return "https://www.google.com/search?q=" + requests.utils.quote(query)


def search_manuals(model: str, limit: int = 5) -> list[dict]:
    """Web-search for manual PDFs via Google Custom Search (requires keys)."""
    key = os.getenv("GOOGLE_CSE_KEY", "").strip()
    cx = os.getenv("GOOGLE_CSE_ID", "").strip()
    if not (key and cx) or not model.strip():
        return []

    try:
        r = requests.get(
            "https://www.googleapis.com/customsearch/v1",
            params={
                "key": key,
                "cx": cx,
                "q": f"{model} {MANUAL_TERMS}",
                "fileType": "pdf",
                "num": limit,
                "safe": "active",
            },
            headers=HEADERS,
            timeout=TIMEOUT,
        )
        r.raise_for_status()
        items = r.json().get("items") or []
    except (requests.RequestException, ValueError):
        return []

    results = []
    for item in items:
        link = item.get("link") or ""
        if not link.lower().endswith(".pdf"):
            continue
        results.append({
            "title": item.get("title") or "Manual",
            "url": link,
            "source": item.get("displayLink") or "",
            "snippet": (item.get("snippet") or "")[:200],
        })
    return results
