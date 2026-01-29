from fastapi import APIRouter, Query
from typing import List
from backend.services.charger_service import fetch_charging_stations
from backend.models.schemas import StationResponse

router = APIRouter()

@router.get("/charging-stations", response_model=List[StationResponse])
def get_stations(city: str = Query(..., description="City name")):
    return fetch_charging_stations(city)