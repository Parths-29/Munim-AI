"""FastAPI application entry point for the Phase 1 scaffold."""

from fastapi import FastAPI
from contextlib import asynccontextmanager

from app.api.customers import router as customers_router
from app.api.events import router as events_router
from app.api.health import router as health_router
from app.api.inventory import router as inventory_router
from app.api.ledger import router as ledger_router
from app.services.database import initialize_database


@asynccontextmanager
async def lifespan(_: FastAPI):
    initialize_database()
    yield

app = FastAPI(
    title="Munim-AI API",
    description="Synthetic hackathon prototype; no live Paytm integration.",
    version="0.3.0",
    lifespan=lifespan,
)

app.include_router(health_router)
app.include_router(inventory_router)
app.include_router(customers_router)
app.include_router(events_router)
app.include_router(ledger_router)
