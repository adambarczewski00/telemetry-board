from __future__ import annotations

from collections.abc import Awaitable, Callable

from fastapi import APIRouter, Request
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest
from starlette.responses import Response

RequestHandler = Callable[[Request], Awaitable[Response]]

REQUESTS = Counter("api_requests_total", "Total HTTP requests", ["method", "path"])
# Histograms let us capture p95/p99 latencies per route template.
LATENCY = Histogram(
    "api_request_duration_seconds", "Request duration seconds", ["path"]
)
ERRORS = Counter(
    "api_errors_total",
    "HTTP responses with status >= 400",
    ["method", "path", "status"],
)

router = APIRouter()


@router.get("/metrics", include_in_schema=False)
def metrics() -> Response:
    """Expose the latest Prometheus sample set."""
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)


def _path_label(request: Request) -> str:
    """Prefer path templates (e.g. `/assets/{asset_id}`) to avoid cardinality blowups."""
    route = request.scope.get("route")
    path_template = getattr(route, "path_format", None) or getattr(route, "path", None)
    return path_template or request.url.path


async def metrics_middleware(request: Request, call_next: RequestHandler) -> Response:
    """Collect per-request counters, latency and error counts."""
    path_label = _path_label(request)
    REQUESTS.labels(method=request.method, path=path_label).inc()
    with LATENCY.labels(path=path_label).time():
        try:
            response = await call_next(request)
        except Exception:
            # Count unhandled exceptions as 500s
            ERRORS.labels(method=request.method, path=path_label, status="500").inc()
            raise
    # Count client/server error responses
    if response.status_code >= 400:
        ERRORS.labels(
            method=request.method,
            path=path_label,
            status=str(response.status_code),
        ).inc()
    return response
