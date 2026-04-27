"""
routing_service.py — Smart EV Routing with Precise Battery Math
================================================================
Algorithm summary:
  1. Fetch shortest route from OSRM.
  2. Predict total energy. If battery is sufficient → "No charging needed".
  3. Otherwise, scan stations ALONG the route (within 4 km detour).
  4. Build a greedy hop plan:
       - Start with current battery (or a `start_pct` override for Plan A simulation).
       - At each step, find the FURTHEST reachable station along the route
         that still leaves ≥10% on arrival.
       - At that station, charge only enough to reach the NEXT waypoint + 10% buffer.
       - Repeat until destination is reachable with ≥10%.
  5. For Plan A (Charge at Home):
       - Run the greedy hop plan from 100% to determine which stations to use.
       - Back-calculate: charge_at_home = cost_to_stop1 + 10.
       - Recompute arrival at stop1 = charge_at_home − cost_to_stop1  (always 10%).
  6. For Plan B (Nearest Fast Charger near home):
       - Find the nearest station to the start point.
       - Run the greedy hop plan from that station at 100%.
       - Prepend the local-charger hop (arrive with current battery − cost).
  7. Route display: always show the shortest direct route as the blue line.
     Numbered orange markers show recommended charging stops.
     "Reroute via these stations" bends the blue line through all of them.
"""

import os
import math
import requests
from fastapi import HTTPException

from backend.services.energy_model import energy_predictor, knn_finder, station_ranker
from backend.services.traffic_service import get_traffic_level
from backend.services.context_service import (
    get_temperature, get_elevation_change,
    prefetch_route_elevations, prefetch_route_temperatures,
)
from backend.models.schemas import RouteRequest, ChargingStop, RouteVariant, FallbackPlan

# ── Constants ────────────────────────────────────────────────────────────────
MIN_ARRIVE_PCT   = 10.0   # always arrive at any waypoint with at least this %
CHARGING_MIN     = 45.0   # assumed charging session length (minutes)
MAX_DETOUR_KM    = 2.5    # how far off-route a station can be and still count
MAX_HOPS         = 8      # safety cap on number of charging stops


# ── Geometry helpers ─────────────────────────────────────────────────────────

def _haversine_km(lat1, lon1, lat2, lon2) -> float:
    R = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2) ** 2 + (
        math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2) ** 2
    )
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def _cum_distances(coords):
    cum = [0.0]
    for i in range(1, len(coords)):
        cum.append(cum[-1] + _haversine_km(*coords[i - 1], *coords[i]))
    return cum


# ── OSRM helpers ─────────────────────────────────────────────────────────────

def _dominant_road_type(legs: list) -> int:
    counts = {0: 0, 1: 0, 2: 0}
    for leg in legs:
        for step in leg.get("steps", []):
            combined = (step.get("ref", "") + " " + step.get("name", "")).lower()
            if any(x in combined for x in ["nh", "sh", "national", "expressway", "highway"]):
                counts[0] += 1
            elif any(x in combined for x in ["main", "road", "avenue", "boulevard"]):
                counts[1] += 1
            else:
                counts[2] += 1
    return max(counts, key=counts.get)


def _parse_osrm_route(route: dict):
    distance_km = route["distance"] / 1000.0
    duration    = route["duration"]
    coords      = [(pt[1], pt[0]) for pt in route["geometry"]["coordinates"]]
    speed       = max(5.0, min((distance_km / (duration / 3600.0)) if duration > 0 else 30.0, 120.0))
    road_type   = _dominant_road_type(route.get("legs", []))
    return distance_km, coords, round(speed, 1), road_type


def _get_osrm_route(start_lat, start_lon, end_lat, end_lon, via_coords=None):
    """Fetch a single route, optionally via intermediate waypoints."""
    base = os.getenv("OSRM_BASE_URL", "http://router.project-osrm.org/route/v1/driving")
    if via_coords:
        via_str = ";".join(f"{lon},{lat}" for lat, lon in via_coords)
        coord_str = f"{start_lon},{start_lat};{via_str};{end_lon},{end_lat}"
    else:
        coord_str = f"{start_lon},{start_lat};{end_lon},{end_lat}"
    url = f"{base}/{coord_str}?overview=full&geometries=geojson&steps=true&annotations=true"

    for attempt in range(3):
        try:
            resp = requests.get(url, timeout=15)
            if resp.status_code == 200:
                data = resp.json()
                if data["code"] == "Ok":
                    return _parse_osrm_route(data["routes"][0])
        except requests.exceptions.RequestException:
            if attempt == 2:
                raise
    raise HTTPException(status_code=503, detail="Routing service unavailable")


def _get_osrm_alternatives(start_lat, start_lon, end_lat, end_lon):
    """Fetch up to 2 route alternatives (shortest + a different option)."""
    base = os.getenv("OSRM_BASE_URL", "http://router.project-osrm.org/route/v1/driving")
    coord_str = f"{start_lon},{start_lat};{end_lon},{end_lat}"
    url = (f"{base}/{coord_str}"
           f"?overview=full&geometries=geojson&steps=true&annotations=true&alternatives=true")
    for attempt in range(3):
        try:
            resp = requests.get(url, timeout=15)
            if resp.status_code == 200:
                data = resp.json()
                if data["code"] == "Ok":
                    return [_parse_osrm_route(r) for r in data["routes"][:2]]
        except requests.exceptions.RequestException:
            if attempt == 2:
                raise
    raise HTTPException(status_code=503, detail="Routing service unavailable")


# ── Energy helpers ────────────────────────────────────────────────────────────

def _predict_segment_energy(dist_km, speed=30.0, load=100.0, road_type=2,
                             mid_lat=None, mid_lon=None,
                             start_lat=None, start_lon=None,
                             end_lat=None, end_lon=None) -> float:
    """Predict kWh for a segment using real-world context wherever available."""
    traffic   = get_traffic_level(mid_lat, mid_lon) if mid_lat else 5.0
    temp      = get_temperature(mid_lat, mid_lon)   if mid_lat else 30.0
    elevation = (get_elevation_change(start_lat, start_lon, end_lat, end_lon)
                 if start_lat else 0.0)
    return energy_predictor.predict(
        distance_km=dist_km, speed=speed, traffic=traffic,
        elevation=elevation, temp=temp, load=load, road_type=road_type,
    )


def _pct_cost(dist_km, battery_cap, speed, load, road_type,
              mid_lat=None, mid_lon=None,
              start_lat=None, start_lon=None,
              end_lat=None, end_lon=None) -> float:
    """Convenience: percentage of battery consumed over `dist_km`."""
    kwh = _predict_segment_energy(
        dist_km, speed=speed, load=load, road_type=road_type,
        mid_lat=mid_lat, mid_lon=mid_lon,
        start_lat=start_lat, start_lon=start_lon,
        end_lat=end_lat, end_lon=end_lon,
    )
    return (kwh / battery_cap) * 100.0


# ── Station discovery ─────────────────────────────────────────────────────────

def _stations_along_route(route_coords, cum_dist, max_detour_km=MAX_DETOUR_KM):
    """
    Return all stations within max_detour_km of the route, tagged with:
      route_dist_km  — cumulative distance along the route to the nearest point
      detour_km      — straight-line distance from route to station
    Sorted by route_dist_km (forward progress order).
    """
    seen, results = set(), []
    step = max(1, len(route_coords) // 200)
    for i in range(0, len(route_coords), step):
        rlat, rlon = route_coords[i]
        for s in knn_finder.query(rlat, rlon, k=8, radius_km=max_detour_km):
            sid = (round(s["lat"], 4), round(s["lon"], 4))
            if sid in seen:
                continue
            seen.add(sid)
            detour = _haversine_km(rlat, rlon, s["lat"], s["lon"])
            results.append({
                **s,
                "route_idx":     i,
                "route_dist_km": round(cum_dist[i], 3),
                "detour_km":     round(detour, 3),
            })
    results.sort(key=lambda x: x["route_dist_km"])
    return results


def _find_all_route_stations_for_map(route_coords, cum_dist, battery_cap, battery_level_pct,
                                     avg_speed, load, road_type):
    """
    Return every station along the route annotated with reachability from current battery.
    Used by the frontend to render the grey/green map markers.
    """
    seen, results = set(), []
    step = max(1, len(route_coords) // 100)
    for i in range(0, len(route_coords), step):
        rlat, rlon = route_coords[i]
        for s in knn_finder.query(rlat, rlon, k=8, radius_km=3.0):
            sid = (round(s["lat"], 4), round(s["lon"], 4))
            if sid in seen:
                continue
            seen.add(sid)
            dist_to_station = cum_dist[i] + _haversine_km(rlat, rlon, s["lat"], s["lon"])
            cost_pct = _pct_cost(dist_to_station, battery_cap, avg_speed, load, road_type)
            arrive_pct = battery_level_pct - cost_pct

            if cost_pct > 100.0:
                continue  # unreachable even fully charged

            entry = {
                "lat":        s["lat"],
                "lon":        s["lon"],
                "name":       s.get("name", "EV Charging Station"),
                "arrive_pct": round(max(arrive_pct, 0.0), 1),
                "segment_km": round(dist_to_station, 2),
                "reachable":  arrive_pct >= 0,
            }
            if arrive_pct < 0:
                entry["charge_at_home"] = round(min(cost_pct + MIN_ARRIVE_PCT, 100.0), 1)
            results.append(entry)

    results.sort(key=lambda x: (not x["reachable"], -x["arrive_pct"]))
    return results


# ── Core Smart Hop Planner ────────────────────────────────────────────────────

def _smart_hop_plan(route_stations, route_coords, cum_dist,
                    battery_cap, starting_pct, avg_speed, load, road_type):
    """
    Greedy smart charging algorithm.

    Starting at the beginning of the route with `starting_pct` battery:
      - Find the FURTHEST station along the route we can still reach
        with ≥ MIN_ARRIVE_PCT remaining.
      - At that station, charge ONLY what's needed to reach the next
        waypoint (next station or destination) + MIN_ARRIVE_PCT buffer.
      - Repeat until the destination is reachable.

    Returns a list of hop dicts (empty if no charging needed).
    Each hop includes:
      pct_cost_to_here, arrive_pct, depart_pct, name, lat, lon,
      route_dist_km, detour_km
    """
    total_km     = cum_dist[-1]
    hops         = []
    current_pct  = starting_pct
    current_dist = 0.0   # progress along route (km)
    used         = set()

    for _ in range(MAX_HOPS):
        # ── Can we reach the destination from here? ──────────────────────────
        remaining_km = total_km - current_dist
        cost_to_dest = _pct_cost(remaining_km, battery_cap, avg_speed, load, road_type)
        if current_pct - cost_to_dest >= MIN_ARRIVE_PCT:
            break  # ✅ We can make it!

        # ── Find the best next station ────────────────────────────────────────
        # Candidates: stations ahead that we can reach with MIN_ARRIVE_PCT buffer
        best_candidate = None
        best_score     = float("inf")

        for stn in route_stations:
            sid = (round(stn["lat"], 4), round(stn["lon"], 4))
            if sid in used:
                continue
            if stn["route_dist_km"] <= current_dist + 0.5:
                continue  # must be strictly ahead (allow tiny overlap)

            # Total km from current position to this station
            seg_km   = (stn["route_dist_km"] - current_dist) + stn["detour_km"]
            cost_pct = _pct_cost(seg_km, battery_cap, avg_speed, load, road_type)
            arrive   = current_pct - cost_pct

            if arrive < MIN_ARRIVE_PCT:
                continue  # not reachable with safe buffer

            # Score: PRIMARY — minimise detour (stay on the road).
            # SECONDARY — among similar-detour stations, prefer the FURTHEST one
            # so we cover as much ground as possible per hop (fewer total stops).
            seg_km_from_current = stn["route_dist_km"] - current_dist
            score = stn["detour_km"] * 10.0 - seg_km_from_current * 0.2  # lower = better

            if score < best_score:
                best_score     = score
                best_candidate = (stn, seg_km, cost_pct, arrive)

        if best_candidate is None:
            break  # No reachable station — stuck (front-end will show warning)

        stn, seg_km, cost_pct, arrive_pct = best_candidate
        sid = (round(stn["lat"], 4), round(stn["lon"], 4))
        used.add(sid)

        # ── How much to charge at this station? ───────────────────────────────
        # Cost from this station to the destination (conservative estimate)
        dist_from_here_to_dest = total_km - stn["route_dist_km"]
        cost_to_dest_from_here = _pct_cost(
            dist_from_here_to_dest, battery_cap, avg_speed, load, road_type,
        )
        # Charge only what we need + 10% buffer. Never exceed 100%.
        smart_depart = round(min(cost_to_dest_from_here + MIN_ARRIVE_PCT, 100.0), 1)

        hops.append({
            "name":            stn.get("name", "EV Charging Station"),
            "lat":             stn["lat"],
            "lon":             stn["lon"],
            "route_dist_km":   round(stn["route_dist_km"], 2),
            "detour_km":       stn["detour_km"],
            "seg_km":          round(seg_km, 2),
            "pct_cost_to_here": round(cost_pct, 1),
            "arrive_pct":      round(arrive_pct, 1),
            "depart_pct":      smart_depart,
        })

        current_pct  = smart_depart
        current_dist = stn["route_dist_km"]

    return hops


# ── Option A / B Builders ────────────────────────────────────────────────────

def _build_plan_a(route_stations, route_coords, cum_dist,
                  battery_cap, current_battery_pct, avg_speed, load, road_type):
    """
    Option A — Charge at Home First.

    Run the hop planner from 100% to determine WHICH stations to use.
    Then back-calculate the minimum home charge needed:
        charge_at_home = cost_to_stop1 + MIN_ARRIVE_PCT   (always arrive with 10%)

    If the user's current battery is already enough → "No home charging needed".
    """
    # Discover the optimal set of stations starting from a full battery
    hops_from_full = _smart_hop_plan(
        route_stations, route_coords, cum_dist,
        battery_cap, 100.0, avg_speed, load, road_type,
    )

    total_km = cum_dist[-1]

    if not hops_from_full:
        # Even from 100% we go directly — calculate minimum needed for the whole trip
        cost_to_dest = _pct_cost(total_km, battery_cap, avg_speed, load, road_type,
                                 mid_lat=route_coords[len(route_coords)//2][0],
                                 mid_lon=route_coords[len(route_coords)//2][1])
        charge_needed = round(min(cost_to_dest + MIN_ARRIVE_PCT, 100.0), 1)
        if current_battery_pct >= charge_needed:
            return {
                "plan_type":         "home",
                "start_action":      f"✅ Current battery sufficient ({current_battery_pct:.0f}%) — drive directly",
                "charge_at_home_pct": current_battery_pct,
                "hops":              [],
            }
        return {
            "plan_type":         "home",
            "start_action":      f"Charge at home to {charge_needed:.0f}%",
            "charge_at_home_pct": charge_needed,
            "hops":              [],
        }

    # Back-calculate exact home charge for stop 1
    cost_to_stop1    = hops_from_full[0]["pct_cost_to_here"]
    charge_at_home   = round(min(cost_to_stop1 + MIN_ARRIVE_PCT, 100.0), 1)

    # Adjust hop 0 arrive_pct to reflect the real home charge, not 100%
    hops_from_full[0]["arrive_pct"] = round(charge_at_home - cost_to_stop1, 1)  # always 10%

    if current_battery_pct >= charge_at_home:
        start_action = f"✅ Leave now ({current_battery_pct:.0f}%) — enough to reach Stop 1"
        effective_home_pct = current_battery_pct
        hops_from_full[0]["arrive_pct"] = round(current_battery_pct - cost_to_stop1, 1)
    else:
        start_action = f"Charge at home to {charge_at_home:.0f}%"
        effective_home_pct = charge_at_home

    # Build rich hop list for the UI
    ui_hops = []
    for i, h in enumerate(hops_from_full):
        ui_hops.append({
            "stop_number":      i + 1,
            "name":             h["name"],
            "lat":              h["lat"],
            "lon":              h["lon"],
            "dist_from_start":  round(h["route_dist_km"], 1),
            "pct_cost_to_here": h["pct_cost_to_here"],
            "arrive_pct":       round(max(h["arrive_pct"], MIN_ARRIVE_PCT), 1),
            "depart_pct":       h["depart_pct"],
            "charging_time_min": CHARGING_MIN,
        })

    return {
        "plan_type":         "home",
        "start_action":      start_action,
        "charge_at_home_pct": effective_home_pct,
        "first_station_name": hops_from_full[0]["name"],
        "hops":              ui_hops,
    }


def _build_plan_b(route_stations, route_coords, cum_dist,
                  all_stations, battery_cap, current_battery_pct,
                  avg_speed, load, road_type):
    """
    Option B — Go to Nearest Fast Charger Near Home First.

    1. Calculate exact home charge needed to reach nearest station with ≥10%.
    2. From that station (smart charge amount), run the hop planner
       for the rest of the journey to find all needed charging stops.
    3. Return complete multi-stop plan including the home charge instruction.
    """
    if not all_stations:
        return None

    start_lat, start_lon = route_coords[0]

    # ── Find nearest station to home ─────────────────────────────────────────
    nearest = min(all_stations, key=lambda s: _haversine_km(start_lat, start_lon, s["lat"], s["lon"]))
    dist_to_local = _haversine_km(start_lat, start_lon, nearest["lat"], nearest["lon"])
    cost_to_local = _pct_cost(dist_to_local, battery_cap, avg_speed, load, road_type)

    # ── How much to charge at home so user arrives at local station with 10% ─
    min_home_charge = round(min(cost_to_local + MIN_ARRIVE_PCT, 100.0), 1)

    if current_battery_pct >= min_home_charge:
        # Already enough battery — no home charging needed
        charge_at_home_pct = current_battery_pct
        arrive_local       = round(current_battery_pct - cost_to_local, 1)
        need_home_charge   = False
        start_action = (
            f"✅ Current battery ({current_battery_pct:.0f}%) is enough — "
            f"go to nearest charger ({dist_to_local:.1f} km away)"
        )
    else:
        # User must charge at home first
        charge_at_home_pct = min_home_charge
        arrive_local       = round(min_home_charge - cost_to_local, 1)  # always = MIN_ARRIVE_PCT
        need_home_charge   = True
        start_action = (
            f"Charge at home to {min_home_charge:.0f}% "
            f"→ then go to nearest charger ({dist_to_local:.1f} km away)"
        )

    # ── Plan from local charger to destination ────────────────────────────────
    local_dist_on_route = dist_to_local
    remaining_stations = [s for s in route_stations
                          if s["route_dist_km"] > local_dist_on_route + 0.5]

    # Run hop planner from local charger at 100% (fast charge there)
    onward_hops = _smart_hop_plan(
        remaining_stations, route_coords, cum_dist,
        battery_cap, 100.0, avg_speed, load, road_type,
    )

    # ── Smart depart_pct for local station ───────────────────────────────────
    total_km = cum_dist[-1]
    if not onward_hops:
        # Can go directly to destination — charge only what's needed
        remaining_km  = max(total_km - local_dist_on_route, 0.1)
        cost_to_dest  = _pct_cost(remaining_km, battery_cap, avg_speed, load, road_type)
        depart_local  = round(min(cost_to_dest + MIN_ARRIVE_PCT, 100.0), 1)
    else:
        # Charge enough to reach first onward hop + 10% buffer
        next_pos_km   = onward_hops[0]["route_dist_km"]
        dist_to_next  = max(next_pos_km - local_dist_on_route, 0.1)
        cost_to_next  = _pct_cost(dist_to_next, battery_cap, avg_speed, load, road_type)
        depart_local  = round(min(cost_to_next + MIN_ARRIVE_PCT, 100.0), 1)

    local_hop = {
        "stop_number":       1,
        "name":              nearest.get("name", "Local Fast Charger"),
        "lat":               nearest["lat"],
        "lon":               nearest["lon"],
        "dist_from_start":   round(dist_to_local, 1),
        "pct_cost_to_here":  round(cost_to_local, 1),
        "arrive_pct":        max(round(arrive_local, 1), MIN_ARRIVE_PCT),
        "depart_pct":        depart_local,
        "will_run_out":      False,   # user pre-charges at home so no runout
        "charging_time_min": CHARGING_MIN,
        "home_charge_needed": need_home_charge,
        "home_charge_pct":    charge_at_home_pct,
    }

    ui_onward = []
    for i, h in enumerate(onward_hops):
        ui_onward.append({
            "stop_number":      i + 2,  # local charger is stop 1
            "name":             h["name"],
            "lat":              h["lat"],
            "lon":              h["lon"],
            "dist_from_start":  round(h["route_dist_km"], 1),
            "pct_cost_to_here": h["pct_cost_to_here"],
            "arrive_pct":       round(max(h["arrive_pct"], MIN_ARRIVE_PCT), 1),
            "depart_pct":       h["depart_pct"],
            "charging_time_min": CHARGING_MIN,
        })

    return {
        "plan_type":          "station",
        "start_action":       start_action,
        "charge_at_home_pct": charge_at_home_pct,
        "first_station_name": nearest.get("name", "Local Fast Charger"),
        "hops":               [local_hop] + ui_onward,
    }


# ── convert hops → ChargingStop objects for the map ──────────────────────────

def _hops_to_charging_stops(hops, avg_speed, stop_offset=0):
    """Convert plan hop dicts to ChargingStop Pydantic objects for the map markers."""
    stops = []
    for i, h in enumerate(hops):
        num   = i + 1 + stop_offset
        label = f"Stop {num} — Charge Here"
        drive_min = round((h.get("seg_km", h.get("dist_from_start", 0)) / max(avg_speed, 1)) * 60, 1)
        stops.append(ChargingStop(
            label=label,
            name=h["name"],
            lat=h["lat"],
            lon=h["lon"],
            arrive_pct=round(h.get("arrive_pct", MIN_ARRIVE_PCT), 1),
            depart_pct=h.get("depart_pct", 80.0),
            segment_km=round(h.get("seg_km", h.get("dist_from_start", 0)), 2),
            time_to_station_min=drive_min,
            charging_time_min=CHARGING_MIN,
            will_run_out=h.get("will_run_out", False),
            charge_to_pct=h.get("depart_pct"),
        ))
    return stops


# ── Variant builder ───────────────────────────────────────────────────────────

def _build_variant(label, distance_km, route_coords, osrm_speed, road_type, req, load):
    avg_speed = req.speed_kmh if (req.speed_kmh and req.speed_kmh > 0) else osrm_speed

    # Apply traffic factor for "fastest" label
    if label == "fastest":
        mid = route_coords[len(route_coords) // 2]
        traffic       = get_traffic_level(mid[0], mid[1])
        traffic_factor = max(0.6, 1.0 - (traffic / 10.0) * 0.4)
        avg_speed      = round(avg_speed * traffic_factor, 1)

    cum_dist  = _cum_distances(route_coords)
    total_km  = cum_dist[-1]
    mid_coord = route_coords[len(route_coords) // 2]

    # ── Overall energy prediction ─────────────────────────────────────────────
    predicted_energy = _predict_segment_energy(
        distance_km, speed=avg_speed, load=load, road_type=road_type,
        mid_lat=mid_coord[0], mid_lon=mid_coord[1],
        start_lat=route_coords[0][0],  start_lon=route_coords[0][1],
        end_lat=route_coords[-1][0],   end_lon=route_coords[-1][1],
    )
    current_energy  = req.battery_capacity_kwh * (req.battery_level_pct / 100.0)
    reserve_energy  = req.battery_capacity_kwh * (MIN_ARRIVE_PCT / 100.0)
    charging_needed = predicted_energy > (current_energy - reserve_energy)

    # ── Station discovery ─────────────────────────────────────────────────────
    stops, plan_a, plan_b, all_stations_map = [], None, None, []
    raw_hops = []  # always initialise so final-battery calc can reference it

    if req.stations:
        # Discover stations along the route for smart planning
        route_stns = _stations_along_route(route_coords, cum_dist)

        all_stations_map = _find_all_route_stations_for_map(
            route_coords, cum_dist,
            req.battery_capacity_kwh, req.battery_level_pct,
            avg_speed, load, road_type,
        )

        if charging_needed:
            # ── Direct route stops (greedy from current battery) ──────────────
            raw_hops = _smart_hop_plan(
                route_stns, route_coords, cum_dist,
                req.battery_capacity_kwh, req.battery_level_pct,
                avg_speed, load, road_type,
            )
            stops = _hops_to_charging_stops(raw_hops, avg_speed)

            # ── Option A: charge at home ──────────────────────────────────────
            plan_a_dict = _build_plan_a(
                route_stns, route_coords, cum_dist,
                req.battery_capacity_kwh, req.battery_level_pct,
                avg_speed, load, road_type,
            )
            plan_a = FallbackPlan(**{
                "plan_type":         plan_a_dict["plan_type"],
                "start_action":      plan_a_dict["start_action"],
                "charge_at_home_pct": plan_a_dict.get("charge_at_home_pct"),
                "first_station_name": plan_a_dict.get("first_station_name"),
                "hops":              plan_a_dict.get("hops", []),
            })

            # ── Option B: nearest fast charger first ──────────────────────────
            plan_b_dict = _build_plan_b(
                route_stns, route_coords, cum_dist,
                req.stations,
                req.battery_capacity_kwh, req.battery_level_pct,
                avg_speed, load, road_type,
            )
            if plan_b_dict:
                plan_b = FallbackPlan(**{
                    "plan_type":          plan_b_dict["plan_type"],
                    "start_action":       plan_b_dict["start_action"],
                    "charge_at_home_pct": plan_b_dict.get("charge_at_home_pct"),
                    "first_station_name": plan_b_dict.get("first_station_name"),
                    "hops":               plan_b_dict.get("hops", []),
                })

    # ── Timing ────────────────────────────────────────────────────────────────
    total_charging_min = sum(s.charging_time_min for s in stops)
    for s in stops:
        s.time_to_station_min = round((s.segment_km / max(avg_speed, 1)) * 60.0, 1)

    drive_min = round((distance_km / max(avg_speed, 1)) * 60.0, 1)
    total_min = round(drive_min + total_charging_min, 1)

    # ── Final battery at destination ──────────────────────────────────────────
    if stops:
        # Use the last stop's route position to find the true remaining km to dest
        last_route_dist = raw_hops[-1]["route_dist_km"] if raw_hops else 0.0
        last_seg_km     = max(total_km - last_route_dist, 0.1)
        last_mid        = route_coords[len(route_coords) * 3 // 4]
        final_pct       = stops[-1].depart_pct - _pct_cost(
            last_seg_km, req.battery_capacity_kwh, avg_speed, load, road_type,
            mid_lat=last_mid[0], mid_lon=last_mid[1],
        )
        # The smart hop planner charges enough to arrive with MIN_ARRIVE_PCT;
        # enforce the floor so rounding never dips below it.
        final_pct = max(round(final_pct, 1), MIN_ARRIVE_PCT)
    else:
        final_pct = round(
            ((current_energy - predicted_energy) / req.battery_capacity_kwh) * 100.0, 1
        )
        final_pct = max(final_pct, 0.0)

    no_station_on_route = charging_needed and not stops

    return RouteVariant(
        variant=label,
        distance_km=round(distance_km, 2),
        drive_duration_min=drive_min,
        total_duration_min=total_min,
        energy_consumption_kwh=round(predicted_energy, 4),
        avg_speed_kmh=avg_speed,
        route_coords=route_coords,
        charging_stops=stops,
        final_battery_pct=round(final_pct, 1),
        charging_needed=charging_needed,
        no_station_on_route=no_station_on_route,
        opt_a_home_charge_plan=plan_a,
        opt_b_nearest_station_plan=plan_b,
        alternative_stations=all_stations_map,
    )


# ── Public API ────────────────────────────────────────────────────────────────

def calculate_optimal_route(req: RouteRequest):
    try:
        load = getattr(req, "vehicle_load_kg", 100.0)

        # ── Via-station reroute ───────────────────────────────────────────────
        if req.via_stations and len(req.via_stations) > 0:
            via_coords = [
                (v["lat"], v["lon"]) for v in req.via_stations
                if "lat" in v and "lon" in v
            ]
            dk, rc, sp, rt = _get_osrm_route(
                req.start_lat, req.start_lon, req.end_lat, req.end_lon,
                via_coords=via_coords,
            )
            if req.stations:
                knn_finder.fit(req.stations)
                station_ranker.train()
            prefetch_route_elevations(rc)
            prefetch_route_temperatures(rc)
            v = _build_variant("fastest", dk, rc, sp, rt, req, load)
            return _variant_to_response(v, v, v)

        # ── Fresh route: fetch shortest + optional alternative ────────────────
        osrm_routes = _get_osrm_alternatives(
            req.start_lat, req.start_lon, req.end_lat, req.end_lon
        )

        if req.stations:
            knn_finder.fit(req.stations)
            station_ranker.train()

        d0, c0, s0, r0 = osrm_routes[0]
        prefetch_route_elevations(c0)
        prefetch_route_temperatures(c0)

        shortest = _build_variant("shortest", d0, c0, s0, r0, req, load)

        if len(osrm_routes) >= 2:
            d1, c1, s1, r1 = osrm_routes[1]
        else:
            d1, c1, s1, r1 = d0, c0, s0, r0

        fastest = _build_variant("fastest", d1, c1, s1, r1, req, load)

        # Active = whichever is actually faster in total time
        active = shortest if shortest.total_duration_min <= fastest.total_duration_min else fastest

        return _variant_to_response(active, shortest, fastest)

    except requests.exceptions.RequestException:
        raise HTTPException(status_code=503, detail="Could not connect to routing server")
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Routing error: {e}")
        import traceback; traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


def _variant_to_response(active: RouteVariant, shortest: RouteVariant, fastest: RouteVariant) -> dict:
    """Serialise a RouteVariant (and both alternatives) into the API response dict."""
    result = {
        "distance_km":            active.distance_km,
        "energy_consumption_kwh": active.energy_consumption_kwh,
        "charging_needed":        active.charging_needed,
        "route_coords":           active.route_coords,
        "charging_stops":         [s.dict() for s in active.charging_stops],
        "final_battery_pct":      active.final_battery_pct,
        "total_duration_min":     active.total_duration_min,
        "no_station_on_route":    active.no_station_on_route,
        "alternative_stations":   active.alternative_stations,
        "shortest_route":         shortest.dict(),
        "fastest_route":          fastest.dict() if fastest is not active else None,
    }
    if active.opt_a_home_charge_plan:
        result["opt_a_home_charge_plan"] = active.opt_a_home_charge_plan.dict()
    if active.opt_b_nearest_station_plan:
        result["opt_b_nearest_station_plan"] = active.opt_b_nearest_station_plan.dict()
    return result
