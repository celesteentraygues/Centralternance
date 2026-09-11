import json

import pytest
from openai import OpenAIError

from app.config import OPENAI_MAX_TOKENS, OPENAI_MODEL
from app.generator import GenerationError, generate_lettre, generate_spontane
from app.schemas import GenerateRequest, SpontaneResponse
from tests.conftest import FakeOpenAI

CS = {"rythme": "3 semaines / 1 semaine", "debut": "septembre 2027", "duree": "3 ans"}
CONTACT = {
    "nom": "Marie Martin",
    "entreprise": "Thales",
    "poste_contact": "Responsable RH",
    "poste_vise": "Ingénieur data",
}
LETTRE = GenerateRequest(type="lettre", cv="cv", cs=CS, offre="offre")
SPONTANE = GenerateRequest(type="spontane", cv="cv", cs=CS, contact=CONTACT)


def test_lettre_renvoie_le_texte_nettoye():
    client = FakeOpenAI(content="  Madame, Monsieur,\n\nLettre.  ")
    assert generate_lettre(client, LETTRE) == "Madame, Monsieur,\n\nLettre."


def test_lettre_utilise_les_bons_parametres():
    client = FakeOpenAI()
    generate_lettre(client, LETTRE)
    kwargs = client.calls[0]
    assert kwargs["model"] == OPENAI_MODEL
    assert kwargs["max_tokens"] == OPENAI_MAX_TOKENS
    assert kwargs["temperature"] == 0.7
    assert kwargs["timeout"] == 60
    assert "response_format" not in kwargs
    assert kwargs["messages"][0]["role"] == "system"


def test_spontane_parse_le_json():
    payload = {"objet": "Alternance data", "email": "Bonjour Marie,", "linkedin": "Bonjour Marie,"}
    client = FakeOpenAI(content=json.dumps(payload))
    result = generate_spontane(client, SPONTANE)
    assert isinstance(result, SpontaneResponse)
    assert result.objet == "Alternance data"
    assert client.calls[0]["response_format"] == {"type": "json_object"}


def test_spontane_json_invalide_leve_generation_error():
    client = FakeOpenAI(content="pas du json")
    with pytest.raises(GenerationError):
        generate_spontane(client, SPONTANE)


def test_spontane_json_incomplet_leve_generation_error():
    client = FakeOpenAI(content=json.dumps({"objet": "x"}))
    with pytest.raises(GenerationError):
        generate_spontane(client, SPONTANE)


def test_erreur_openai_leve_generation_error():
    client = FakeOpenAI(error=OpenAIError("quota dépassé"))
    with pytest.raises(GenerationError):
        generate_lettre(client, LETTRE)


def test_reponse_vide_leve_generation_error():
    client = FakeOpenAI(content=None)
    with pytest.raises(GenerationError):
        generate_lettre(client, LETTRE)
