"""FastAPI application entry point for Tirithel."""

import logging
from contextlib import asynccontextmanager
from datetime import datetime

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from tirithel import __version__
from tirithel.api.routes import guidance, knowledge, profiles, sessions
from tirithel.config.database import init_db
from tirithel.config.settings import get_settings

settings = get_settings()

logging.basicConfig(
    level=getattr(logging, settings.log_level.upper()),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup and shutdown."""
    logging.info("Tirithel starting up - The One Who Watches Far...")
    await init_db()
    yield
    logging.info("Tirithel shutting down...")


app = FastAPI(
    title=settings.app_name,
    description=(
        "Tirithel - AI Support UI Learning Tool. "
        "Learns software navigation by observing remote support sessions "
        "and provides step-by-step guidance for future users."
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

# Register API routes
app.include_router(sessions.router, prefix=settings.api_prefix)
app.include_router(guidance.router, prefix=settings.api_prefix)
app.include_router(knowledge.router, prefix=settings.api_prefix)
app.include_router(profiles.router, prefix=settings.api_prefix)

# Serve static web UI
import os

static_dir = os.path.join(os.path.dirname(__file__), "static")
if os.path.isdir(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir), name="static")


@app.get(f"{settings.api_prefix}/health")
async def health_check():
    """System health check endpoint."""
    return {
        "status": "healthy",
        "service": "Tirithel",
        "version": __version__,
        "timestamp": datetime.utcnow().isoformat(),
    }


@app.get("/")
async def root():
    """Root endpoint - redirect to web UI or show API info."""
    return {
        "name": settings.app_name,
        "description": "AI Support UI Learning Tool - One Who Watches Far",
        "version": __version__,
        "docs": f"{settings.api_prefix}/docs",
        "health": f"{settings.api_prefix}/health",
        "ui": "/static/index.html",
    }
