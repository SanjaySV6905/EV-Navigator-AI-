import os
import time
import requests
import math

OCM_API_KEY = os.getenv("OCM_API_KEY", "471b3533-7ffe-4f91-be73-9cb11f91a776")

CITY_COORDS = {
    "Bangalore": (12.9716, 77.5946),
    "Chennai":   (13.0827, 80.2707),
}

CITY_LAND_BOUNDS = {
    "Bangalore": {"lat_min": 12.7, "lat_max": 13.3, "lon_min": 77.3, "lon_max": 77.9},
    "Chennai":   {"lat_min": 12.8, "lat_max": 13.3, "lon_min": 80.0, "lon_max": 80.28},
}

_OCM_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "application/json",
    "X-API-Key": OCM_API_KEY,
}


def _is_on_land(city_name: str, lat: float, lon: float) -> bool:
    bounds = CITY_LAND_BOUNDS.get(city_name)
    if not bounds:
        return True
    return (bounds["lat_min"] <= lat <= bounds["lat_max"] and
            bounds["lon_min"] <= lon <= bounds["lon_max"])


_cache: dict = {}


def _fetch_from_ocm(city_name: str, lat: float, lon: float) -> list | None:
    """Try OCM API with retries. Returns list on success, None on failure."""
    params = {
        "output": "json", "countrycode": "IN",
        "latitude": lat, "longitude": lon,
        "distance": 30, "distanceunit": "KM",
        "maxresults": 500, "compact": "true", "verbose": "false",
        "key": OCM_API_KEY,
    }
    for attempt in range(3):
        try:
            resp = requests.get(
                "https://api.openchargemap.io/v3/poi/",
                params=params,
                headers=_OCM_HEADERS,
                timeout=20,
            )
            resp.raise_for_status()
            stations = []
            for poi in resp.json():
                try:
                    addr = poi.get("AddressInfo", {})
                    slat, slon = addr.get("Latitude"), addr.get("Longitude")
                    if slat is None or slon is None:
                        continue
                    if math.isnan(float(slat)) or math.isnan(float(slon)):
                        continue
                    if not _is_on_land(city_name, float(slat), float(slon)):
                        continue
                    stations.append({
                        "name": str(addr.get("Title") or "EV Charging Station"),
                        "lat":  round(float(slat), 6),
                        "lon":  round(float(slon), 6),
                    })
                except Exception:
                    continue
            print(f"✅ OCM: {len(stations)} stations in {city_name}")
            return stations
        except Exception as e:
            print(f"⚠️ OCM attempt {attempt + 1} failed for {city_name}: {e}")
            if attempt < 2:
                time.sleep(2 ** attempt)  # 1s, 2s backoff
    return None


def _fetch_from_overpass(city_name: str, lat: float, lon: float) -> list:
    """Fallback: fetch EV charging stations from OpenStreetMap via Overpass API."""
    print(f"🔄 Falling back to Overpass OSM for {city_name}...")
    query = (
        f"[out:json][timeout:30];"
        f"(node[\"amenity\"=\"charging_station\"](around:30000,{lat},{lon});"
        f"way[\"amenity\"=\"charging_station\"](around:30000,{lat},{lon}););"
        f"out center;"
    )
    try:
        resp = requests.get(
            "https://overpass-api.de/api/interpreter",
            params={"data": query},
            headers={"User-Agent": "EVRoutePlanner/1.0"},
            timeout=35,
        )
        resp.raise_for_status()
        stations = []
        for el in resp.json().get("elements", []):
            slat = el.get("lat") or (el.get("center") or {}).get("lat")
            slon = el.get("lon") or (el.get("center") or {}).get("lon")
            if not slat or not slon:
                continue
            if not _is_on_land(city_name, float(slat), float(slon)):
                continue
            name = (el.get("tags") or {}).get("name") or "Public Charger"
            stations.append({"name": name, "lat": round(float(slat), 6), "lon": round(float(slon), 6)})
        print(f"✅ Overpass: {len(stations)} stations in {city_name}")
        return stations
    except Exception as e:
        print(f"❌ Overpass also failed for {city_name}: {e}")
        return []


def fetch_charging_stations(city_name: str) -> list:
    if city_name in _cache:
        print(f"📦 Cached stations for {city_name} ({len(_cache[city_name])})")
        return _cache[city_name]

    coords = CITY_COORDS.get(city_name)
    if not coords:
        print(f"⚠️ Unknown city: {city_name}")
        return []

    lat, lon = coords

    # Try OCM first, fall back to Overpass OSM
    stations = _fetch_from_ocm(city_name, lat, lon)
    if not stations:
        stations = _fetch_from_overpass(city_name, lat, lon)

    if stations:
        _cache[city_name] = stations
    return stations
