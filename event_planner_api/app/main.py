"""
Main entrypoint for the Event Planner API.

This module assembles the FastAPI application, sets up logging and
includes versioned routers.  The ``create_app`` function builds
and configures the app, which is then instantiated at module
import time as ``app``.  Importing the app here makes it easy to
run with uvicorn or another ASGI server, e.g.::

    uvicorn event_planner_api.app.main:app --reload

The application title and version are provided via ``Settings`` from
``core.config``.
"""

from fastapi import FastAPI

from .core.config import settings
from .core.logging_config import setup_logging
from .api.v1.router import router as v1_router
from .core.db import init_db


def create_app() -> FastAPI:
    """Create and configure a FastAPI application.

    This function performs one‑time setup tasks such as configuring
    logging and including versioned API routers.  It returns a
    fully configured FastAPI instance ready to be served.

    Returns
    -------
    FastAPI
        A configured FastAPI application instance.
    """
    # Initialise logging before anything else so that imports below can
    # safely log messages.  The logging configuration reads the
    # desired log level from settings.
    setup_logging(settings.log_level)

    app = FastAPI(title=settings.project_name, version=settings.api_version)

    # Mount versioned routes under /api/v1.  Additional versions can be
    # added later by including their respective routers with a
    # different prefix.
    app.include_router(v1_router, prefix="/api/v1")

    # Register startup event to initialise the database and apply migrations.
    @app.on_event("startup")
    async def startup_event() -> None:
        # Apply migrations at startup.  This will create the database
        # file if it does not exist and ensure all tables are up to date.
        init_db()

    return app


# Create the application instance at import time so that tools such as
# uvicorn can discover it without calling create_app manually.
app = create_app()