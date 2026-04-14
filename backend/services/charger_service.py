import requests
import math

OCM_API_KEY = "471b3533-7ffe-4f91-be73-9cb11f91a776"

CITY_COORDS = {
    "Bangalore": (12.9716, 77.5946),
    "Chennai":   (13.0827, 80.2707),
}

_cache: dict = {}


def fetch_charging_stations(city_name: str) -> list:
    if city_name in _cache:
        print(f"📦 Cached stations for {city_name} ({len(_cache[city_name])})")
        return _cache[city_name]

    coords = CITY_COORDS.get(city_name)
    if not coords:
        print(f"⚠️ Unknown city: {city_name}")
        return []

    lat, lon = coords
    print(f"🔌 Fetching {city_name} from Open Charge Map...")

    try:
        resp = requests.get(
            "https://api.openchargemap.io/v3/poi/",
            params={
                "output": "json", "countrycode": "IN",
                "latitude": lat, "longitude": lon,
                "distance": 30, "distanceunit": "KM",
                "maxresults": 500, "compact": "true", "verbose": "false",
                "key": OCM_API_KEY,
            },
            headers={"X-API-Key": OCM_API_KEY},
            timeout=15
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
                stations.append({
                    "name": str(addr.get("Title") or "EV Charging Station"),
                    "lat":  round(float(slat), 6),
                    "lon":  round(float(slon), 6),
                })
            except Exception:
                continue

        print(f"✅ Found {len(stations)} stations in {city_name}")
        if stations:
            _cache[city_name] = stations
        return stations

    except Exception as e:
        print(f"❌ OCM error for {city_name}: {e}")
        return []
