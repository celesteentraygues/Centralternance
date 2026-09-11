import pytest
from pydantic import ValidationError

from app.config import MAX_CV_CHARS, MAX_OFFRE_CHARS
from app.schemas import BlocCS, Contact, GenerateRequest

CS = {"debut": "septembre 2027", "duree": "3 ans"}
CONTACT = {
    "nom": "Marie Martin",
    "entreprise": "Thales",
    "poste_contact": "Responsable RH",
    "poste_vise": "Ingénieur data",
}


def test_lettre_valide():
    req = GenerateRequest(type="lettre", cv="Mon CV", cs=CS, offre="Une offre")
    assert req.modele == ""
    assert req.contact is None


def test_spontane_valide():
    req = GenerateRequest(type="spontane", cv="Mon CV", cs=CS, contact=CONTACT)
    assert isinstance(req.contact, Contact)
    assert isinstance(req.cs, BlocCS)


def test_bloc_cs_ne_contient_que_debut_et_duree():
    assert set(BlocCS.model_fields) == {"debut", "duree"}


def test_lettre_sans_offre_est_refusee():
    with pytest.raises(ValidationError):
        GenerateRequest(type="lettre", cv="Mon CV", cs=CS)


def test_lettre_avec_offre_vide_est_refusee():
    with pytest.raises(ValidationError):
        GenerateRequest(type="lettre", cv="Mon CV", cs=CS, offre="   ")


def test_spontane_sans_contact_est_refuse():
    with pytest.raises(ValidationError):
        GenerateRequest(type="spontane", cv="Mon CV", cs=CS)


def test_type_inconnu_est_refuse():
    with pytest.raises(ValidationError):
        GenerateRequest(type="autre", cv="Mon CV", cs=CS, offre="x")


def test_cv_trop_long_est_refuse():
    with pytest.raises(ValidationError):
        GenerateRequest(type="lettre", cv="A" * (MAX_CV_CHARS + 1), cs=CS, offre="x")


def test_offre_trop_longue_est_refusee():
    with pytest.raises(ValidationError):
        GenerateRequest(type="lettre", cv="cv", cs=CS, offre="A" * (MAX_OFFRE_CHARS + 1))


def test_champ_contact_trop_long_est_refuse():
    contact = dict(CONTACT, nom="A" * 201)
    with pytest.raises(ValidationError):
        GenerateRequest(type="spontane", cv="cv", cs=CS, contact=contact)
