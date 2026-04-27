from pydantic import BaseModel
from typing import List, Tuple, Optional

class RouteRequest(BaseModel):
    city: str
    start_lat: float
    start_lon: float
    end_lat: float
    end_lon: float
    battery_capacity_kwh: float
    battery_level_pct: float = 50.0
    vehicle_load_kg: float = 100.0
    speed_kmh: Optional[float] = None
    stations: Optional[List[dict]] = []
    via_stations: Optional[List[dict]] = None
    
class FallbackPlan(BaseModel):
    plan_type: str  # "home" or "station"
    start_action: str
    charge_at_home_pct: Optional[float] = None
    first_station_name: Optional[str] = None
    hops: List[dict] = []


class ChargingStop(BaseModel):
    label: str
    name: str
    lat: float
    lon: float
    arrive_pct: float
    depart_pct: float
    segment_km: float
    time_to_station_min: float = 0.0
    charging_time_min: float = 45.0
    will_run_out: bool = False
    charge_to_pct: Optional[float] = None

class RouteVariant(BaseModel):
    """One route option — either shortest-distance or fastest-time."""
    variant: str                              # "shortest" or "fastest"
    distance_km: float
    drive_duration_min: float                 # pure drive time (no charging)
    total_duration_min: float                 # drive + all charging stops
    energy_consumption_kwh: float
    avg_speed_kmh: float
    route_coords: List[Tuple[float, float]]
    charging_stops: List[ChargingStop] = []
    final_battery_pct: float = 0.0
    charging_needed: bool = False
    no_station_on_route: bool = False
    opt_a_home_charge_plan: Optional[FallbackPlan] = None
    opt_b_nearest_station_plan: Optional[FallbackPlan] = None
    alternative_stations: Optional[List[dict]] = []

class RouteResponse(BaseModel):
    # Active (default) route fields — kept for backward compat
    distance_km: float
    energy_consumption_kwh: float
    charging_needed: bool
    route_coords: List[Tuple[float, float]]
    charging_stops: List[ChargingStop] = []
    final_battery_pct: float = 0.0
    total_duration_min: float = 0.0
    no_station_on_route: bool = False
    opt_a_home_charge_plan: Optional[FallbackPlan] = None
    opt_b_nearest_station_plan: Optional[FallbackPlan] = None
    alternative_stations: Optional[List[dict]] = []
    # Both variants for the toggle
    shortest_route: Optional[RouteVariant] = None
    fastest_route: Optional[RouteVariant] = None

class StationResponse(BaseModel):
    name: str
    lat: float
    lon: float
