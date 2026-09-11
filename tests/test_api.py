from fastapi.testclient import TestClient

from app.main import app


def test_racine_sert_index_html():
    with TestClient(app) as client:
        res = client.get("/")
    assert res.status_code == 200
    assert "Centralternance" in res.text
