# ML Models Used in pro-python

## Overview

All ML models live exclusively in the **backend**. The frontend has zero ML — it's pure UI/map logic.

---

## 1. EnergyPredictor — `backend/services/energy_model.py`

**Model:** XGBoost (`XGBRegressor`) with GradientBoostingRegressor as fallback

**Class:** `EnergyPredictor`

**Purpose:** Predicts how much battery energy (kWh) an EV will consume for a given road segment.

**Input Features:**
- `distance_km` — segment distance
- `avg_speed` — average speed
- `vehicle_load_kg` — vehicle load
- `traffic_level` — traffic congestion level
- `elevation_change` — elevation gain/loss
- `temperature` — ambient temperature
- `road_type` — type of road (0, 1, 2)

**Training:** Trained on 3,000 synthetically generated samples using a physics-inspired formula with added noise.

**Used in:**
- `energy_model.py` — defined and trained here
- `routing_service.py` — called via `energy_predictor.predict(...)` to estimate energy per segment
- `app.py` — pre-trained at server startup via `energy_predictor.train_mock_model()`

---

## 2. StationKNNFinder — `backend/services/energy_model.py`

**Model:** BallTree (from `sklearn.neighbors`) with Haversine metric

**Class:** `StationKNNFinder`

**Purpose:** Spatial nearest-neighbor search to find EV charging stations close to any point along the route. Uses Haversine distance so it works correctly on geographic coordinates.

**How it works:**
- `fit(stations)` — builds the BallTree index from station lat/lon coordinates
- `query(lat, lon, k, radius_km)` — returns stations within a radius, or falls back to k-nearest if none found in radius

**Used in:**
- `energy_model.py` — defined here
- `routing_service.py` — called via `knn_finder.query(...)` to find candidate charging stations near each route point
- `app.py` — the `knn_finder` instance is imported and used at request time (fitted per request with city stations)

---

## 3. StationRankingModel — `backend/services/energy_model.py`

**Model:** GradientBoostingRegressor (`sklearn.ensemble`)

**Class:** `StationRankingModel`

**Purpose:** Scores and ranks candidate charging stations to pick the best one at each stop. Lower score = better station choice.

**Input Features:**
- `detour_km` — how far off-route the station is
- `arrive_pct` — estimated battery % when arriving at the station
- `dist_remaining` — remaining distance to destination
- `route_position` — normalized position along the route (0.0 to 1.0)

**Training:** Trained on 2,000 synthetic samples with a scoring formula that penalizes large detours and low battery arrivals.

**Used in:**
- `energy_model.py` — defined and trained here
- `routing_service.py` — called via `station_ranker.score(...)` inside `_best_station()` and `_plan_charging_stops()` to rank candidates
- `app.py` — pre-trained at server startup via `station_ranker.train()`

---

## Summary Table

| Model | Algorithm | File | Role |
|---|---|---|---|
| `EnergyPredictor` | XGBoost / GradientBoosting | `energy_model.py` | Predict kWh consumption per segment |
| `StationKNNFinder` | BallTree (Haversine KNN) | `energy_model.py` | Find nearby charging stations spatially |
| `StationRankingModel` | GradientBoostingRegressor | `energy_model.py` | Rank & select the best charging stop |

---

## Frontend

No ML models are used in the frontend (`js/` files). The frontend handles:
- Map rendering (Leaflet.js)
- Address autocomplete (Nominatim API)
- Route drawing and UI updates
- Calling the backend REST API for all ML-powered predictions
