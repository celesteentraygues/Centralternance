from app.config import PROMPTS_DIR
from app.prompts import build_lettre_prompt, build_spontane_prompt
from app.schemas import GenerateRequest

CS = {"rythme": "3 semaines / 1 semaine", "debut": "septembre 2027", "duree": "3 ans"}
CONTACT = {
    "nom": "Marie Martin",
    "entreprise": "Thales",
    "poste_contact": "Responsable RH",
    "poste_vise": "Ingénieur data",
}


def _read(name: str) -> str:
    return (PROMPTS_DIR / f"{name}.md").read_text(encoding="utf-8").strip()


def _lettre(modele: str = "") -> GenerateRequest:
    return GenerateRequest(
        type="lettre", cv="CV DE TEST", cs=CS, modele=modele, offre="OFFRE DE TEST"
    )


def test_format_des_messages():
    messages = build_lettre_prompt(_lettre())
    assert [m["role"] for m in messages] == ["system", "user"]
    assert all(isinstance(m["content"], str) and m["content"] for m in messages)


def test_sans_modele_utilise_les_instructions_sans_modele_et_l_exemple():
    system, user = (m["content"] for m in build_lettre_prompt(_lettre()))
    assert _read("commun") in system
    assert _read("lettre_sans_modele") in system
    assert _read("lettre_avec_modele") not in system
    assert _read("lettre_exemple") in user


def test_avec_modele_utilise_les_instructions_avec_modele_et_le_modele():
    system, user = (m["content"] for m in build_lettre_prompt(_lettre("MON MODELE PERSO")))
    assert _read("lettre_avec_modele") in system
    assert _read("lettre_sans_modele") not in system
    assert "MON MODELE PERSO" in user
    assert _read("lettre_exemple") not in user


def test_modele_blanc_compte_comme_absent():
    system, _ = (m["content"] for m in build_lettre_prompt(_lettre("   \n")))
    assert _read("lettre_sans_modele") in system


def test_lettre_contient_cv_cs_et_offre():
    _, user = (m["content"] for m in build_lettre_prompt(_lettre()))
    assert "CV DE TEST" in user
    assert "OFFRE DE TEST" in user
    for valeur in CS.values():
        assert valeur in user


def test_spontane_contient_cv_cs_et_contact():
    req = GenerateRequest(type="spontane", cv="CV DE TEST", cs=CS, contact=CONTACT)
    system, user = (m["content"] for m in build_spontane_prompt(req))
    assert _read("commun") in system
    assert _read("spontane") in system
    assert "CV DE TEST" in user
    for valeur in CS.values():
        assert valeur in user
    for valeur in CONTACT.values():
        assert valeur in user
