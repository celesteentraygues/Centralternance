from app.config import PROMPTS_DIR
from app.schemas import GenerateRequest

Message = dict[str, str]


def _load(name: str) -> str:
    return (PROMPTS_DIR / f"{name}.md").read_text(encoding="utf-8").strip()


def _bloc_cs(req: GenerateRequest) -> str:
    return (
        f"Rythme d'alternance : {req.cs.rythme}\n"
        f"Date de début : {req.cs.debut}\n"
        f"Durée du contrat : {req.cs.duree}"
    )


def _messages(system: str, user_sections: list[str]) -> list[Message]:
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": "\n\n".join(user_sections)},
    ]


def build_lettre_prompt(req: GenerateRequest) -> list[Message]:
    modele = req.modele.strip()
    if modele:
        specifique = _load("lettre_avec_modele")
        reference = f"## Modèle de lettre écrit par le candidat\n{modele}"
    else:
        specifique = _load("lettre_sans_modele")
        reference = (
            "## Lettre de référence (niveau de qualité attendu, ne pas recopier)\n"
            f"{_load('lettre_exemple')}"
        )
    system = f"{_load('commun')}\n\n{specifique}"
    return _messages(
        system,
        [
            f"## CV du candidat\n{req.cv}",
            f"## Informations CentraleSupélec\n{_bloc_cs(req)}",
            reference,
            f"## Offre d'alternance\n{(req.offre or '').strip()}",
        ],
    )


def build_spontane_prompt(req: GenerateRequest) -> list[Message]:
    c = req.contact
    assert c is not None  # garanti par le validateur de GenerateRequest
    system = f"{_load('commun')}\n\n{_load('spontane')}"
    return _messages(
        system,
        [
            f"## CV du candidat\n{req.cv}",
            f"## Informations CentraleSupélec\n{_bloc_cs(req)}",
            "## Contact visé\n"
            f"Nom : {c.nom}\n"
            f"Entreprise : {c.entreprise}\n"
            f"Poste du contact : {c.poste_contact}\n"
            f"Poste visé par le candidat : {c.poste_vise}",
        ],
    )
