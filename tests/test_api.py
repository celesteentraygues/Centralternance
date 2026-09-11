import json

import pytest
from fastapi.testclient import TestClient
from openai import OpenAIError

from app.config import MAX_PDF_BYTES, MSG_GENERATION, MSG_NON_PDF, MSG_PDF_ILLISIBLE
from app.main import app
from tests.conftest import FakeOpenAI, make_pdf

CS = {"rythme": "3 semaines / 1 semaine", "debut": "septembre 2027", "duree": "3 ans"}
CONTACT = {
    "nom": "Marie Martin",
    "entreprise": "Thales",
    "poste_contact": "Responsable RH",
    "poste_vise": "Ingénieur data",
}


@pytest.fixture
def fake_openai():
    fake = FakeOpenAI()
    app.state.openai = fake
    yield fake
    del app.state.openai


@pytest.fixture
def client(fake_openai):
    with TestClient(app) as c:
        yield c


def test_racine_sert_index_html(client):
    res = client.get("/")
    assert res.status_code == 200
    assert "Centralternance" in res.text


# --- /api/parse-cv ---


def test_parse_cv_ok(client):
    files = {"file": ("cv.pdf", make_pdf("Jean Dupont"), "application/pdf")}
    res = client.post("/api/parse-cv", files=files)
    assert res.status_code == 200
    assert "Jean Dupont" in res.json()["text"]
    assert res.json()["truncated"] is False


def test_parse_cv_refuse_extension_non_pdf(client):
    files = {"file": ("cv.txt", b"bonjour", "text/plain")}
    res = client.post("/api/parse-cv", files=files)
    assert res.status_code == 400
    assert res.json()["detail"] == MSG_NON_PDF


def test_parse_cv_refuse_pdf_illisible(client):
    files = {"file": ("cv.pdf", b"pas un pdf", "application/pdf")}
    res = client.post("/api/parse-cv", files=files)
    assert res.status_code == 400
    assert res.json()["detail"] == MSG_PDF_ILLISIBLE


def test_parse_cv_refuse_fichier_trop_gros(client):
    files = {"file": ("cv.pdf", b"%PDF" + b"0" * MAX_PDF_BYTES, "application/pdf")}
    res = client.post("/api/parse-cv", files=files)
    assert res.status_code == 413


# --- /api/generate ---


def test_generate_lettre_ok(client, fake_openai):
    fake_openai.content = "Madame, Monsieur, lettre."
    body = {"type": "lettre", "cv": "cv", "cs": CS, "offre": "offre"}
    res = client.post("/api/generate", json=body)
    assert res.status_code == 200
    assert res.json() == {"lettre": "Madame, Monsieur, lettre."}


def test_generate_spontane_ok(client, fake_openai):
    payload = {"objet": "Alternance", "email": "Bonjour Marie,", "linkedin": "Bonjour Marie,"}
    fake_openai.content = json.dumps(payload)
    body = {"type": "spontane", "cv": "cv", "cs": CS, "contact": CONTACT}
    res = client.post("/api/generate", json=body)
    assert res.status_code == 200
    assert res.json() == payload


def test_generate_champ_manquant_422(client):
    body = {"type": "lettre", "cv": "cv", "cs": CS}
    assert client.post("/api/generate", json=body).status_code == 422


def test_generate_champ_trop_long_422(client):
    body = {"type": "lettre", "cv": "cv", "cs": CS, "offre": "A" * 10_001}
    assert client.post("/api/generate", json=body).status_code == 422


def test_generate_erreur_openai_502(client, fake_openai):
    fake_openai.error = OpenAIError("boom")
    body = {"type": "lettre", "cv": "cv", "cs": CS, "offre": "offre"}
    res = client.post("/api/generate", json=body)
    assert res.status_code == 502
    assert res.json()["detail"] == MSG_GENERATION


# --- démarrage ---


def test_demarrage_sans_cle_echoue(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    with pytest.raises(RuntimeError, match="OPENAI_API_KEY"):
        with TestClient(app):
            pass
