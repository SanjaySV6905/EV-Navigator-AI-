import os
import pandas as pd
import numpy as np

try:
    from xgboost import XGBRegressor
    XGBOOST_AVAILABLE = True
except ImportError:
    from sklearn.ensemble import GradientBoostingRegressor
    XGBOOST_AVAILABLE = False

from sklearn.neighbors import BallTree
from sklearn.ensemble import GradientBoostingRegressor as StationRanker


class EnergyPredictor:
    def __init__(self):
        if XGBOOST_AVAILABLE:
            self.model = XGBRegressor(
                n_estimators=200, max_depth=5, learning_rate=0.05,
                subsample=0.8, colsample_bytree=0.8, random_state=42, verbosity=0
            )
        else:
            self.model = GradientBoostingRegressor(n_estimators=200, random_state=42)
        self.is_trained = False

    def train_mock_model(self):
        if self.is_trained:
            return
        backend = "XGBoost" if XGBOOST_AVAILABLE else "GradientBoosting (fallback)"
        print(f"⚡ Training Battery Predictor ({backend})...")
        np.random.seed(42)
        n = 3000
        distance  = np.random.uniform(0.5, 50, n)
        speed     = np.random.uniform(10, 120, n)
        # Realistic EV vehicle weights: lightweight(870) to heavy+5pax(2150)
        load      = np.random.uniform(800, 2200, n)
        traffic   = np.random.uniform(0, 10, n)
        elevation = np.random.uniform(-100, 100, n)
        temp      = np.random.uniform(10, 45, n)
        road_type = np.random.randint(0, 3, n)
        # Physics-based formula:
        # Base consumption ~0.15 kWh/km for a 1000kg EV
        # Each extra 100kg adds ~0.01 kWh/km (rolling resistance scales with mass)
        # load_factor normalises around 1000kg baseline
        load_factor = load / 1000.0
        energy = (
            distance * 0.15 * load_factor
            + traffic * 0.012 * distance
            + speed ** 2 * 0.00008
            + np.abs(elevation) * 0.006 * load_factor
            + np.abs(temp - 25) * 0.003
            + road_type * 0.05 * distance
            + np.random.normal(0, 0.05, n)
        )
        X = pd.DataFrame({
            'distance_km': distance, 'avg_speed': speed, 'vehicle_load_kg': load,
            'traffic_level': traffic, 'elevation_change': elevation,
            'temperature': temp, 'road_type': road_type
        })
        self.model.fit(X, energy)
        self.is_trained = True
        print(f"✅ Battery Predictor trained ({backend}).")

    def predict(self, distance_km: float, speed=30.0, traffic=None,
                elevation=0.0, temp=30.0, load=100.0, road_type=0,
                lat=None, lon=None) -> float:
        """
        Predict energy consumption for a segment.

        If lat/lon are provided, fetches real-time traffic from TomTom and
        uses it as traffic_level. Otherwise falls back to the passed traffic
        value (default 5.0 = moderate).
        """
        if not self.is_trained:
            self.train_mock_model()

        # Resolve traffic_level: real API > caller-supplied > neutral default
        if lat is not None and lon is not None:
            from backend.services.traffic_service import get_traffic_level
            traffic_level = get_traffic_level(lat, lon)
        elif traffic is not None:
            traffic_level = traffic
        else:
            traffic_level = 5.0

        df = pd.DataFrame([{
            'distance_km': distance_km, 'avg_speed': speed, 'vehicle_load_kg': load,
            'traffic_level': traffic_level, 'elevation_change': elevation,
            'temperature': temp, 'road_type': road_type
        }])
        return float(self.model.predict(df)[0])


class StationKNNFinder:
    def __init__(self):
        self.tree = None
        self.stations = []

    def fit(self, stations: list):
        if not stations:
            return
        self.stations = stations
        coords = np.radians([[s['lat'], s['lon']] for s in stations])
        self.tree = BallTree(coords, metric='haversine')

    def query(self, lat: float, lon: float, k: int = 5, radius_km: float = 5.0) -> list:
        if self.tree is None or not self.stations:
            return []
        point  = np.radians([[lat, lon]])
        radius = radius_km / 6371.0
        idxs   = self.tree.query_radius(point, r=radius)[0]
        if len(idxs) == 0:
            k_use = min(k, len(self.stations))
            _, idxs = self.tree.query(point, k=k_use)
            idxs = idxs[0]
        return [self.stations[i] for i in idxs]


class StationRankingModel:
    def __init__(self):
        self.model = StationRanker(n_estimators=100, random_state=42)
        self.is_trained = False

    def train(self):
        if self.is_trained:
            return
        print("🏆 Training Station Ranker...")
        np.random.seed(7)
        n = 2000
        detour_km      = np.random.uniform(0, 5, n)
        arrive_pct     = np.random.uniform(5, 80, n)
        dist_remaining = np.random.uniform(1, 40, n)
        route_position = np.random.uniform(0, 1, n)
        score = (
            detour_km * 2.0 - arrive_pct * 0.3 + dist_remaining * 0.1
            + route_position * 5.0 * (1 - arrive_pct / 100)
            + np.random.normal(0, 0.1, n)
        )
        X = pd.DataFrame({
            'detour_km': detour_km, 'arrive_pct': arrive_pct,
            'dist_remaining': dist_remaining, 'route_position': route_position
        })
        self.model.fit(X, score)
        self.is_trained = True
        print("✅ Station Ranker trained.")

    def score(self, detour_km, arrive_pct, dist_remaining, route_position) -> float:
        if not self.is_trained:
            self.train()
        df = pd.DataFrame([{
            'detour_km': detour_km, 'arrive_pct': arrive_pct,
            'dist_remaining': dist_remaining, 'route_position': route_position
        }])
        return float(self.model.predict(df)[0])


energy_predictor = EnergyPredictor()
knn_finder       = StationKNNFinder()
station_ranker   = StationRankingModel()
