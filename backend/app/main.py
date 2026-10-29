"""FastAPI application entry point for the Phase 1 scaffold."""

from fastapi import FastAPI

from app.api.health import router as health_router

app = FastAPI(
    title="Munim-AI API",
    description="Hackathon prototype scaffold; no live Paytm integration.",
    version="0.1.0",
)

app.include_router(health_router)
