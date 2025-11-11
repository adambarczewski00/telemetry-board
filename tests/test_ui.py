from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import create_app


def _client() -> TestClient:
    app = create_app()
    return TestClient(app)


def test_ui_overview_renders() -> None:
    client = _client()
    r = client.get("/ui")
    assert r.status_code == 200
    assert "Assets Overview" in r.text


def test_ui_asset_detail_renders() -> None:
    client = _client()
    r = client.get("/ui/assets/BTC")
    assert r.status_code == 200
    # Symbol is interpolated server-side
    assert "Asset: BTC" in r.text


def test_ui_alerts_page_renders() -> None:
    client = _client()
    r = client.get("/ui/alerts")
    assert r.status_code == 200
    assert ">Alerts<" in r.text or "<h2>Alerts</h2>" in r.text


def test_static_readme_served() -> None:
    client = _client()
    r = client.get("/static/README.txt")
    # Static README might not be present in certain install modes, but in repo it exists.
    assert r.status_code == 200
    assert "Static assets" in r.text

