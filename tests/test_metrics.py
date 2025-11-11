from pytest import MonkeyPatch
from fastapi.testclient import TestClient
from app.main import create_app


def test_metrics_endpoint_available_when_enabled(monkeypatch: MonkeyPatch) -> None:
    """The `/metrics` endpoint should be opt-in and emit Prometheus text."""
    monkeypatch.setenv("ENABLE_METRICS_ENDPOINT", "true")
    with TestClient(create_app()) as client:
        response = client.get("/metrics")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/plain")
    assert "api_requests_total" in response.text


def test_metrics_endpoint_unavailable_when_disabled(monkeypatch: MonkeyPatch) -> None:
    """The `/metrics` endpoint should be opt-out and return 404 when disabled."""
    monkeypatch.delenv("ENABLE_METRICS_ENDPOINT", raising=False)
    with TestClient(create_app()) as client:
        response = client.get("/metrics")
    assert response.status_code == 404
