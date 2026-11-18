"""QRYVANTA FastAPI Application Entrypoint."""

from contextlib import asynccontextmanager
import logging
import sys
from pathlib import Path

# Ensure project root is on sys.path so `ml.*` and `data.*` resolve cleanly
PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config.settings import get_settings
from app.database.init_db import init_db
from app.routers import agents, analytics, auth, departments, incidents, intelligence, models, operations, portals, settings as settings_router, tickets

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger("qryvanta")


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    logger.info("QRYVANTA database initialized and ready.")
    yield


app_settings = get_settings()

app = FastAPI(
    title="QRYVANTA API",
    description="Intelligent Customer Support Operations & Ticket Resolution Platform",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=app_settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    logger.exception("Unhandled server exception on %s %s", request.method, request.url.path)
    return JSONResponse(
        status_code=500,
        content={"detail": "An unexpected internal server error occurred. Please contact support."},
    )


@app.get("/api/health", tags=["System"])
def health_check():
    return {
        "status": "ok",
        "application": app_settings.APP_NAME,
        "environment": app_settings.APP_ENV,
    }


app.include_router(auth.router)
app.include_router(tickets.router)
app.include_router(intelligence.router)
app.include_router(departments.router)
app.include_router(agents.router)
app.include_router(analytics.router)
app.include_router(models.router)
app.include_router(incidents.router)
app.include_router(operations.router)
app.include_router(portals.router)
app.include_router(settings_router.router)
