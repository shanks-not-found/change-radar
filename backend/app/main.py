"""
StackSignal FastAPI Application.

Entry point for the backend server:
- Lifespan initialization (DB schema & directories)
- CORS middleware configuration
- Router registration
- OpenAPI documentation
"""

import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.db import init_db
from app.routers import health, projects, scans, ask

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("stacksignal")

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Initializing StackSignal backend...")
    init_db()
    logger.info("SQLite Database initialized.")
    yield
    logger.info("Shutting down StackSignal backend.")

app = FastAPI(
    title="StackSignal API",
    description="AI-powered software change impact analysis tool mapping external changes to project code.",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS Middleware configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins or ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register Routers
app.include_router(health.router)
app.include_router(projects.router)
app.include_router(scans.router)
app.include_router(ask.router)

@app.get("/")
def root():
    return {
        "service": "StackSignal API",
        "version": "1.0.0",
        "docs_url": "/docs",
        "health_url": "/api/health",
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host=settings.host, port=settings.port, reload=True)
