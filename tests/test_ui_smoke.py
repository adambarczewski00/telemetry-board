from fastapi.testclient import TestClient
from app.main import create_app


def test_ui_overview_200() -> None:
    with TestClient(create_app()) as client:
        resp = client.get("/ui")
    assert resp.status_code == 200
    assert "Assets Overview" in resp.text


def test_ui_asset_detail_200() -> None:
    with TestClient(create_app()) as client:
        resp = client.get("/ui/assets/BTC")
    assert resp.status_code == 200
    assert "Asset: BTC" in resp.text


def test_ui_alerts_200() -> None:
    with TestClient(create_app()) as client:
        resp = client.get("/ui/alerts")
    assert resp.status_code == 200
    assert "Alerts" in resp.text

