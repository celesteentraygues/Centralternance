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
    specifique = _load("lettre_avec_modele" if modele else "lettre_sans_modele")
    system = f"{_load('commun')}\n\n{specifique}"
    sections = [
        f"## CV du candidat\n{req.cv}",
        f"## Informations CentraleSupélec\n{_bloc_cs(req)}",
    ]
    if modele:
        sections.append(f"## Modèle de lettre écrit par le candidat\n{modele}")
    sections.append(f"## Offre d'alternance\n{(req.offre or '').strip()}")
    return _messages(system, sections)


def build_spontane_prompt(req: GenerateRequest) -> list[Message]:
    c = req.contact
    if c is None:  # garanti par le validateur de GenerateRequest
        raise ValueError("build_spontane_prompt requiert req.contact")
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
