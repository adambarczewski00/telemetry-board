from __future__ import annotations

import os

from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from starlette.middleware.proxy_headers import ProxyHeadersMiddleware

from .metrics import metrics_middleware, router as metrics_router
from .api.assets import router as assets_router
from .api.prices import router as prices_router
from .api.alerts import router as alerts_router
from .ui import router as ui_router


def _flag(env_var: str, default: bool = False) -> bool:
    """Return True when an env var is explicitly set to a truthy value."""
    value = os.getenv(env_var)
    if value is None:
        return default
    return value.lower() in {"1", "true", "yes", "on"}


def create_app() -> FastAPI:
    """Build the FastAPI application with optional observability extras."""
    application = FastAPI(title="Crypto Telemetry Board")
    # Attach Prometheus instrumentation to every HTTP request.
    application.middleware("http")(metrics_middleware)
    # Respect X-Forwarded-* from Cloudflare/Cloudflared to generate correct URLs (https)
    application.add_middleware(ProxyHeadersMiddleware)

    # Ensure database schema exists when the service starts (dev/compose friendly).
    # In production you may prefer running Alembic migrations separately.
    @application.on_event("startup")
    def _ensure_db_schema() -> None:  # pragma: no cover - exercised in integration
        try:
            from .db import create_all

            create_all()
        except Exception:
            # Avoid crashing app on import-time issues; surface via logs instead.
            # The request will still fail if schema truly missing, but this best-effort
            # path helps local/compose environments without a migration step.
            pass

    if _flag("ENABLE_METRICS_ENDPOINT"):
        # Only expose /metrics when the deployment explicitly enables it.
        application.include_router(metrics_router)

    # Business endpoints
    application.include_router(assets_router)
    application.include_router(prices_router)
    application.include_router(alerts_router)
    # UI: static + server-rendered templates
    static_dir = Path(__file__).parent / "static"
    application.mount("/static", StaticFiles(directory=str(static_dir)), name="static")
    application.include_router(ui_router)

    @application.get("/health")
    def _health() -> dict[str, str]:
        """Tiny health probe used by Docker and uptime checks."""
        return {"status": "ok"}

    return application


app = create_app()
