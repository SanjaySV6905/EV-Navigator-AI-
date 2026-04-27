"""
Real-world context fetcher for energy prediction.

APIs used (all FREE, no key required):
  - Open-Meteo    : https://open-meteo.com/       → real temperature
  - OpenTopoData  : https://www.opentopodata.org/ → elevation (batched, SRTM 90m)
"""

import os
import time
import requests

# ── Cache config ──────────────────────────────────────────────────────────────
_temp_cache: dict = {}
_elev_cache: dict = {}
_CACHE_TTL  = 3600   # 1 hour
_TEMP_GRID  = 0.15   # ~15 km grid — entire Bangalore fits in ~4 cells, Chennai in ~3
_ELEV_GRID  = 0.01   # ~1 km grid for elevation


def _get_url(env_key: str, default: str) -> str:
    """Read URL at call-time so dotenv is already loaded."""
    return os.getenv(env_key, default)


def _grid_key(lat: float, lon: float, grid: float) -> tuple:
    return (round(lat / grid) * grid, round(lon / grid) * grid)


# ── Temperature ───────────────────────────────────────────────────────────────

def get_temperature(lat: float, lon: float) -> float:
    """Return cached temperature — only fetches if not already in cache."""
    key = _grid_key(lat, lon, _TEMP_GRID)
    now = time.time()
    if key in _temp_cache:
        temp, ts = _temp_cache[key]
        if now - ts < _CACHE_TTL:
            return temp
    # Not cached — fetch with retry
    url = _get_url("OPEN_METEO_URL", "https://api.open-meteo.com/v1/forecast")
    for attempt in range(3):
        try:
            resp = requests.get(
                url,
                params={"latitude": lat, "longitude": lon,
                        "current_weather": "true", "timezone": "auto"},
                timeout=5,
            )
            resp.raise_for_status()
            temp = float(resp.json()["current_weather"]["temperature"])
            _temp_cache[key] = (temp, now)
            print(f"🌡️  Temperature at ({lat:.3f},{lon:.3f}): {temp}°C")
            return temp
        except Exception as e:
            if attempt == 2:
                print(f"⚠️  Open-Meteo failed ({lat:.3f},{lon:.3f}) after 3 tries: {e} — using 30.0°C")
                _temp_cache[key] = (30.0, now)
                return 30.0
            time.sleep(0.5)
    return 30.0


def prefetch_route_temperatures(route_coords: list) -> None:
    """
    Pre-warm temperature cache using only 5 evenly-spaced points along the route.
    All subsequent get_temperature calls will hit the cache — zero extra HTTP requests.
    """
    if not route_coords:
        return
    n = len(route_coords)
    # Pick 5 evenly-spaced indices: start, 25%, 50%, 75%, end
    indices = sorted(set([0, n // 4, n // 2, 3 * n // 4, n - 1]))
    for i in indices:
        lat, lon = route_coords[i]
        key = _grid_key(lat, lon, _TEMP_GRID)
        now = time.time()
        if key not in _temp_cache or now - _temp_cache[key][1] >= _CACHE_TTL:
            get_temperature(lat, lon)  # fetches and caches


# ── Elevation (batched) ───────────────────────────────────────────────────────

def _get_elevation_cached(lat: float, lon: float) -> float | None:
    key = _grid_key(lat, lon, _ELEV_GRID)
    now = time.time()
    if key in _elev_cache:
        elev, ts = _elev_cache[key]
        if now - ts < _CACHE_TTL:
            return elev
    return None


def _batch_fetch_elevations(points: list) -> list:
    """Fetch elevations for multiple points in one API call (up to 100 per request)."""
    if not points:
        return []

    now     = time.time()
    results = [None] * len(points)
    to_fetch_indices = []
    to_fetch_coords  = []

    for i, (lat, lon) in enumerate(points):
        cached = _get_elevation_cached(lat, lon)
        if cached is not None:
            results[i] = cached
        else:
            to_fetch_indices.append(i)
            to_fetch_coords.append((lat, lon))

    if not to_fetch_coords:
        return [r if r is not None else 0.0 for r in results]

    url = _get_url("OPENTOPODATA_URL", "https://api.opentopodata.org/v1/srtm90m")
    fetched = {}
    for chunk_start in range(0, len(to_fetch_coords), 100):
        chunk = to_fetch_coords[chunk_start:chunk_start + 100]
        locations_str = "|".join(f"{lat},{lon}" for lat, lon in chunk)
        for attempt in range(3):
            try:
                resp = requests.get(url, params={"locations": locations_str}, timeout=10)
                resp.raise_for_status()
                for j, result in enumerate(resp.json().get("results", [])):
                    elev = float(result.get("elevation") or 0.0)
                    orig_lat, orig_lon = chunk[j]
                    key = _grid_key(orig_lat, orig_lon, _ELEV_GRID)
                    _elev_cache[key] = (elev, now)
                    fetched[(orig_lat, orig_lon)] = elev
                break  # success
            except Exception as e:
                if attempt == 2:
                    print(f"⚠️  OpenTopoData batch failed: {e} — using 0.0m for {len(chunk)} points")
                    for orig_lat, orig_lon in chunk:
                        key = _grid_key(orig_lat, orig_lon, _ELEV_GRID)
                        _elev_cache[key] = (0.0, now)
                        fetched[(orig_lat, orig_lon)] = 0.0
                else:
                    time.sleep(1.0)  # wait before retry on 429

    for i, (lat, lon) in zip(to_fetch_indices, to_fetch_coords):
        results[i] = fetched.get((lat, lon), 0.0)

    return [r if r is not None else 0.0 for r in results]


def get_elevation_change(start_lat: float, start_lon: float,
                         end_lat: float, end_lon: float) -> float:
    """Elevation change (end - start) in metres. Uses cache — no extra HTTP calls after prefetch."""
    elevs = _batch_fetch_elevations([(start_lat, start_lon), (end_lat, end_lon)])
    return round(elevs[1] - elevs[0], 1)


def prefetch_route_elevations(route_coords: list) -> None:
    """
    Pre-warm elevation cache for entire route in ONE API call.
    All subsequent get_elevation_change calls hit cache only.
    """
    step   = max(1, len(route_coords) // 80)
    points = list({_grid_key(lat, lon, _ELEV_GRID) for lat, lon in route_coords[::step]})
    now    = time.time()
    uncached = [p for p in points
                if p not in _elev_cache or now - _elev_cache[p][1] >= _CACHE_TTL]
    if uncached:
        _batch_fetch_elevations(uncached)
        print(f"🏔️  Prefetched elevation for {len(uncached)} grid cells in 1 API call")
