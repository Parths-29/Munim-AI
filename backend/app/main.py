"""FastAPI application entry point for the Phase 1 scaffold."""

import asyncio
import logging

from fastapi import FastAPI
from starlette.concurrency import run_in_threadpool
from contextlib import asynccontextmanager
import os
from fastapi.middleware.cors import CORSMiddleware

from app.api.customers import router as customers_router
from app.api.actions import router as actions_router
from app.api.commands import router as commands_router
from app.api.events import router as events_router
from app.api.health import router as health_router
from app.api.insights import router as insights_router
from app.api.inventory import router as inventory_router
from app.api.invoices import router as invoices_router
from app.api.inward import router as inward_router
from app.api.ledger import router as ledger_router
from app.api.payments import router as payments_router
from app.api.reminders import router as reminders_router
from app.api.speech import router as speech_router
from app.api.suppliers import router as suppliers_router
from app.services.database import connect, initialize_database
from app.services.reminders import run_eligibility
from app.services.synthetic_data import seed_synthetic_transactions


async def _reminder_scheduler(minutes: float) -> None:
    """Optional periodic eligibility run. Safe across restarts: runs are idempotent per debt."""
    logger = logging.getLogger("munim.reminders")
    while True:
        try:
            await run_in_threadpool(run_eligibility)
        except Exception as error:  # keep the loop alive; never log customer data
            logger.warning("Reminder eligibility run failed (%s).", type(error).__name__)
        await asyncio.sleep(minutes * 60)


@asynccontextmanager
async def lifespan(_: FastAPI):
    initialize_database()
    with connect() as connection:
        seed_synthetic_transactions(connection)
    task = None
    try:
        minutes = float(os.environ.get("MUNIM_REMINDER_SCHEDULER_MINUTES", "0") or 0)
    except ValueError:
        minutes = 0
    if minutes > 0:
        task = asyncio.create_task(_reminder_scheduler(minutes))
    yield
    if task:
        task.cancel()

app = FastAPI(
    title="Munim-AI API",
    description="Synthetic hackathon prototype; no live Paytm integration.",
    version="0.5.0",
    lifespan=lifespan,
)

# Expo Web runs on a separate local origin. Native Android/iOS clients do not
# use CORS; allow only the local development origins by default.
cors_origins = [
    origin.strip()
    for origin in os.environ.get(
        "MUNIM_CORS_ORIGINS",
        "http://localhost:8081,http://127.0.0.1:8081",
    ).split(",")
    if origin.strip()
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type"],
)

app.include_router(health_router)
app.include_router(actions_router)
app.include_router(commands_router)
app.include_router(speech_router)
app.include_router(insights_router)
app.include_router(inventory_router)
app.include_router(payments_router)
app.include_router(customers_router)
app.include_router(events_router)
app.include_router(ledger_router)
app.include_router(suppliers_router)
app.include_router(invoices_router)
app.include_router(inward_router)
app.include_router(reminders_router)
