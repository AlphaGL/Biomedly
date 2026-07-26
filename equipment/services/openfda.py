"""openFDA device APIs + NIH AccessGUDID.

- Classification: official FDA device names, class (I/II/III), medical specialty.
  https://open.fda.gov/apis/device/classification/
- Recalls: https://open.fda.gov/apis/device/recall/
- AccessGUDID: look a device up by the UDI barcode printed on it.
  https://accessgudid.nlm.nih.gov/resources/developers/device_lookup_api
All free; openFDA key is optional (higher rate limits).
"""
from __future__ import annotations

import os

import requests

TIMEOUT = 12
FDA_BASE = "https://api.fda.gov/device"
GUDID_BASE = "https://accessgudid.nlm.nih.gov/api/v3"


def _fda_params(extra: dict) -> dict:
    params = dict(extra)
    key = os.getenv("OPENFDA_API_KEY")
    if key:
        params["api_key"] = key
    return params


def classify_device(query: str, limit: int = 5) -> list[dict]:
    """Official FDA classification records matching a device name."""
    try:
        r = requests.get(
            f"{FDA_BASE}/classification.json",
            params=_fda_params({"search": f'device_name:"{query}"', "limit": limit}),
            timeout=TIMEOUT,
        )
        if r.status_code == 404:  # openFDA returns 404 for "no matches"
            return []
        r.raise_for_status()
        results = r.json().get("results", [])
    except (requests.RequestException, ValueError):
        return []

    out = []
    for item in results:
        out.append({
            "device_name": item.get("device_name", ""),
            "device_class": item.get("device_class", ""),
            "medical_specialty": item.get("medical_specialty_description", ""),
            "definition": item.get("definition", ""),
            "regulation_number": item.get("regulation_number", ""),
        })
    return out


def recent_recalls(query: str, limit: int = 5) -> list[dict]:
    """Recent FDA recalls mentioning this device."""
    try:
        r = requests.get(
            f"{FDA_BASE}/recall.json",
            params=_fda_params({"search": f'product_description:"{query}"', "limit": limit}),
            timeout=TIMEOUT,
        )
        if r.status_code == 404:
            return []
        r.raise_for_status()
        results = r.json().get("results", [])
    except (requests.RequestException, ValueError):
        return []

    out = []
    for item in results:
        out.append({
            "product": (item.get("product_description") or "")[:200],
            "reason": (item.get("reason_for_recall") or "")[:300],
            "firm": item.get("recalling_firm", ""),
            "date": item.get("event_date_initiated", ""),
        })
    return out


def lookup_udi(udi: str) -> dict | None:
    """Identify a device from its UDI barcode via NIH AccessGUDID."""
    try:
        r = requests.get(
            f"{GUDID_BASE}/devices/lookup.json",
            params={"udi": udi},
            timeout=TIMEOUT,
        )
        if r.status_code != 200:
            return None
        data = r.json()
    except (requests.RequestException, ValueError):
        return None

    device = (data.get("gudid") or {}).get("device") or {}
    if not device:
        return None
    return {
        "brand_name": device.get("brandName", ""),
        "model": device.get("versionModelNumber", ""),
        "company": device.get("companyName", ""),
        "description": device.get("deviceDescription", ""),
        "catalog_number": device.get("catalogNumber", ""),
    }
