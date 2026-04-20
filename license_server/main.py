"""FastAPI license server application."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from license_server import __version__
from license_server.database import close_connection, get_connection, run_migrations
from license_server.models import ErrorResponse, HealthResponse
from license_server.rate_limit import limiter
from license_server.routes.activate import router as activate_router
from license_server.routes.revoke import router as revoke_router
from license_server.routes.usage import router as usage_router
from license_server.routes.validate import router as validate_router
from license_server.routes.webhook import router as webhook_router

_db_path_override = None


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Run migrations on startup, close DB on shutdown."""
    conn = get_connection(_db_path_override)
    run_migrations(conn)
    yield
    close_connection()


app = FastAPI(
    title="AnchorMD License Server",
    version=__version__,
    lifespan=lifespan,
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.include_router(activate_router)
app.include_router(revoke_router)
app.include_router(validate_router)
app.include_router(usage_router)
app.include_router(webhook_router)


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Return structured errors instead of tracebacks."""
    return JSONResponse(
        status_code=500,
        content=ErrorResponse(
            error="internal_error", detail="An unexpected error occurred"
        ).model_dump(),
    )


@app.get("/v1/health", response_model=HealthResponse)
@limiter.limit("120/minute")
def health(request: Request) -> HealthResponse:
    """Health check with database statistics."""
    conn = get_connection(_db_path_override)
    try:
        total = conn.execute("SELECT COUNT(*) FROM licenses").fetchone()[0]
        active = conn.execute("SELECT COUNT(*) FROM licenses WHERE active = 1").fetchone()[0]
    except Exception:
        total = 0
        active = 0

    return HealthResponse(
        status="ok",
        version=__version__,
        total_licenses=total,
        active_licenses=active,
    )
