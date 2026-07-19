import os
import json
from datetime import datetime
import re
import requests
import asyncio

def geocode_place(place_text: str) -> tuple[float, float] | None:
    """
    Returns (lat, lon) for a place string using Nominatim (OpenStreetMap).
    Uses a simple JSON cache to reduce repeated calls.
    """
    q = (place_text or "").strip()
    print(f"[GEOCODE START] q='{q}'", flush=True)

    if not q:
        return None

    # בדיקה בקאש
    cache = _load_json_dict(GEO_CACHE_FILE)
    if q in cache:
        try:
            lat = float(cache[q]["lat"])
            lon = float(cache[q]["lon"])
            print(f"[GEOCODE CACHE] '{q}' -> lat={lat}, lon={lon}", flush=True)
            return lat, lon
        except Exception as e:
            print(f"[GEOCODE CACHE ERROR] '{q}' -> {e}", flush=True)

    # קריאה ל־Nominatim
    url = "https://nominatim.openstreetmap.org/search"
    params = {"q": q, "format": "json", "limit": 1}
    headers = {"User-Agent": "TrempiBot/1.0 (edu project)"}

    try:
        resp = requests.get(url, params=params, headers=headers, timeout=8)
        resp.raise_for_status()
        results = resp.json()

        if not results:
            print(f"[GEOCODE API] '{q}' -> no results", flush=True)
            return None

        lat = float(results[0]["lat"])
        lon = float(results[0]["lon"])

        print(f"[GEOCODE API] '{q}' -> lat={lat}, lon={lon}", flush=True)

        # שמירה בקאש
        cache[q] = {"lat": lat, "lon": lon}
        _save_json_dict(GEO_CACHE_FILE, cache)

        return lat, lon

    except Exception as e:
        print(f"[GEOCODE API ERROR] '{q}' -> {e}", flush=True)
        return None

    url = "https://nominatim.openstreetmap.org/search"
    params = {"q": q, "format": "json", "limit": 1}
    headers = {"User-Agent": "TrempiBot/1.0 (edu project)"}

    try:
        resp = requests.get(url, params=params, headers=headers, timeout=8)
        resp.raise_for_status()
        results = resp.json()
        if not results:
            return None

        lat = float(results[0]["lat"])
        lon = float(results[0]["lon"])

        print(f"[GEOCODE] '{q}' -> lat={lat}, lon={lon}")


        cache[q] = {"lat": lat, "lon": lon}
        _save_json_dict(GEO_CACHE_FILE, cache)

        return lat, lon
    except Exception:
        return None

# ---- קוד בדיקה קצר בזמן אמת ----
if __name__ == "__main__":
    print("\n=== מריץ בדיקה מבודדת עבור ה-API של המפות ===")
    
    # בדיקה ראשונה: מקום מרכזי מאוד
    geocode_place("כיכר המדינה")
    
    # בדיקה שנייה: מקום בשפה חופשית
    geocode_place("אוניברסיטת בר אילן")