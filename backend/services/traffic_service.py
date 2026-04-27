"""
Real-time traffic fetcher using TomTom Traffic Flow API (free tier).
Free tier: 2,500 requests/day — https://developer.tomtom.com/traffic-api/documentation/traffic-flow/flow-segment-data

How traffic_level is derived:
  - TomTom returns currentSpeed and freeFlowSpeed for a road segment.
  - congestion_ratio = 1 - (currentSpeed / freeFlowSpeed)
    0.0 = free flow  →  traffic_level 0
    1.0 = standstill →  traffic_level 10
  - We scale that linearly to 0–10 to match the XGBoost training range.
"""

import os
import time
import requests

# ── Config ────────────────────────────────────────────────────────────────────
# Set your TomTom API key here or via environment variable TOMTOM_API_KEY.
# Get a free key at: https://developer.tomtom.com/
TOMTOM_API_KEY = os.getenv("TOMTOM_API_KEY", "YOUR_TOMTOM_API_KEY_HERE")

TOMTOM_FLOW_URL = (
    "https://api.tomtom.com/traffic/services/4/flowSegmentData/absolute/10/json"
)

# ── In-memory cache (5-minute TTL per coordinate cell) ────────────────────────
_cache: dict = {}          # key: (lat_cell, lon_cell) → (traffic_level, timestamp)
_CACHE_TTL   = 300         # seconds
_GRID_SIZE   = 0.01        # ~1 km grid — nearby points share a cached value


def _cache_key(lat: float, lon: float) -> tuple:
    """Snap to a ~1 km grid cell to maximise cache hits."""
    return (round(lat / _GRID_SIZE) * _GRID_SIZE,
            round(lon / _GRID_SIZE) * _GRID_SIZE)


def get_traffic_level(lat: float, lon: float) -> float:
    """
    Return a traffic_level in [0, 10] for the road nearest to (lat, lon).
    Falls back to 5.0 (moderate) on any error or missing API key.
    """
    if TOMTOM_API_KEY == "YOUR_TOMTOM_API_KEY_HERE":
        return 5.0  # no key configured — use neutral default

    key = _cache_key(lat, lon)
    now = time.time()

    # Return cached value if still fresh
    if key in _cache:
        level, ts = _cache[key]
        if now - ts < _CACHE_TTL:
            return level

    try:
        resp = requests.get(
            TOMTOM_FLOW_URL,
            params={
                "key":   TOMTOM_API_KEY,
                "point": f"{lat},{lon}",
                "unit":  "KMPH",
            },
            timeout=5,
        )
        resp.raise_for_status()
        data = resp.json().get("flowSegmentData", {})

        current_speed   = float(data.get("currentSpeed",   0))
        free_flow_speed = float(data.get("freeFlowSpeed",  1))  # avoid div/0

        if free_flow_speed <= 0:
            return 5.0

        # congestion_ratio: 0 = free flow, 1 = standstill
        congestion = max(0.0, min(1.0, 1.0 - current_speed / free_flow_speed))
        traffic_level = round(congestion * 10.0, 2)

        _cache[key] = (traffic_level, now)
        print(f"🚦 Traffic at ({lat:.4f},{lon:.4f}): "
              f"{current_speed:.0f}/{free_flow_speed:.0f} km/h → level {traffic_level}")
        return traffic_level

    except Exception as e:
        print(f"⚠️  TomTom traffic fetch failed ({lat:.4f},{lon:.4f}): {e} — using 5.0")
        _cache[key] = (5.0, now)   # cache the fallback too, avoids hammering on errors
        return 5.0
