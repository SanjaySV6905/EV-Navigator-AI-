import asyncio
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

load_dotenv()  # loads TOMTOM_API_KEY from backend/.env

from backend.api import routes, charging
from backend.services.energy_model import energy_predictor, station_ranker

app = FastAPI(
    title="Last-Mile EV Routing System",
    description="EV Routing with XGBoost Energy Prediction and Open Charge Map"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
async def startup_event():
    energy_predictor.is_trained = False   # force retrain with updated formula
    energy_predictor.train_mock_model()
    station_ranker.train()
    loop = asyncio.get_running_loop()
    loop.run_in_executor(None, _prewarm_stations)

def _prewarm_stations():
    from backend.services.charger_service import fetch_charging_stations
    for city in ["Bangalore", "Chennai"]:
        fetch_charging_stations(city)

app.include_router(routes.router)
app.include_router(charging.router)

@app.get("/")
def health_check():
    return {"status": "active"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.app:app", host="0.0.0.0", port=8000, reload=True)
