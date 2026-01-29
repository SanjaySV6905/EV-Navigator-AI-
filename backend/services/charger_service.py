import osmnx as ox
import pandas as pd
import math
from backend.models.schemas import StationResponse

def fetch_charging_stations(city_name: str) -> list[StationResponse]:
    print(f"🔌 Fetching charging stations for {city_name}...")
    tags = {'amenity': 'charging_station'}
    
    try:
        # Fetch features from OSM
        gdf = ox.features_from_place(f"{city_name}, India", tags)
        
        if gdf.empty:
            return []

        stations = []
        for _, row in gdf.iterrows():
            lat, lon = None, None
            geom = row.geometry
            
            # Handle Points vs Polygons (Buildings)
            if geom.geom_type == 'Point':
                lat, lon = geom.y, geom.x
            elif geom.geom_type in ['Polygon', 'MultiPolygon']:
                centroid = geom.centroid
                lat, lon = centroid.y, centroid.x
            
            # Clean Name
            name = row.get('name', 'EV Charging Station')
            if isinstance(name, list): 
                name = name[0]
            if pd.isna(name): 
                name = "EV Charging Station"
            
            # Validate Coordinates
            if lat and lon and not (math.isnan(lat) or math.isnan(lon)):
                stations.append({
                    "name": str(name),
                    "lat": round(lat, 6),
                    "lon": round(lon, 6)
                })
                
        print(f"✅ Found {len(stations)} stations in {city_name}")
        return stations

    except Exception as e:
        print(f"❌ Error fetching stations: {e}")
        return []