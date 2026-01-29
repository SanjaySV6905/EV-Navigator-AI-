from pydantic import BaseModel
from typing import List, Tuple

class RouteRequest(BaseModel):
    city: str
    start_lat: float
    start_lon: float
    end_lat: float
    end_lon: float
    battery_capacity_kwh: float

class RouteResponse(BaseModel):
    distance_km: float
    energy_consumption_kwh: float
    charging_needed: bool
    route_coords: List[Tuple[float, float]] # List of (lat, lon) tuples

class StationResponse(BaseModel):
    name: str
    lat: float
    lon: float