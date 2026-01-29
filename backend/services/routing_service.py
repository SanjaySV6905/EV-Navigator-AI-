import requests
from fastapi import HTTPException
from backend.services.energy_model import energy_predictor
from backend.models.schemas import RouteRequest

def calculate_optimal_route(req: RouteRequest):
    """
    Calculates route using OSRM Public API (Real-time, Fast, No Download).
    Then applies the AI Energy Model to the result.
    """
    print(f"🔄 Fetching route for {req.city} via OSRM...")

    # OSRM Public API Endpoint (uses OpenStreetMap Data)
    base_url = "http://router.project-osrm.org/route/v1/driving/"
    
    # Format: {longitude},{latitude};{longitude},{latitude}
    coordinates = f"{req.start_lon},{req.start_lat};{req.end_lon},{req.end_lat}"
    
    # Request full geometry (the line shape)
    url = f"{base_url}{coordinates}?overview=full&geometries=geojson"

    try:
        # 1. Get Route from OSRM
        response = requests.get(url, timeout=10)
        
        if response.status_code != 200:
            raise HTTPException(status_code=503, detail="Routing Service Unavailable")
        
        data = response.json()
        
        if data["code"] != "Ok":
            raise HTTPException(status_code=400, detail="No route found between these points")

        route = data["routes"][0]
        
        # 2. Extract Real Data
        distance_km = route["distance"] / 1000.0
        
        # OSRM gives [lon, lat], we need [lat, lon] for Leaflet map
        route_coords = [(pt[1], pt[0]) for pt in route["geometry"]["coordinates"]]

        # 3. AI Energy Prediction
        predicted_energy = energy_predictor.predict(distance_km)
        charging_needed = predicted_energy > req.battery_capacity_kwh

        print(f"✅ Route Found: {distance_km}km")

        return {
            "distance_km": round(distance_km, 2),
            "energy_consumption_kwh": round(predicted_energy, 4),
            "charging_needed": charging_needed,
            "route_coords": route_coords
        }

    except requests.exceptions.RequestException as e:
        print(f"❌ Network Error: {e}")
        raise HTTPException(status_code=503, detail="Could not connect to routing server")
    except Exception as e:
        print(f"❌ Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))