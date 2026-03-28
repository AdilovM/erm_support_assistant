"""FastAPI application entry point for the Government Payment System."""

import logging
from contextlib import asynccontextmanager
from datetime import datetime

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from gov_pay import __version__
from gov_pay.api.routes import entities, erm, payments, reports
from gov_pay.config.settings import get_settings

settings = get_settings()

logging.basicConfig(
    level=getattr(logging, settings.log_level.upper()),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup and shutdown."""
    logging.info("Government Payment System starting up...")
    yield
    logging.info("Government Payment System shutting down...")


app = FastAPI(
    title=settings.app_name,
    description=(
        "Payment processing system for federal, state, and county government entities. "
        "Supports credit card, ACH/eCheck, cash, and check payments with void and refund "
        "capabilities. Integrates with ERM systems including Tyler Tech Recorder."
    ),
    version=__version__,
    lifespan=lifespan,
    docs_url=f"{settings.api_prefix}/docs",
    redoc_url=f"{settings.api_prefix}/redoc",
    openapi_url=f"{settings.api_prefix}/openapi.json",
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins.split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routes
app.include_router(payments.router, prefix=settings.api_prefix)
app.include_router(entities.router, prefix=settings.api_prefix)
app.include_router(reports.router, prefix=settings.api_prefix)
app.include_router(erm.router, prefix=settings.api_prefix)


@app.get(f"{settings.api_prefix}/health")
async def health_check():
    """System health check endpoint."""
    return {
        "status": "healthy",
        "version": __version__,
        "timestamp": datetime.utcnow().isoformat(),
    }


@app.get("/")
async def root():
    """Root endpoint with API information."""
    return {
        "name": settings.app_name,
        "version": __version__,
        "docs": f"{settings.api_prefix}/docs",
        "health": f"{settings.api_prefix}/health",
    }
