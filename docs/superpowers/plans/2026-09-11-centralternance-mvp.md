# Centralternance MVP — Plan d'implémentation

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Application web mono-page qui, à partir d'un CV PDF, génère une lettre de motivation (réponse à une offre) ou un trio objet/email/LinkedIn (candidature spontanée) via GPT-4o.

**Architecture:** Serveur FastAPI qui sert `static/` et expose deux routes (`/api/parse-cv`, `/api/generate`). Aucun stockage serveur : le navigateur garde le CV, le bloc CentraleSupélec et le modèle de lettre dans `sessionStorage` et renvoie tout le contexte à chaque génération. Les prompts sont des fichiers `.md` concaténés, modifiables sans toucher au code.

**Tech Stack:** Python 3.12+, FastAPI, uvicorn, pypdf, openai SDK, pydantic v2, python-dotenv, pytest, httpx. Frontend HTML/CSS/JS vanilla.

**Spec:** `docs/superpowers/specs/2026-09-11-centralternance-mvp-design.md`

## Global Constraints

- Modèle OpenAI : `gpt-4o`, `temperature=0.7`, `max_tokens=1200`, timeout 60 s.
- Limites : CV ≤ 15 000 caractères, offre ≤ 10 000, modèle ≤ 6 000, chaque champ contact ≤ 200, PDF ≤ 5 Mo.
- Le serveur ne stocke rien entre deux requêtes. Pas de base de données, pas d'écriture de fichiers.
- La clé OpenAI n'est lue que côté serveur, depuis `OPENAI_API_KEY`. Le serveur refuse de démarrer sans.
- Aucun appel réel à OpenAI dans les tests.
- Tout le texte visible par l'utilisateur est en français.
- Messages d'erreur exacts (spec §5) : `"Fichier non PDF"`, `"Impossible de lire ce PDF (scanné ou protégé). Essayez un export texte."`, `"Génération impossible, réessayez."`.
- Commits fréquents, messages en français, suffixe `Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>`.
- Toutes les commandes s'exécutent depuis `/Users/celeste/centralternance` avec le venv activé (`source .venv/bin/activate`).

Écarts assumés par rapport à la spec (mineurs, décidés au moment du plan) :
- Ajout de `app/config.py` pour centraliser les constantes (limites, modèle, chemins).
- Le PDF de test est généré par une fonction dans `tests/conftest.py` plutôt que commité en binaire.
- Les fichiers de prompts sont relus à chaque requête (fichiers minuscules) : l'auteur peut les éditer sans redémarrer le serveur.
- `extract_text` renvoie un `ParsedCV(text, truncated)` plutôt qu'un simple `str`, car la route doit renvoyer `truncated`.

---

## Structure des fichiers

| Fichier | Responsabilité |
|---|---|
| `app/config.py` | Constantes : limites de taille, modèle, tokens, timeout, chemins |
| `app/cv_parser.py` | `extract_text(bytes) -> ParsedCV`, `CVParseError` |
| `app/schemas.py` | Modèles Pydantic : `BlocCS`, `Contact`, `GenerateRequest`, `LettreResponse`, `SpontaneResponse`, `ParseCVResponse` |
| `app/prompts.py` | `build_lettre_prompt(req)`, `build_spontane_prompt(req)` → `list[dict]` messages OpenAI |
| `app/prompts/*.md` | Les cinq fichiers de prompts |
| `app/generator.py` | `generate_lettre(client, req) -> str`, `generate_spontane(client, req) -> SpontaneResponse`, `GenerationError` |
| `app/main.py` | App FastAPI, lifespan (client OpenAI), routes, montage de `static/` |
| `static/index.html` | Les 5 écrans |
| `static/style.css` | Styles écran + `@media print` |
| `static/app.js` | Session, navigation, appels API, copier, imprimer |
| `tests/conftest.py` | `make_pdf(text)`, `FakeOpenAI`, fixtures de requêtes |
| `tests/test_*.py` | Un fichier de test par module |
| `README.md` | Installation, lancement, déploiement, checklist manuelle |

---

### Task 1 : Squelette du projet et serveur minimal

**Files:**
- Create: `requirements.txt`, `.gitignore`, `.env.example`, `pytest.ini`, `app/__init__.py`, `app/config.py`, `app/main.py`, `static/index.html`, `tests/__init__.py`, `tests/test_api.py`

**Interfaces:**
- Produces: `app.config` (constantes ci-dessous), `app.main.app` (instance FastAPI servant `static/`).

- [ ] **Step 1 : Créer le venv et les dépendances**

`requirements.txt` :

```
fastapi>=0.115
uvicorn[standard]>=0.30
python-multipart>=0.0.9
pypdf>=4.3
openai>=1.40
python-dotenv>=1.0
pydantic>=2.7
pytest>=8.0
httpx>=0.27
```

```bash
cd /Users/celeste/centralternance
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

- [ ] **Step 2 : Fichiers de config du dépôt**

`.gitignore` :

```
.venv/
__pycache__/
*.pyc
.env
.pytest_cache/
.DS_Store
```

`.env.example` :

```
# Copiez ce fichier en .env et renseignez votre clé : https://platform.openai.com/api-keys
OPENAI_API_KEY=sk-...
```

`pytest.ini` :

```ini
[pytest]
testpaths = tests
```

- [ ] **Step 3 : Constantes**

`app/__init__.py` : fichier vide.

`app/config.py` :

```python
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
STATIC_DIR = BASE_DIR / "static"
PROMPTS_DIR = BASE_DIR / "app" / "prompts"

MAX_CV_CHARS = 15_000
MAX_OFFRE_CHARS = 10_000
MAX_MODELE_CHARS = 6_000
MAX_CONTACT_FIELD_CHARS = 200
MAX_PDF_BYTES = 5 * 1024 * 1024

OPENAI_MODEL = "gpt-4o"
OPENAI_TEMPERATURE = 0.7
OPENAI_MAX_TOKENS = 1200
OPENAI_TIMEOUT_SECONDS = 60

MSG_NON_PDF = "Fichier non PDF"
MSG_PDF_ILLISIBLE = "Impossible de lire ce PDF (scanné ou protégé). Essayez un export texte."
MSG_PDF_TROP_GROS = "Fichier trop volumineux (5 Mo maximum)"
MSG_GENERATION = "Génération impossible, réessayez."
```

- [ ] **Step 4 : Test du serveur statique (doit échouer)**

`tests/__init__.py` : vide.

`tests/test_api.py` :

```python
from fastapi.testclient import TestClient

from app.main import app


def test_racine_sert_index_html():
    with TestClient(app) as client:
        res = client.get("/")
    assert res.status_code == 200
    assert "Centralternance" in res.text
```

Run : `pytest tests/test_api.py -v`
Expected : FAIL avec `ModuleNotFoundError: No module named 'app.main'`

- [ ] **Step 5 : Serveur minimal + page placeholder**

`static/index.html` (placeholder, remplacé en Task 7) :

```html
<!doctype html>
<html lang="fr"><head><meta charset="utf-8"><title>Centralternance</title></head>
<body><h1>Centralternance</h1></body></html>
```

`app/main.py` :

```python
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.config import STATIC_DIR

app = FastAPI(title="Centralternance")

# Les routes API seront ajoutées avant ce montage (Task 6).
app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="static")
```

- [ ] **Step 6 : Vérifier**

Run : `pytest tests/test_api.py -v`
Expected : PASS

- [ ] **Step 7 : Commit**

```bash
git add requirements.txt .gitignore .env.example pytest.ini app static tests
git commit -m "chore: squelette FastAPI et configuration

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 2 : Extraction du texte du CV

**Files:**
- Create: `app/cv_parser.py`, `tests/conftest.py`, `tests/test_cv_parser.py`

**Interfaces:**
- Consumes: `app.config.MAX_CV_CHARS`, `app.config.MSG_PDF_ILLISIBLE`
- Produces: `app.cv_parser.ParsedCV(text: str, truncated: bool)` (NamedTuple), `app.cv_parser.extract_text(pdf_bytes: bytes) -> ParsedCV`, `app.cv_parser.CVParseError(Exception)`. `tests.conftest.make_pdf(text: str) -> bytes`.

- [ ] **Step 1 : Fixture de génération de PDF**

`tests/conftest.py` :

```python
"""Fixtures partagées. make_pdf construit un PDF minimal valide contenant `text`
(ASCII uniquement, sans parenthèses) sur une page, police Helvetica."""


def make_pdf(text: str) -> bytes:
    stream = f"BT /F1 12 Tf 50 750 Td ({text}) Tj ET".encode("latin-1")
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] "
        b"/Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>",
        b"<< /Length " + str(len(stream)).encode() + b" >>\nstream\n" + stream + b"\nendstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    out = bytearray(b"%PDF-1.4\n")
    offsets = []
    for i, obj in enumerate(objects, start=1):
        offsets.append(len(out))
        out += f"{i} 0 obj\n".encode() + obj + b"\nendobj\n"
    xref_pos = len(out)
    out += f"xref\n0 {len(objects) + 1}\n".encode()
    out += b"0000000000 65535 f \n"
    for off in offsets:
        out += f"{off:010d} 00000 n \n".encode()
    out += (
        f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\n"
        f"startxref\n{xref_pos}\n%%EOF\n"
    ).encode()
    return bytes(out)
```

- [ ] **Step 2 : Tests (doivent échouer)**

`tests/test_cv_parser.py` :

```python
import pytest

from app.config import MAX_CV_CHARS
from app.cv_parser import CVParseError, extract_text
from tests.conftest import make_pdf


def test_extrait_le_texte_dun_pdf():
    parsed = extract_text(make_pdf("Jean Dupont ingenieur CentraleSupelec"))
    assert "Jean Dupont" in parsed.text
    assert "CentraleSupelec" in parsed.text
    assert parsed.truncated is False


def test_refuse_un_fichier_non_pdf():
    with pytest.raises(CVParseError):
        extract_text(b"ceci n'est pas un pdf")


def test_refuse_un_pdf_sans_texte():
    with pytest.raises(CVParseError):
        extract_text(make_pdf(""))


def test_tronque_un_cv_trop_long():
    parsed = extract_text(make_pdf("A" * (MAX_CV_CHARS + 500)))
    assert parsed.truncated is True
    assert len(parsed.text) == MAX_CV_CHARS


def test_normalise_les_espaces():
    parsed = extract_text(make_pdf("Jean    Dupont"))
    assert "Jean Dupont" in parsed.text
```

Run : `pytest tests/test_cv_parser.py -v`
Expected : FAIL avec `ModuleNotFoundError: No module named 'app.cv_parser'`

- [ ] **Step 3 : Implémentation**

`app/cv_parser.py` :

```python
import re
from io import BytesIO
from typing import NamedTuple

from pypdf import PdfReader

from app.config import MAX_CV_CHARS, MSG_PDF_ILLISIBLE


class CVParseError(Exception):
    """Le fichier n'est pas un PDF lisible ou ne contient aucun texte."""


class ParsedCV(NamedTuple):
    text: str
    truncated: bool


def _normalize(text: str) -> str:
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n\s*\n+", "\n\n", text)
    return text.strip()


def extract_text(pdf_bytes: bytes) -> ParsedCV:
    try:
        reader = PdfReader(BytesIO(pdf_bytes))
        if reader.is_encrypted:
            reader.decrypt("")
        pages = [page.extract_text() or "" for page in reader.pages]
    except Exception as exc:  # pypdf lève une demi-douzaine de types différents
        raise CVParseError(MSG_PDF_ILLISIBLE) from exc

    text = _normalize("\n".join(pages))
    if not text:
        raise CVParseError(MSG_PDF_ILLISIBLE)

    truncated = len(text) > MAX_CV_CHARS
    return ParsedCV(text=text[:MAX_CV_CHARS], truncated=truncated)
```

- [ ] **Step 4 : Vérifier**

Run : `pytest tests/test_cv_parser.py -v`
Expected : 5 PASS. Si `test_refuse_un_fichier_non_pdf` échoue parce que pypdf ne lève pas d'exception mais renvoie zéro page, le test passe quand même via la branche « texte vide » — c'est le comportement voulu.

- [ ] **Step 5 : Commit**

```bash
git add app/cv_parser.py tests/conftest.py tests/test_cv_parser.py
git commit -m "feat: extraction du texte du CV PDF

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 3 : Schémas de requête et de réponse

**Files:**
- Create: `app/schemas.py`, `tests/test_schemas.py`

**Interfaces:**
- Consumes: constantes `MAX_*` de `app.config`
- Produces:
  - `BlocCS(rythme: str, debut: str, duree: str)`
  - `Contact(nom: str, entreprise: str, poste_contact: str, poste_vise: str)`
  - `GenerateRequest(type: Literal["lettre","spontane"], cv: str, cs: BlocCS, modele: str = "", offre: str | None = None, contact: Contact | None = None)` — validateur : `offre` non vide si `type == "lettre"`, `contact` présent si `type == "spontane"`
  - `LettreResponse(lettre: str)`, `SpontaneResponse(objet: str, email: str, linkedin: str)`, `ParseCVResponse(text: str, truncated: bool)`

- [ ] **Step 1 : Tests (doivent échouer)**

`tests/test_schemas.py` :

```python
import pytest
from pydantic import ValidationError

from app.config import MAX_CV_CHARS, MAX_OFFRE_CHARS
from app.schemas import BlocCS, Contact, GenerateRequest

CS = {"rythme": "3 semaines / 1 semaine", "debut": "septembre 2027", "duree": "3 ans"}
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
```

Run : `pytest tests/test_schemas.py -v`
Expected : FAIL avec `ModuleNotFoundError: No module named 'app.schemas'`

- [ ] **Step 2 : Implémentation**

`app/schemas.py` :

```python
from typing import Literal

from pydantic import BaseModel, Field, model_validator

from app.config import (
    MAX_CONTACT_FIELD_CHARS,
    MAX_CV_CHARS,
    MAX_MODELE_CHARS,
    MAX_OFFRE_CHARS,
)


class BlocCS(BaseModel):
    rythme: str = Field(max_length=MAX_CONTACT_FIELD_CHARS)
    debut: str = Field(max_length=MAX_CONTACT_FIELD_CHARS)
    duree: str = Field(max_length=MAX_CONTACT_FIELD_CHARS)


class Contact(BaseModel):
    nom: str = Field(min_length=1, max_length=MAX_CONTACT_FIELD_CHARS)
    entreprise: str = Field(min_length=1, max_length=MAX_CONTACT_FIELD_CHARS)
    poste_contact: str = Field(min_length=1, max_length=MAX_CONTACT_FIELD_CHARS)
    poste_vise: str = Field(min_length=1, max_length=MAX_CONTACT_FIELD_CHARS)


class GenerateRequest(BaseModel):
    type: Literal["lettre", "spontane"]
    cv: str = Field(min_length=1, max_length=MAX_CV_CHARS)
    cs: BlocCS
    modele: str = Field(default="", max_length=MAX_MODELE_CHARS)
    offre: str | None = Field(default=None, max_length=MAX_OFFRE_CHARS)
    contact: Contact | None = None

    @model_validator(mode="after")
    def _champs_selon_type(self) -> "GenerateRequest":
        if self.type == "lettre" and not (self.offre and self.offre.strip()):
            raise ValueError("Le champ 'offre' est requis pour type='lettre'.")
        if self.type == "spontane" and self.contact is None:
            raise ValueError("Le champ 'contact' est requis pour type='spontane'.")
        return self


class LettreResponse(BaseModel):
    lettre: str


class SpontaneResponse(BaseModel):
    objet: str
    email: str
    linkedin: str


class ParseCVResponse(BaseModel):
    text: str
    truncated: bool
```

- [ ] **Step 3 : Vérifier**

Run : `pytest tests/test_schemas.py -v`
Expected : 9 PASS

- [ ] **Step 4 : Commit**

```bash
git add app/schemas.py tests/test_schemas.py
git commit -m "feat: schémas Pydantic des requêtes et réponses

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 4 : Fichiers de prompts et assemblage

**Files:**
- Create: `app/prompts/commun.md`, `app/prompts/lettre_sans_modele.md`, `app/prompts/lettre_avec_modele.md`, `app/prompts/lettre_exemple.md`, `app/prompts/spontane.md`, `app/prompts.py`, `tests/test_prompts.py`

**Interfaces:**
- Consumes: `app.schemas.GenerateRequest`, `app.config.PROMPTS_DIR`
- Produces: `app.prompts.build_lettre_prompt(req: GenerateRequest) -> list[dict[str, str]]`, `app.prompts.build_spontane_prompt(req: GenerateRequest) -> list[dict[str, str]]`. Chaque liste = `[{"role": "system", "content": ...}, {"role": "user", "content": ...}]`. Les fichiers `.md` sont relus à chaque appel.

Note : `app/prompts.py` (module) et `app/prompts/` (dossier) coexistent. Python importe `app.prompts` comme le **module** `prompts.py` car le dossier n'a pas de `__init__.py`. Ne pas en ajouter un.

- [ ] **Step 1 : Fichiers de prompts (première version, à remplacer par l'auteur)**

`app/prompts/commun.md` :

```markdown
Tu es un assistant qui rédige des candidatures d'alternance pour des élèves-ingénieurs de CentraleSupélec. Tu écris en français, à la première personne, comme si tu étais le candidat.

Règles absolues :
- N'invente jamais une expérience, une compétence, un diplôme ou un chiffre absent du CV.
- Ne paraphrase pas le CV : sélectionne 2 ou 3 éléments réellement pertinents pour le poste et explique en quoi ils comptent.
- Mentionne toujours le rythme d'alternance, la date de début et la durée fournis dans les informations CentraleSupélec.
- Ton professionnel, direct, concret. Phrases courtes. Pas d'emphase.
- Formulations interdites : « je suis passionné », « je me permets de », « n'hésitez pas », « dynamique et motivé », « force de proposition », « au sein de votre prestigieuse entreprise ».
- Pas de titre, pas de commentaire, pas de texte avant ou après le contenu demandé.
- Si une information nécessaire manque (nom du destinataire, intitulé exact du poste), utilise une formule neutre plutôt qu'un crochet ou un placeholder.
```

`app/prompts/lettre_sans_modele.md` :

```markdown
Rédige une lettre de motivation pour l'offre d'alternance fournie.

Structure imposée, 4 paragraphes, 250 à 350 mots au total :
1. Accroche : le poste visé, l'entreprise, et une raison précise (tirée de l'offre) pour laquelle ce poste intéresse le candidat. Pas de « je vous écris pour ».
2. Pourquoi moi : 2 ou 3 expériences ou projets du CV qui répondent directement aux attentes de l'offre, avec ce qu'ils ont produit.
3. Cadre de l'alternance : formation à CentraleSupélec, rythme, date de début, durée. Une ou deux phrases.
4. Conclusion : disponibilité pour un échange, formule de politesse sobre (« Je vous prie d'agréer, Madame, Monsieur, mes salutations distinguées. »).

Commence par « Madame, Monsieur, » sauf si l'offre donne le nom d'un destinataire.

La lettre de référence fournie indique le niveau de qualité, la densité et le ton attendus. Ne recopie ni ses phrases ni ses exemples : elle concerne un autre candidat et une autre entreprise.
```

`app/prompts/lettre_avec_modele.md` :

```markdown
Rédige une lettre de motivation pour l'offre d'alternance fournie, en t'appuyant sur le modèle de lettre écrit par le candidat.

Ce que tu conserves du modèle :
- sa structure (ordre et nombre de paragraphes) ;
- son ton et ses tournures de phrases caractéristiques ;
- sa longueur approximative.

Ce que tu remplaces :
- tout ce qui concerne une autre entreprise, un autre poste ou une autre offre ;
- les exemples du CV qui ne sont pas pertinents pour cette offre, par ceux qui le sont.

Ce que tu ajoutes si le modèle ne le contient pas :
- le rythme d'alternance, la date de début et la durée fournis dans les informations CentraleSupélec.

Le résultat doit se lire comme une lettre écrite par le candidat lui-même pour cette offre précise, pas comme un modèle recyclé.
```

`app/prompts/lettre_exemple.md` :

```markdown
Madame, Monsieur,

Votre offre d'alternance en ingénierie logicielle embarquée a retenu mon attention pour une raison précise : vous cherchez quelqu'un capable de faire le lien entre le développement bas niveau et la validation sur banc d'essai, ce qui correspond exactement à ce que j'ai fait cette année.

Lors de mon stage chez un équipementier automobile, j'ai développé en C un module de diagnostic pour un calculateur de freinage, puis conçu les scénarios de test qui ont permis de détecter deux défauts avant la mise en production. En parallèle, mon projet de deuxième année à CentraleSupélec m'a amené à concevoir un système de mesure temps réel sur STM32, de la carte au traitement des données en Python. Ces deux expériences m'ont appris à livrer du code qui tourne sur du matériel réel, avec des contraintes de temps et de fiabilité.

J'intègre en septembre 2027 le cursus ingénieur par apprentissage de CentraleSupélec, sur un rythme de trois semaines en entreprise pour une semaine à l'école, pour une durée de trois ans. Ce rythme permet une présence longue et continue sur vos projets.

Je serais heureux d'échanger avec vous sur la manière dont je pourrais contribuer à votre équipe. Je vous prie d'agréer, Madame, Monsieur, mes salutations distinguées.
```

`app/prompts/spontane.md` :

```markdown
Le candidat souhaite contacter une personne dans une entreprise pour une candidature spontanée en alternance. Rédige trois contenus et renvoie-les dans un objet JSON avec exactement ces clés : "objet", "email", "linkedin".

"objet" : l'objet de l'email. Moins de 70 caractères. Contient « alternance » et le poste visé. Pas de majuscules abusives, pas de point d'exclamation.

"email" : 120 à 180 mots.
- Salutation : « Bonjour Prénom, » (prénom seul, extrait du nom du contact).
- Une phrase qui explique pourquoi cette personne précisément (son poste, son équipe).
- Le poste visé et une ou deux compétences du CV qui le justifient.
- Le cadre : alternance CentraleSupélec, rythme, date de début, durée.
- Une demande claire et unique : un échange de quinze minutes.
- Signature : « Bien cordialement, » suivi du nom du candidat tel qu'il apparaît dans le CV.

"linkedin" : 60 à 90 mots, moins de 600 caractères. Même contenu que l'email mais condensé, ton plus direct, sans objet ni signature. Commence par « Bonjour Prénom, ». Se termine par la même demande d'échange.

Vouvoiement dans les deux cas. Aucun emoji. Ne mets pas de texte en dehors du JSON.
```

- [ ] **Step 2 : Tests (doivent échouer)**

`tests/test_prompts.py` :

```python
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
```

Run : `pytest tests/test_prompts.py -v`
Expected : FAIL avec `ImportError: cannot import name 'build_lettre_prompt'` (ou `ModuleNotFoundError`)

- [ ] **Step 3 : Implémentation**

`app/prompts.py` :

```python
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
```

- [ ] **Step 4 : Vérifier**

Run : `pytest tests/test_prompts.py -v`
Expected : 6 PASS

- [ ] **Step 5 : Commit**

```bash
git add app/prompts app/prompts.py tests/test_prompts.py
git commit -m "feat: fichiers de prompts et assemblage des messages

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 5 : Appel OpenAI

**Files:**
- Create: `app/generator.py`, `tests/test_generator.py`
- Modify: `tests/conftest.py` (ajout de `FakeOpenAI`)

**Interfaces:**
- Consumes: `build_lettre_prompt`, `build_spontane_prompt`, `SpontaneResponse`, `GenerateRequest`, constantes `OPENAI_*` et `MSG_GENERATION`
- Produces: `app.generator.GenerationError(Exception)`, `app.generator.generate_lettre(client, req) -> str`, `app.generator.generate_spontane(client, req) -> SpontaneResponse`. `client` est n'importe quel objet exposant `client.chat.completions.create(**kwargs)` (instance `openai.OpenAI` en prod, `FakeOpenAI` en test). `tests.conftest.FakeOpenAI(content: str | None = None, error: Exception | None = None)` enregistre chaque appel dans `.calls`.

- [ ] **Step 1 : Faux client OpenAI**

Ajouter à la fin de `tests/conftest.py` :

```python
from types import SimpleNamespace


class FakeOpenAI:
    """Imite openai.OpenAI : client.chat.completions.create(**kwargs).
    Renvoie `content`, ou lève `error` si fourni. Enregistre les kwargs dans .calls."""

    def __init__(self, content: str | None = "réponse de test", error: Exception | None = None):
        self.content = content
        self.error = error
        self.calls: list[dict] = []
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))

    def _create(self, **kwargs):
        self.calls.append(kwargs)
        if self.error is not None:
            raise self.error
        message = SimpleNamespace(content=self.content)
        return SimpleNamespace(choices=[SimpleNamespace(message=message)])
```

- [ ] **Step 2 : Tests (doivent échouer)**

`tests/test_generator.py` :

```python
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
```

Run : `pytest tests/test_generator.py -v`
Expected : FAIL avec `ModuleNotFoundError: No module named 'app.generator'`

- [ ] **Step 3 : Implémentation**

`app/generator.py` :

```python
from typing import Any, Protocol

from openai import OpenAIError
from pydantic import ValidationError

from app.config import (
    MSG_GENERATION,
    OPENAI_MAX_TOKENS,
    OPENAI_MODEL,
    OPENAI_TEMPERATURE,
    OPENAI_TIMEOUT_SECONDS,
)
from app.prompts import Message, build_lettre_prompt, build_spontane_prompt
from app.schemas import GenerateRequest, SpontaneResponse


class GenerationError(Exception):
    """Erreur OpenAI, réponse vide ou JSON invalide."""


class ChatClient(Protocol):
    chat: Any  # openai.OpenAI ou FakeOpenAI en test


def _call(client: ChatClient, messages: list[Message], *, json_mode: bool = False) -> str:
    extra: dict[str, Any] = {}
    if json_mode:
        extra["response_format"] = {"type": "json_object"}
    try:
        completion = client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=messages,
            temperature=OPENAI_TEMPERATURE,
            max_tokens=OPENAI_MAX_TOKENS,
            timeout=OPENAI_TIMEOUT_SECONDS,
            **extra,
        )
    except OpenAIError as exc:
        raise GenerationError(MSG_GENERATION) from exc

    content = completion.choices[0].message.content
    if not content or not content.strip():
        raise GenerationError(MSG_GENERATION)
    return content.strip()


def generate_lettre(client: ChatClient, req: GenerateRequest) -> str:
    return _call(client, build_lettre_prompt(req))


def generate_spontane(client: ChatClient, req: GenerateRequest) -> SpontaneResponse:
    raw = _call(client, build_spontane_prompt(req), json_mode=True)
    try:
        return SpontaneResponse.model_validate_json(raw)
    except ValidationError as exc:
        raise GenerationError(MSG_GENERATION) from exc
```

- [ ] **Step 4 : Vérifier**

Run : `pytest tests/test_generator.py -v`
Expected : 7 PASS

- [ ] **Step 5 : Commit**

```bash
git add app/generator.py tests/conftest.py tests/test_generator.py
git commit -m "feat: génération via OpenAI avec gestion des erreurs

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 6 : Routes API

**Files:**
- Modify: `app/main.py`, `tests/test_api.py`

**Interfaces:**
- Consumes: tout ce qui précède.
- Produces: `POST /api/parse-cv` (multipart, champ `file`) → `ParseCVResponse` ; `POST /api/generate` (JSON `GenerateRequest`) → `LettreResponse` ou `SpontaneResponse`. Le client OpenAI vit dans `app.state.openai` ; le lifespan ne le crée que s'il n'existe pas déjà (injection en test).

- [ ] **Step 1 : Tests (doivent échouer)**

Remplacer `tests/test_api.py` par :

```python
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
```

Run : `pytest tests/test_api.py -v`
Expected : `test_racine_sert_index_html` PASS, tous les autres FAIL (404 ou attribut manquant)

- [ ] **Step 2 : Implémentation**

Remplacer `app/main.py` par :

```python
import os
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI, File, HTTPException, Request, UploadFile
from fastapi.staticfiles import StaticFiles
from openai import OpenAI

from app import cv_parser
from app.config import MAX_PDF_BYTES, MSG_NON_PDF, MSG_PDF_TROP_GROS, STATIC_DIR
from app.generator import GenerationError, generate_lettre, generate_spontane
from app.schemas import (
    GenerateRequest,
    LettreResponse,
    ParseCVResponse,
    SpontaneResponse,
)

load_dotenv()


def create_openai_client() -> OpenAI:
    key = os.environ.get("OPENAI_API_KEY", "").strip()
    if not key:
        raise RuntimeError(
            "OPENAI_API_KEY manquante : copiez .env.example en .env et renseignez votre clé."
        )
    return OpenAI(api_key=key)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Les tests injectent app.state.openai avant le démarrage ; en prod on le crée ici.
    if not hasattr(app.state, "openai"):
        app.state.openai = create_openai_client()
    yield


app = FastAPI(title="Centralternance", lifespan=lifespan)


@app.post("/api/parse-cv", response_model=ParseCVResponse)
async def parse_cv(file: UploadFile = File(...)) -> ParseCVResponse:
    filename = (file.filename or "").lower()
    if file.content_type != "application/pdf" and not filename.endswith(".pdf"):
        raise HTTPException(status_code=400, detail=MSG_NON_PDF)
    data = await file.read()
    if len(data) > MAX_PDF_BYTES:
        raise HTTPException(status_code=413, detail=MSG_PDF_TROP_GROS)
    try:
        parsed = cv_parser.extract_text(data)
    except cv_parser.CVParseError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return ParseCVResponse(text=parsed.text, truncated=parsed.truncated)


@app.post("/api/generate", response_model=LettreResponse | SpontaneResponse)
def generate(req: GenerateRequest, request: Request) -> LettreResponse | SpontaneResponse:
    # Fonction synchrone volontairement : FastAPI l'exécute dans un thread,
    # l'appel bloquant à OpenAI ne gèle pas le serveur.
    client = request.app.state.openai
    try:
        if req.type == "lettre":
            return LettreResponse(lettre=generate_lettre(client, req))
        return generate_spontane(client, req)
    except GenerationError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


# Doit rester après les routes API : tout ce qui n'est pas /api/* est servi depuis static/.
app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="static")
```

- [ ] **Step 3 : Vérifier**

Run : `pytest -v`
Expected : tous PASS (Tasks 1 à 6). Si `test_demarrage_sans_cle_echoue` échoue parce qu'un `.env` local contient une clé : `load_dotenv()` ne remplace pas les variables déjà définies mais `monkeypatch.delenv` s'exécute après le chargement du module. Dans ce cas, le test est correct et doit passer ; vérifier que le venv ne définit pas `OPENAI_API_KEY` dans l'environnement du shell (`env | grep OPENAI`).

- [ ] **Step 4 : Test manuel du démarrage**

```bash
cp .env.example .env   # puis mettre une vraie clé dans .env
uvicorn app.main:app --reload
```

Ouvrir `http://localhost:8000` : la page placeholder « Centralternance » s'affiche. `http://localhost:8000/docs` montre les deux routes. Arrêter avec Ctrl+C.

- [ ] **Step 5 : Commit**

```bash
git add app/main.py tests/test_api.py
git commit -m "feat: routes /api/parse-cv et /api/generate

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 7 : Interface — HTML et CSS

**Files:**
- Modify: `static/index.html` (remplacement complet)
- Create: `static/style.css`

**Interfaces:**
- Produces: les identifiants DOM utilisés par `app.js` (Task 8). Ne pas les renommer :
  - écrans : `screen-onboarding`, `screen-menu`, `screen-offre`, `screen-spontane`, `screen-resultat`
  - onboarding : `form-onboarding`, `cv-file`, `cv-status`, `cs-rythme`, `cs-debut`, `cs-duree`, `modele`, `btn-start`
  - menu : `card-offre`, `card-spontane`, `link-edit-profile`
  - offre : `form-offre`, `offre`, `btn-gen-lettre`, `err-offre`
  - spontané : `form-spontane`, `c-nom`, `c-entreprise`, `c-poste-contact`, `c-poste-vise`, `btn-gen-spontane`, `err-spontane`
  - résultat : `result-lettre`, `lettre-text`, `btn-copy-lettre`, `btn-print`, `result-spontane`, `objet-text`, `email-text`, `linkedin-text`, `btn-copy-objet`, `btn-copy-email`, `btn-copy-linkedin`, `btn-new`, `btn-menu` (dans la barre du haut), `print-area`
- Comportement JS attendu par le HTML : `[hidden]` masque, `.btn.loading` affiche un spinner.

- [ ] **Step 1 : HTML**

Remplacer `static/index.html` par :

```html
<!doctype html>
<html lang="fr">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Centralternance</title>
  <link rel="stylesheet" href="/style.css">
</head>
<body>
  <header class="topbar">
    <span class="brand">Centralternance</span>
    <button type="button" id="btn-menu" class="link" hidden>← Menu</button>
  </header>

  <main>
    <!-- 1. Onboarding -->
    <section id="screen-onboarding" class="screen" hidden>
      <h1>Bienvenue</h1>
      <p class="lead">Chargez votre CV une fois. Ensuite, chaque lettre ou message se génère en quelques secondes.</p>
      <form id="form-onboarding" novalidate>
        <label class="field">
          <span>Votre CV (PDF)</span>
          <input type="file" id="cv-file" accept="application/pdf,.pdf">
        </label>
        <p id="cv-status" class="status" aria-live="polite"></p>

        <fieldset>
          <legend>Mon alternance à CentraleSupélec</legend>
          <label class="field"><span>Rythme</span>
            <input id="cs-rythme" value="3 semaines en entreprise / 1 semaine à l'école" maxlength="200"></label>
          <label class="field"><span>Date de début</span>
            <input id="cs-debut" value="septembre 2027" maxlength="200"></label>
          <label class="field"><span>Durée</span>
            <input id="cs-duree" value="3 ans" maxlength="200"></label>
        </fieldset>

        <label class="field">
          <span>Modèle de lettre <em>(facultatif)</em></span>
          <textarea id="modele" rows="6" maxlength="6000"
            placeholder="Collez une lettre de motivation que vous avez déjà écrite. L'IA reprendra votre ton et votre structure."></textarea>
        </label>

        <button type="submit" id="btn-start" class="btn primary" disabled>Commencer</button>
      </form>
    </section>

    <!-- 2. Menu -->
    <section id="screen-menu" class="screen" hidden>
      <h1>Que voulez-vous faire ?</h1>
      <div class="cards">
        <button type="button" id="card-offre" class="card">
          <strong>Répondre à une offre</strong>
          <span>Collez l'offre, obtenez une lettre de motivation.</span>
        </button>
        <button type="button" id="card-spontane" class="card">
          <strong>Candidature spontanée</strong>
          <span>Indiquez qui contacter, obtenez un email et un message LinkedIn.</span>
        </button>
      </div>
      <p><button type="button" id="link-edit-profile" class="link">Modifier mon CV / mes infos</button></p>
    </section>

    <!-- 3. Offre -->
    <section id="screen-offre" class="screen" hidden>
      <h1>Répondre à une offre</h1>
      <form id="form-offre" novalidate>
        <label class="field">
          <span>Collez l'offre ici</span>
          <textarea id="offre" rows="14" maxlength="10000" placeholder="Intitulé, missions, profil recherché…"></textarea>
        </label>
        <p id="err-offre" class="error" hidden></p>
        <button type="submit" id="btn-gen-lettre" class="btn primary" disabled>Générer la lettre</button>
      </form>
    </section>

    <!-- 4. Spontané -->
    <section id="screen-spontane" class="screen" hidden>
      <h1>Candidature spontanée</h1>
      <form id="form-spontane" novalidate>
        <label class="field"><span>Prénom et nom du contact</span>
          <input id="c-nom" maxlength="200" placeholder="Marie Martin"></label>
        <label class="field"><span>Entreprise</span>
          <input id="c-entreprise" maxlength="200" placeholder="Thales"></label>
        <label class="field"><span>Son poste</span>
          <input id="c-poste-contact" maxlength="200" placeholder="Responsable de l'équipe data"></label>
        <label class="field"><span>Poste que vous visez</span>
          <input id="c-poste-vise" maxlength="200" placeholder="Alternant ingénieur data"></label>
        <p id="err-spontane" class="error" hidden></p>
        <button type="submit" id="btn-gen-spontane" class="btn primary" disabled>Générer les messages</button>
      </form>
    </section>

    <!-- 5. Résultat -->
    <section id="screen-resultat" class="screen" hidden>
      <h1>Votre candidature</h1>
      <p class="lead">Relisez, modifiez si besoin, puis copiez.</p>

      <div id="result-lettre" hidden>
        <label class="field"><span>Lettre de motivation</span>
          <textarea id="lettre-text" rows="22"></textarea></label>
        <div class="actions">
          <button type="button" id="btn-copy-lettre" class="btn">Copier</button>
          <button type="button" id="btn-print" class="btn">Télécharger en PDF</button>
        </div>
      </div>

      <div id="result-spontane" hidden>
        <label class="field"><span>Objet de l'email</span>
          <input id="objet-text"></label>
        <div class="actions"><button type="button" id="btn-copy-objet" class="btn">Copier l'objet</button></div>

        <label class="field"><span>Email</span>
          <textarea id="email-text" rows="12"></textarea></label>
        <div class="actions"><button type="button" id="btn-copy-email" class="btn">Copier l'email</button></div>

        <label class="field"><span>Message LinkedIn</span>
          <textarea id="linkedin-text" rows="7"></textarea></label>
        <div class="actions"><button type="button" id="btn-copy-linkedin" class="btn">Copier le message LinkedIn</button></div>
      </div>

      <div class="actions bottom">
        <button type="button" id="btn-new" class="btn primary">Nouvelle candidature</button>
      </div>
    </section>
  </main>

  <!-- Zone imprimée uniquement (export PDF de la lettre) -->
  <div id="print-area" aria-hidden="true"></div>

  <script src="/app.js"></script>
</body>
</html>
```

- [ ] **Step 2 : CSS**

`static/style.css` :

```css
:root {
  --bg: #f6f7f9;
  --surface: #ffffff;
  --text: #1c2130;
  --muted: #5f6675;
  --border: #d9dde5;
  --primary: #1f4fd8;
  --primary-hover: #183fb0;
  --error: #b42323;
  --ok: #1d7a3b;
  --radius: 10px;
}

* { box-sizing: border-box; }
[hidden] { display: none !important; }

body {
  margin: 0;
  font: 16px/1.5 system-ui, -apple-system, "Segoe UI", Roboto, sans-serif;
  color: var(--text);
  background: var(--bg);
}

.topbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 14px 20px;
  background: var(--surface);
  border-bottom: 1px solid var(--border);
}
.brand { font-weight: 700; letter-spacing: 0.2px; }

main { max-width: 720px; margin: 0 auto; padding: 28px 20px 60px; }

h1 { font-size: 1.6rem; margin: 0 0 6px; }
.lead { color: var(--muted); margin: 0 0 24px; }

.field { display: block; margin-bottom: 16px; }
.field > span { display: block; font-weight: 600; margin-bottom: 6px; }
.field em { font-weight: 400; color: var(--muted); font-style: normal; }

input[type="text"], input:not([type]), textarea {
  width: 100%;
  padding: 10px 12px;
  font: inherit;
  color: inherit;
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius);
}
textarea { resize: vertical; }
input:focus, textarea:focus { outline: 2px solid var(--primary); outline-offset: 1px; border-color: transparent; }
input[type="file"] { display: block; }

fieldset { border: 1px solid var(--border); border-radius: var(--radius); padding: 14px 16px 2px; margin: 0 0 16px; }
legend { font-weight: 600; padding: 0 6px; }

.btn {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 10px 18px;
  font: inherit;
  font-weight: 600;
  color: var(--text);
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  cursor: pointer;
}
.btn:hover:not(:disabled) { border-color: var(--primary); }
.btn.primary { color: #fff; background: var(--primary); border-color: var(--primary); }
.btn.primary:hover:not(:disabled) { background: var(--primary-hover); }
.btn:disabled { opacity: 0.55; cursor: not-allowed; }

.btn.loading::before {
  content: "";
  width: 14px; height: 14px;
  border: 2px solid currentColor;
  border-right-color: transparent;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}
@keyframes spin { to { transform: rotate(360deg); } }

.link {
  padding: 0;
  font: inherit;
  color: var(--primary);
  background: none;
  border: none;
  cursor: pointer;
  text-decoration: underline;
}

.cards { display: grid; gap: 16px; grid-template-columns: 1fr; margin: 20px 0; }
@media (min-width: 560px) { .cards { grid-template-columns: 1fr 1fr; } }
.card {
  display: flex; flex-direction: column; gap: 6px;
  padding: 22px 20px;
  text-align: left;
  font: inherit;
  color: inherit;
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  cursor: pointer;
}
.card:hover { border-color: var(--primary); }
.card strong { font-size: 1.05rem; }
.card span { color: var(--muted); }

.actions { display: flex; flex-wrap: wrap; gap: 10px; margin: -6px 0 22px; }
.actions.bottom { margin-top: 10px; }

.status { min-height: 1.5em; margin: -8px 0 16px; color: var(--muted); }
.status.ok { color: var(--ok); }
.status.error, .error { color: var(--error); margin: 0 0 12px; }

#print-area { display: none; }

@media print {
  body { background: #fff; }
  .topbar, main { display: none !important; }
  #print-area {
    display: block;
    font: 12pt/1.5 Georgia, "Times New Roman", serif;
    color: #000;
    white-space: pre-wrap;
    max-width: 17cm;
    margin: 2cm auto;
  }
}
```

- [ ] **Step 3 : Vérification visuelle**

```bash
uvicorn app.main:app --reload
```

Ouvrir `http://localhost:8000`. Sans JS, tous les écrans sont masqués (`hidden`) : c'est normal, la page paraît vide sous la barre du haut. Pour vérifier le rendu, ouvrir l'inspecteur et retirer temporairement l'attribut `hidden` de chaque `<section>` l'une après l'autre. Contrôler : marges lisibles, champs pleine largeur, cartes côte à côte au-delà de 560 px, bouton principal bleu.

- [ ] **Step 4 : Commit**

```bash
git add static/index.html static/style.css
git commit -m "feat: interface HTML/CSS des cinq écrans

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 8 : Interface — logique JavaScript

**Files:**
- Create: `static/app.js`

**Interfaces:**
- Consumes: les identifiants DOM de la Task 7, les routes de la Task 6.
- Produces: une page fonctionnelle de bout en bout. Clé `sessionStorage` : `centralternance.session` = `{ cv, truncated, cs: {rythme, debut, duree}, modele }`.

- [ ] **Step 1 : Implémentation**

`static/app.js` :

```js
"use strict";

const SESSION_KEY = "centralternance.session";
const $ = (id) => document.getElementById(id);

// ---------- Session (navigateur uniquement) ----------

function loadSession() {
  try {
    const raw = sessionStorage.getItem(SESSION_KEY);
    return raw ? JSON.parse(raw) : null;
  } catch {
    return null;
  }
}

function saveSession(session) {
  try {
    sessionStorage.setItem(SESSION_KEY, JSON.stringify(session));
  } catch {
    /* mode privé strict : on continue en mémoire seulement */
  }
}

const state = {
  session: loadSession(),
  pendingCV: null,     // { text, truncated } uploadé mais pas encore validé par "Commencer"
  lastType: null,      // "lettre" | "spontane"
  lastBody: null,      // dernière requête envoyée à /api/generate (pour Réessayer)
};

// ---------- Navigation ----------

function show(name) {
  document.querySelectorAll(".screen").forEach((s) => {
    s.hidden = s.id !== `screen-${name}`;
  });
  $("btn-menu").hidden = name === "onboarding" || name === "menu";
  window.scrollTo(0, 0);
}

// ---------- Appels API ----------

async function api(path, options) {
  let res;
  try {
    res = await fetch(path, options);
  } catch {
    throw new Error("Connexion impossible. Vérifiez votre réseau et réessayez.");
  }
  let body = null;
  try {
    body = await res.json();
  } catch {
    /* réponse sans JSON */
  }
  if (!res.ok) {
    const detail = body && body.detail;
    throw new Error(typeof detail === "string" ? detail : "Erreur inattendue, réessayez.");
  }
  return body;
}

function setLoading(btn, on, label) {
  btn.disabled = on;
  btn.classList.toggle("loading", on);
  if (on) {
    btn.dataset.label = btn.textContent;
    btn.textContent = label;
  } else if (btn.dataset.label) {
    btn.textContent = btn.dataset.label;
  }
}

function showError(el, message, onRetry) {
  el.textContent = message + " ";
  if (onRetry) {
    const retry = document.createElement("button");
    retry.type = "button";
    retry.className = "link";
    retry.textContent = "Réessayer";
    retry.addEventListener("click", onRetry);
    el.appendChild(retry);
  }
  el.hidden = false;
}

function clearError(el) {
  el.textContent = "";
  el.hidden = true;
}

// ---------- Écran 1 : onboarding ----------

function fillOnboardingFromSession() {
  const s = state.session;
  const status = $("cv-status");
  if (s && s.cv) {
    $("cs-rythme").value = s.cs.rythme;
    $("cs-debut").value = s.cs.debut;
    $("cs-duree").value = s.cs.duree;
    $("modele").value = s.modele || "";
    status.textContent = "CV chargé : conservé (choisissez un fichier pour le remplacer).";
    status.className = "status ok";
  } else {
    status.textContent = "";
    status.className = "status";
  }
  $("cv-file").value = "";
  state.pendingCV = null;
  updateStartButton();
}

function updateStartButton() {
  const hasCV = Boolean(state.pendingCV || (state.session && state.session.cv));
  $("btn-start").disabled = !hasCV;
}

$("cv-file").addEventListener("change", async (event) => {
  const file = event.target.files[0];
  const status = $("cv-status");
  state.pendingCV = null;
  updateStartButton();
  if (!file) return;

  status.textContent = "Lecture du CV…";
  status.className = "status";
  const form = new FormData();
  form.append("file", file);
  try {
    const parsed = await api("/api/parse-cv", { method: "POST", body: form });
    state.pendingCV = { text: parsed.text, truncated: parsed.truncated };
    status.textContent = parsed.truncated
      ? "CV lu (très long : seules les premières pages seront utilisées)."
      : "CV lu avec succès.";
    status.className = "status ok";
  } catch (err) {
    status.textContent = err.message;
    status.className = "status error";
    event.target.value = "";
  }
  updateStartButton();
});

$("form-onboarding").addEventListener("submit", (event) => {
  event.preventDefault();
  const cv = state.pendingCV || { text: state.session.cv, truncated: state.session.truncated };
  state.session = {
    cv: cv.text,
    truncated: cv.truncated,
    cs: {
      rythme: $("cs-rythme").value.trim(),
      debut: $("cs-debut").value.trim(),
      duree: $("cs-duree").value.trim(),
    },
    modele: $("modele").value.trim(),
  };
  saveSession(state.session);
  state.pendingCV = null;
  show("menu");
});

// ---------- Écran 2 : menu ----------

$("card-offre").addEventListener("click", () => openOffre());
$("card-spontane").addEventListener("click", () => openSpontane());
$("link-edit-profile").addEventListener("click", () => {
  fillOnboardingFromSession();
  show("onboarding");
});
$("btn-menu").addEventListener("click", () => show("menu"));

// ---------- Écran 3 : offre ----------

function openOffre() {
  $("offre").value = "";
  clearError($("err-offre"));
  $("btn-gen-lettre").disabled = true;
  show("offre");
  $("offre").focus();
}

$("offre").addEventListener("input", () => {
  $("btn-gen-lettre").disabled = $("offre").value.trim() === "";
});

$("form-offre").addEventListener("submit", (event) => {
  event.preventDefault();
  const body = {
    type: "lettre",
    cv: state.session.cv,
    cs: state.session.cs,
    modele: state.session.modele,
    offre: $("offre").value.trim(),
  };
  runGeneration(body, $("btn-gen-lettre"), $("err-offre"));
});

// ---------- Écran 4 : spontané ----------

const contactFields = ["c-nom", "c-entreprise", "c-poste-contact", "c-poste-vise"];

function openSpontane() {
  contactFields.forEach((id) => { $(id).value = ""; });
  clearError($("err-spontane"));
  $("btn-gen-spontane").disabled = true;
  show("spontane");
  $("c-nom").focus();
}

function updateSpontaneButton() {
  const complete = contactFields.every((id) => $(id).value.trim() !== "");
  $("btn-gen-spontane").disabled = !complete;
}
contactFields.forEach((id) => $(id).addEventListener("input", updateSpontaneButton));

$("form-spontane").addEventListener("submit", (event) => {
  event.preventDefault();
  const body = {
    type: "spontane",
    cv: state.session.cv,
    cs: state.session.cs,
    modele: state.session.modele,
    contact: {
      nom: $("c-nom").value.trim(),
      entreprise: $("c-entreprise").value.trim(),
      poste_contact: $("c-poste-contact").value.trim(),
      poste_vise: $("c-poste-vise").value.trim(),
    },
  };
  runGeneration(body, $("btn-gen-spontane"), $("err-spontane"));
});

// ---------- Génération commune ----------

async function runGeneration(body, btn, errEl) {
  clearError(errEl);
  setLoading(btn, true, "Génération en cours…");
  state.lastType = body.type;
  state.lastBody = body;
  try {
    const result = await api("/api/generate", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    showResult(body.type, result);
  } catch (err) {
    showError(errEl, err.message, () => runGeneration(body, btn, errEl));
  } finally {
    setLoading(btn, false);
  }
}

// ---------- Écran 5 : résultat ----------

function showResult(type, result) {
  const isLettre = type === "lettre";
  $("result-lettre").hidden = !isLettre;
  $("result-spontane").hidden = isLettre;
  if (isLettre) {
    $("lettre-text").value = result.lettre;
  } else {
    $("objet-text").value = result.objet;
    $("email-text").value = result.email;
    $("linkedin-text").value = result.linkedin;
  }
  show("resultat");
}

async function copyFrom(inputId, btn) {
  const text = $(inputId).value;
  const original = btn.textContent;
  try {
    await navigator.clipboard.writeText(text);
    btn.textContent = "Copié !";
  } catch {
    $(inputId).select();
    document.execCommand("copy");
    btn.textContent = "Copié !";
  }
  setTimeout(() => { btn.textContent = original; }, 1500);
}

$("btn-copy-lettre").addEventListener("click", (e) => copyFrom("lettre-text", e.currentTarget));
$("btn-copy-objet").addEventListener("click", (e) => copyFrom("objet-text", e.currentTarget));
$("btn-copy-email").addEventListener("click", (e) => copyFrom("email-text", e.currentTarget));
$("btn-copy-linkedin").addEventListener("click", (e) => copyFrom("linkedin-text", e.currentTarget));

$("btn-print").addEventListener("click", () => {
  $("print-area").textContent = $("lettre-text").value;
  window.print();
});

$("btn-new").addEventListener("click", () => {
  if (state.lastType === "spontane") openSpontane();
  else openOffre();
});

// ---------- Démarrage ----------

if (state.session && state.session.cv) {
  show("menu");
} else {
  fillOnboardingFromSession();
  show("onboarding");
}
```

- [ ] **Step 2 : Test manuel de bout en bout**

Avec une vraie clé dans `.env` :

```bash
uvicorn app.main:app --reload
```

Parcourir, dans l'ordre, et cocher :

1. Ouvrir `http://localhost:8000` → écran Onboarding, bouton Commencer grisé.
2. Choisir un fichier `.txt` → message d'erreur « Fichier non PDF », bouton toujours grisé.
3. Choisir un vrai CV PDF → « CV lu avec succès. », bouton actif.
4. Commencer → écran Menu.
5. « Répondre à une offre » → bouton Générer grisé ; coller une offre → bouton actif ; Générer → spinner puis écran Résultat avec une lettre en français mentionnant le rythme et la date de début.
6. Modifier un mot dans la lettre → Copier → coller dans un éditeur : le texte modifié est bien copié.
7. Télécharger en PDF → la boîte d'impression montre uniquement la lettre, en serif, sans interface.
8. Nouvelle candidature → écran Offre vide. ← Menu → écran Menu.
9. « Candidature spontanée » → remplir les 4 champs (bouton actif seulement quand les 4 sont remplis) → Générer → objet, email, LinkedIn affichés, chaque bouton Copier fonctionne.
10. Recharger la page (F5) → arrive directement sur le Menu (session conservée).
11. « Modifier mon CV / mes infos » → champs pré-remplis, message « CV chargé : conservé », bouton Commencer actif sans re-upload.
12. Fermer l'onglet, rouvrir `http://localhost:8000` → écran Onboarding (session perdue, comportement voulu).
13. Mettre une clé OpenAI invalide dans `.env`, redémarrer, générer → message « Génération impossible, réessayez. » avec lien Réessayer ; le bouton Générer est réactivé.

Toute étape qui échoue est corrigée avant de passer à la suivante.

- [ ] **Step 3 : Commit**

```bash
git add static/app.js
git commit -m "feat: logique front (session, navigation, génération, copie, PDF)

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 9 : README et checklist de déploiement

**Files:**
- Create: `README.md`

**Interfaces:** aucune.

- [ ] **Step 1 : README**

`README.md` :

```markdown
# Centralternance

Générateur de lettres de motivation et de messages de candidature spontanée (email + LinkedIn) pour les élèves-ingénieurs apprentis de CentraleSupélec. L'étudiant charge son CV une fois ; chaque candidature se génère ensuite en quelques secondes avec GPT-4o.

Aucune donnée n'est stockée côté serveur : le CV reste dans le navigateur de l'étudiant tant que l'onglet est ouvert.

## Lancer en local

Prérequis : Python 3.12 ou plus, une clé API OpenAI (https://platform.openai.com/api-keys).

    python3 -m venv .venv
    source .venv/bin/activate
    pip install -r requirements.txt
    cp .env.example .env        # puis renseigner OPENAI_API_KEY dans .env
    uvicorn app.main:app --reload

Ouvrir http://localhost:8000.

## Tests

    pytest

Aucun test n'appelle OpenAI : le client est simulé.

## Modifier les prompts

Les instructions données à l'IA sont dans `app/prompts/` :

| Fichier | Rôle |
|---|---|
| `commun.md` | Règles valables pour tout (ton, interdits, ne rien inventer) |
| `lettre_sans_modele.md` | Lettre quand l'étudiant n'a pas fourni de modèle |
| `lettre_avec_modele.md` | Lettre quand l'étudiant a fourni un modèle |
| `lettre_exemple.md` | Lettre de référence utilisée quand il n'y a pas de modèle |
| `spontane.md` | Objet + email + message LinkedIn (sortie JSON) |

Ils sont relus à chaque requête : modifiez-les, rechargez la page, c'est pris en compte. Ne changez pas les clés JSON demandées dans `spontane.md` (`objet`, `email`, `linkedin`).

## Coûts

Une génération consomme environ 4 000 tokens en entrée et 600 en sortie, soit ~0,4 centime avec GPT-4o. Pour éviter toute surprise, définissez un plafond mensuel dans https://platform.openai.com/settings/organization/limits.

Les limites de taille (CV, offre, modèle) et le nombre maximal de tokens en sortie sont dans `app/config.py`.

## Déployer

L'application est un serveur FastAPI classique. Sur Render, Railway ou Fly.io :

- Commande de build : `pip install -r requirements.txt`
- Commande de démarrage : `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
- Variable d'environnement : `OPENAI_API_KEY`

Le serveur refuse de démarrer si la clé est absente.

## Checklist de test manuel

À dérouler après toute modification du front (`static/`) :

1. Onboarding : `.txt` refusé, PDF accepté, bouton Commencer actif seulement avec un CV.
2. Offre : bouton grisé si vide, génération, lettre en français avec rythme et date.
3. Résultat : édition puis Copier copie le texte édité ; Télécharger en PDF n'imprime que la lettre.
4. Nouvelle candidature → formulaire vide du même type ; ← Menu → menu.
5. Spontané : bouton actif seulement avec les 4 champs ; objet, email, LinkedIn affichés et copiables.
6. F5 → menu direct ; fermeture de l'onglet → retour onboarding.
7. Modifier mon CV : champs pré-remplis, CV conservé sans re-upload.
8. Clé invalide → « Génération impossible, réessayez. » + Réessayer.
```

- [ ] **Step 2 : Vérifier que tout passe**

Run : `pytest -v`
Expected : tous PASS

- [ ] **Step 3 : Commit**

```bash
git add README.md
git commit -m "docs: README (installation, prompts, coûts, déploiement, checklist)

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```
