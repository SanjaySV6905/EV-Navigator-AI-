# EV Navigator AI

An AI-powered last-mile EV routing system that predicts battery consumption, finds optimal charging stops along your route, and gives smart pre-departure charging advice — all on an interactive map.

---

## How It Works

```
User Input
    ↓
Route Finder (OSRM / A*)
    ↓
Battery Predictor (XGBoost)
    ↓
Find Nearby Stations (KNN / BallTree)
    ↓
Rank Stations (ML Model)
    ↓
Final Route + Charging Plan
```

1. **Route Finder** — Uses OSRM (OpenStreetMap Routing Machine) with A* algorithm to find the optimal driving path.

2. **Battery Predictor (XGBoost)** — A trained XGBoost regression model predicts energy consumption (kWh) for each route segment based on distance, speed, traffic, elevation, temperature, and road type.

3. **Find Nearby Stations (KNN)** — A `BallTree` (haversine metric) from scikit-learn queries the nearest charging stations within a radius of each route point.

4. **Rank Stations (ML Model)** — A `GradientBoostingRegressor` scores each candidate station based on detour distance, arrival battery %, remaining distance, and route position.

5. **Charging Plan** — Outputs numbered charging stops (1, 2, 3...) with arrival/departure battery %, or pre-departure advice if no stations are on the route.

---

## Features

- Interactive map with real-time EV charging station data (Open Charge Map API)
- ML-powered battery consumption prediction per route segment
- Smart charging stop recommendations with numbered markers
- "Reroute via this station" — click any station to recalculate route through it
- Pre-departure advice: exact % to charge at home before leaving
- Shows all reachable stations along route as optional top-up stops
- Out-of-range stations shown greyed out with warning
- Address autocomplete using Nominatim API (accurate for Indian addresses)
- Supports Bangalore and Chennai

---

## Project Structure

```
pro-python/
├── backend/
│   ├── app.py                  # FastAPI app entry point
│   ├── requirements.txt
│   ├── api/
│   │   ├── routes.py           # POST /route endpoint
│   │   └── charging.py         # GET /charging-stations endpoint
│   ├── models/
│   │   └── schemas.py          # Pydantic request/response models
│   └── services/
│       ├── energy_model.py     # XGBoost predictor + KNN finder + ML ranker
│       ├── routing_service.py  # Core ML pipeline logic
│       └── charger_service.py  # Open Charge Map API integration
└── frontend/
    ├── index.html
    ├── style.css
    └── js/
        ├── main.js             # App init, city switching
        ├── map.js              # Leaflet map, click handlers
        ├── stations.js         # Station markers, charging stop rendering
        ├── routing.js          # Route calculation, rerouting
        ├── ui.js               # Sidebar summary panel
        └── autocomplete.js     # Address search (Nominatim)
```

---

## Tech Stack

| Layer | Technology |
|---|---|
| Frontend | HTML, Tailwind CSS, Leaflet.js |
| Backend | Python, FastAPI, Uvicorn |
| ML — Battery Prediction | XGBoost / GradientBoosting |
| ML — Station Search | scikit-learn BallTree (KNN, haversine) |
| ML — Station Ranking | GradientBoostingRegressor |
| Routing | OSRM (A* algorithm, OpenStreetMap) |
| Charging Station Data | Open Charge Map API |
| Address Search | Nominatim (OpenStreetMap) |
| Geocoding | Nominatim (OpenStreetMap) |

---

## Installation (Windows)

### Prerequisites
- Python 3.10+
- Node.js 18+
- Git

### Step 1 — Clone the repository

```bash
git clone https://github.com/SanjaySV6905/EV-Navigator-AI-.git
cd EV-Navigator-AI-/pro-python
```

### Step 2 — Set up Python virtual environment

```bash
python -m venv venv
venv\Scripts\activate
```

### Step 3 — Install backend dependencies

```bash
pip install -r backend/requirements.txt
```

### Step 4 — Add your Open Charge Map API key

Open `backend/services/charger_service.py` and replace:
```python
OCM_API_KEY = "your-api-key-here"
```
Get a free key at: https://openchargemap.org/site/develop/api

### Step 5 — Install frontend dependencies

```bash
cd frontend
npm install
cd ..
```

### Step 6 — Run the backend

Open **Terminal 1** in the `pro-python` folder:

```bash
venv\Scripts\activate
python -m uvicorn backend.app:app --host 0.0.0.0 --port 8000 --reload
```

Reference :

cd "C:\Users\ASUS\Documents\ev map project python\pro-python"
venv\Scripts\activate
python -m uvicorn backend.app:app --host 0.0.0.0 --port 8000 --reload

cd "C:\Users\ASUS\Documents\ev map project python\pro-python\frontend"
npx live-server --port=3000


You should see:
```
✅ Battery Predictor trained (XGBoost)
✅ Station Ranker trained
INFO: Uvicorn running on http://0.0.0.0:8000
```

### Step 7 — Run the frontend

Open **Terminal 2** in the `pro-python/frontend` folder:

```bash
npx live-server --port=3000
```

### Step 8 — Open in browser

```
http://127.0.0.1:3000
```

---

## API Endpoints

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/` | Health check |
| `GET` | `/charging-stations?city=Bangalore` | Get charging stations for a city |
| `POST` | `/route` | Calculate route with charging plan |

### POST /route — Request body

```json
{
  "city": "Bangalore",
  "start_lat": 12.9716,
  "start_lon": 77.5946,
  "end_lat": 12.9352,
  "end_lon": 77.6245,
  "battery_capacity_kwh": 40,
  "battery_level_pct": 50,
  "stations": [],
  "via_station_lat": null,
  "via_station_lon": null
}
```

---

## Environment

- OS: Windows 10/11
- Python: 3.10+
- Node.js: 18+
- Browser: Chrome / Edge (recommended)
