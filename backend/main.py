"""
precise-rag backend — FastAPI entry point.
"""

import os
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.router_health import router as health_router
from app.api.v1.router_document import router as document_router
from app.api.v1.router_collection import router as collection_router
from app.api.v1.router_llm_provider import router as llm_provider_router
from app.api.v1.router_model_assignment import router as model_assignment_router
from app.core.config import get_settings, Settings
from app.core.database import startup_db, shutdown_db
from app.utils import simple_generate_unique_route_id


async def lifespan(app: FastAPI):
    """
    Application lifespan context manager.
    
    Handles startup and shutdown events including:
    - Upload directory creation
    - Database connection pool setup/teardown
    """
    # Store settings for access in other modules
    app.state.settings = get_settings()
    
    # Create upload directory on startup (not at import time)
    # This avoids crashes if the process lacks disk permissions
    upload_dir = Path(os.getenv("UPLOAD_DIR", "backend/uploads"))
    try:
        upload_dir.mkdir(parents=True, exist_ok=True)
        if app.state.settings.debug:
            print(f"[APP] Upload directory ready: {upload_dir.absolute()}")
    except Exception as e:
        print(f"[ERROR] Failed to create upload directory: {e}")
    
    # Startup database
    await startup_db(app)
    
    yield
    
    # Shutdown database
    await shutdown_db(app)


settings = get_settings()

app = FastAPI(
    title="precise-rag",
    description="High-Fidelity Legal RAG Engine API",
    version="0.1.0",
    lifespan=lifespan,
    openapi_url=settings.openapi_url,
    generate_unique_id_function=simple_generate_unique_route_id,
)


# ---------------------------------------------------------------------------
# CORS — allow frontend origin. SSE requires text/event-stream to pass through.
# ---------------------------------------------------------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Routers
# ---------------------------------------------------------------------------
app.include_router(health_router, prefix="/api/v1")
app.include_router(document_router, prefix="/api/v1")
app.include_router(collection_router, prefix="/api/v1")
app.include_router(llm_provider_router, prefix="/api/v1")
app.include_router(model_assignment_router, prefix="/api/v1")
