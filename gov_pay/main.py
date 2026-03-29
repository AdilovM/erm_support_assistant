"""FastAPI application entry point for the Government Payment System."""

import logging
import sys
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

from gov_pay import __version__
from gov_pay.api.middleware.security import RateLimitMiddleware, SecurityHeadersMiddleware
from gov_pay.api.routes import entities, erm, payments, reports
from gov_pay.config.settings import get_settings

settings = get_settings()

logging.basicConfig(
    level=getattr(logging, settings.log_level.upper()),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)


def _validate_startup_config():
    """Validate critical configuration at startup. Fail fast on misconfiguration."""
    errors = []

    if not settings.jwt_secret:
        errors.append("APP_JWT_SECRET is required but not set.")

    if not settings.api_keys:
        errors.append("APP_API_KEYS is required but not set. Provide comma-separated API keys.")

    if settings.allowed_origins == "*":
        errors.append(
            "APP_ALLOWED_ORIGINS must not be '*' in production. "
            "Set explicit origins (e.g., 'https://admin.county.gov')."
        )

    if errors and not settings.debug:
        for err in errors:
            logging.critical("STARTUP CHECK FAILED: %s", err)
        sys.exit(1)
    elif errors:
        for err in errors:
            logging.warning("STARTUP WARNING (debug mode): %s", err)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup and shutdown."""
    _validate_startup_config()
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

# Security headers middleware (F6)
app.add_middleware(SecurityHeadersMiddleware)

# Rate limiting middleware (F7)
app.add_middleware(RateLimitMiddleware, payment_limit=30, general_limit=120, window_seconds=60)

# CORS middleware (F4 — explicit origins, no wildcard)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins.split(","),
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=[settings.api_key_header, "Content-Type", "Authorization"],
)

# Static files for UI
ui_dir = Path(__file__).parent / "ui"
app.mount("/static", StaticFiles(directory=str(ui_dir / "static")), name="static")

# Register API routes
app.include_router(payments.router, prefix=settings.api_prefix)
app.include_router(entities.router, prefix=settings.api_prefix)
app.include_router(reports.router, prefix=settings.api_prefix)
app.include_router(erm.router, prefix=settings.api_prefix)


@app.get(f"{settings.api_prefix}/health")
async def health_check():
    """System health check endpoint. Does not expose version info (F8)."""
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
    }


@app.get("/", response_class=HTMLResponse)
async def root():
    """Serve the county admin UI."""
    html_path = ui_dir / "templates" / "index.html"
    return HTMLResponse(content=html_path.read_text())
