from fastapi.middleware.cors import CORSMiddleware

def setup_cors(app):
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # In production, specify ["http://localhost:5500"] etc.
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )