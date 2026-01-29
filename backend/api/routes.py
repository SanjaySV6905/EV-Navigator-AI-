from fastapi import APIRouter
from backend.models.schemas import RouteRequest, RouteResponse
from backend.services.routing_service import calculate_optimal_route

router = APIRouter()

@router.post("/route", response_model=RouteResponse)
def get_route(request: RouteRequest):
    return calculate_optimal_route(request)