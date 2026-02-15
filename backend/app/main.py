from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.routes import incidents, webhooks
# from app.core.config import settings (will create next)

app = FastAPI(
    title="AIREX",
    description="Autonomous Incident Resolution Engine Xecution",
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS (Restrict in production)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],  # Frontend URL
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Health Check
@app.get("/health")
async def health_check():
    return {"status": "ok", "service": "airex-backend"}

# Register Routes
# app.include_router(webhooks.router, prefix="/api/v1/webhooks", tags=["webhooks"])
# app.include_router(incidents.router, prefix="/api/v1/incidents", tags=["incidents"])
