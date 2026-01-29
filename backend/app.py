import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from backend.api import routes, charging
from backend.services.energy_model import energy_predictor

# Initialize App
app = FastAPI(
    title="Last-Mile EV Routing System",
    description="Full Stack EV Routing with AI Energy Prediction and OSMnx"
)

# Setup CORS (Allow frontend to connect)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Train AI Model on Startup
@app.on_event("startup")
async def startup_event():
    energy_predictor.train_mock_model()

# Include Routers
app.include_router(routes.router)
app.include_router(charging.router)

@app.get("/")
def health_check():
    return {"status": "active", "system": "Last-Mile EV Routing"}

if __name__ == "__main__":
    uvicorn.run("backend.app:app", host="0.0.0.0", port=8000, reload=True)
    