"""Supplier cross-reference for a part number.

No distributor offers a free public API for this, so — same honest pattern
as the manual finder — this builds direct search-by-part-number URLs to the
major electronics distributors. Zero cost, zero keys, always works; it just
doesn't confirm the part is actually in stock before you click through.
"""
from __future__ import annotations

import requests

SUPPLIERS = [
    ("Digi-Key", "https://www.digikey.com/en/products/result?keywords={q}"),
    ("Mouser", "https://www.mouser.com/c/?q={q}"),
    ("Newark / element14", "https://www.newark.com/search?st={q}"),
    ("Google Shopping", "https://www.google.com/search?tbm=shop&q={q}"),
]


def supplier_links(part_number: str) -> list[dict]:
    if not part_number.strip():
        return []
    q = requests.utils.quote(part_number.strip())
    return [{"name": name, "url": url.format(q=q)} for name, url in SUPPLIERS]
