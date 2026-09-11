# Centralternance — Design du MVP

Date : 2026-09-11
Statut : validé en brainstorming, en attente de relecture

## 1. Objectif

Outil web pour les étudiants ingénieurs apprentis de CentraleSupélec. À partir de leur CV, il génère :

- une **lettre de motivation** sur mesure en réponse à une offre d'alternance ;
- un **message LinkedIn**, un **email** et son **objet** pour une candidature spontanée.

Critères de succès du MVP :

- un étudiant obtient une lettre exploitable en moins d'une minute après avoir collé l'offre ;
- chaque génération coûte moins de 1 centime ;
- aucune donnée personnelle n'est stockée côté serveur.

## 2. Périmètre

### Inclus

- Onboarding une fois par session : upload CV (PDF), bloc CentraleSupélec, modèle de lettre facultatif.
- Flux **Offre** : coller l'offre → lettre de motivation.
- Flux **Spontané** : formulaire (contact, entreprise, poste du contact, poste visé) → objet + email + message LinkedIn, générés ensemble.
- Résultat éditable, bouton Copier par bloc, export PDF de la lettre.
- Après export : retour au formulaire du même type (vide), avec bouton Menu.
- Français uniquement.
- Modèle IA : GPT-4o via l'API OpenAI, appelé uniquement côté serveur.

### Exclu (v2 ou plus tard)

- Comptes utilisateurs, base de données, historique persistant.
- Messages de relance, score de compatibilité, pitch oral, section « À propos » LinkedIn, plusieurs variantes.
- Export Word.
- Anglais.
- Hébergement par l'association Rezo (envisagé une fois l'usage réel démontré).

## 3. Décisions techniques

| Sujet | Décision | Raison |
|---|---|---|
| Frontend | HTML / CSS / JS vanilla, une seule page | 5 écrans, 3 formulaires : un framework n'apporte rien et l'auteur ne connaît pas React |
| Serveur | Python 3.12 + FastAPI + uvicorn | L'auteur connaît Python ; nécessaire pour cacher la clé OpenAI |
| Parsing PDF | `pypdf` côté serveur | Simple, sans dépendance système |
| IA | `openai` SDK, modèle `gpt-4o`, réponse JSON pour le flux spontané | Qualité suffisante, ~0,5 centime par lettre |
| Export PDF | Côté navigateur via `window.print()` + feuille de style `@media print` | Zéro dépendance, rendu propre, l'utilisateur choisit « Enregistrer en PDF » |
| Session | `sessionStorage` du navigateur | Survit à un rechargement, disparaît à la fermeture de l'onglet ; rien côté serveur |
| Config | `.env` avec `OPENAI_API_KEY`, chargé par `python-dotenv` | Standard, jamais commité |
| Tests | `pytest` + `httpx` (TestClient), OpenAI mocké | Aucun appel réel en test |
| Hébergement | Local d'abord, puis Render / Railway / Fly.io | Déploiement en quelques minutes, gratuit ou ~5 €/mois |

## 4. Architecture

```
centralternance/
├── app/
│   ├── __init__.py
│   ├── main.py              # FastAPI : monte static/, expose /api/parse-cv et /api/generate
│   ├── cv_parser.py         # bytes PDF → texte brut ; lève CVParseError
│   ├── prompts.py           # charge les .md, assemble le prompt selon le type et le contexte
│   ├── generator.py         # appelle OpenAI, renvoie texte (lettre) ou dict (spontané)
│   ├── schemas.py           # modèles Pydantic des requêtes / réponses
│   └── prompts/
│       ├── commun.md
│       ├── lettre_sans_modele.md
│       ├── lettre_avec_modele.md
│       └── spontane.md
├── static/
│   ├── index.html           # les 5 écrans
│   ├── style.css            # incluant @media print
│   └── app.js               # navigation, session, appels API, copier, imprimer
├── tests/
│   ├── fixtures/cv_test.pdf
│   ├── test_cv_parser.py
│   ├── test_prompts.py
│   ├── test_generator.py
│   └── test_api.py
├── .env.example
├── .gitignore
├── requirements.txt
└── README.md
```

### Responsabilités

- **`cv_parser.py`** — `extract_text(pdf_bytes) -> str`. Concatène le texte de toutes les pages, normalise les espaces, tronque à `MAX_CV_CHARS` (15 000). Lève `CVParseError` si le fichier n'est pas un PDF valide ou si le texte extrait est vide (PDF scanné).
- **`prompts.py`** — `build_lettre_prompt(ctx) -> list[Message]` et `build_spontane_prompt(ctx) -> list[Message]`. Lit les fichiers `.md` une fois au démarrage. Choisit `lettre_avec_modele.md` si `ctx.modele` est non vide, sinon `lettre_sans_modele.md`. Le message système = `commun.md` + fichier spécifique ; le message utilisateur = les données (CV, bloc CS, modèle s'il existe, offre ou formulaire).
- **`generator.py`** — `generate_lettre(ctx) -> str` et `generate_spontane(ctx) -> SpontaneResult`. Appelle `chat.completions.create` avec `model="gpt-4o"`, `temperature=0.7`, `max_tokens=1200`. Pour le spontané, `response_format={"type": "json_object"}` et validation Pydantic du JSON. Lève `GenerationError` sur toute erreur OpenAI ou JSON invalide.
- **`main.py`** — routes ci-dessous, gestion des erreurs → codes HTTP, sert `static/` à la racine.
- **`app.js`** — un objet `session` (cv, cs, modele) synchronisé avec `sessionStorage` ; une fonction `show(screen)` ; deux fonctions `generateLettre()` / `generateSpontane()` ; `copy(el)` ; `printLettre()`.

### Flux de données

1. Onboarding : le navigateur envoie le PDF à `POST /api/parse-cv`, reçoit le texte, le range dans `session.cv` avec le bloc CS et le modèle.
2. Génération : le navigateur envoie **tout le contexte** (CV, CS, modèle, offre ou formulaire) à `POST /api/generate`. Le serveur ne garde rien entre deux requêtes.
3. Le résultat est affiché dans des zones éditables. Copier et Imprimer opèrent sur le contenu édité.

## 5. API

### `POST /api/parse-cv`

- Corps : `multipart/form-data`, champ `file` (PDF, max 5 Mo).
- 200 : `{ "text": "...", "truncated": false }`
- 400 : `{ "detail": "Fichier non PDF" }` / `{ "detail": "Impossible de lire ce PDF (scanné ou protégé). Essayez un export texte." }`
- 413 : fichier trop gros.

### `POST /api/generate`

Corps JSON :

```json
{
  "type": "lettre" | "spontane",
  "cv": "texte du CV",
  "cs": { "rythme": "...", "debut": "...", "duree": "..." },
  "modele": "texte ou chaîne vide",
  "offre": "texte de l'offre",            // requis si type = lettre
  "contact": {                            // requis si type = spontane
    "nom": "...", "entreprise": "...", "poste_contact": "...", "poste_vise": "..."
  }
}
```

Limites (validées par Pydantic, 422 sinon) : `cv` ≤ 15 000 caractères, `offre` ≤ 10 000, `modele` ≤ 6 000, chaque champ contact ≤ 200.

Réponses :

- 200, type lettre : `{ "lettre": "..." }`
- 200, type spontané : `{ "objet": "...", "email": "...", "linkedin": "..." }`
- 502 : `{ "detail": "Génération impossible, réessayez." }` (erreur OpenAI, timeout 60 s, JSON invalide).

## 6. Prompts

Les quatre fichiers `.md` sont la seule chose que l'auteur modifiera au quotidien. Aucune logique n'y est codée : `prompts.py` les concatène tels quels.

- `commun.md` — règles transverses : ton, formulations interdites, ne jamais inventer d'expérience absente du CV, toujours mentionner le rythme et la date de début CentraleSupélec.
- `lettre_sans_modele.md` — structure imposée, longueur cible. (Décision du 2026-09-11 : pas de lettre de référence par défaut ; l'auteur n'en fournit pas.)
- `lettre_avec_modele.md` — comment exploiter le modèle de l'étudiant : conserver ton, structure et tournures ; remplacer tout contenu spécifique à une autre entreprise ; appliquer quand même les règles communes.
- `spontane.md` — contraintes LinkedIn (court, direct, « Bonjour Prénom »), email (formel, objet accrocheur, demande claire en fin de message) ; impose la sortie JSON `{ "objet", "email", "linkedin" }`.

Une première version de chaque fichier est écrite lors de l'implémentation pour que l'application soit testable ; l'auteur les remplacera ensuite sans toucher au code.

## 7. Écrans

Une page, cinq sections `<section id="screen-…">`, une seule visible à la fois.

1. **Onboarding** — input fichier PDF (obligatoire) ; trois champs CS pré-remplis (« 3 semaines entreprise / 1 semaine école », « septembre 2027 », « 3 ans ») ; textarea modèle (facultatif) ; bouton « Commencer » (désactivé tant que le CV n'est pas parsé).
2. **Menu** — deux cartes « Répondre à une offre » / « Candidature spontanée » ; lien « Modifier mon CV / mes infos » → écran 1 avec les champs CS et le modèle pré-remplis ; le CV actuel est conservé sauf si un nouveau fichier est uploadé (mention « CV chargé : conservé » affichée).
3. **Offre** — textarea « Collez l'offre ici » ; bouton « Générer la lettre » (désactivé si vide) ; lien « Menu ».
4. **Spontané** — champs Prénom Nom, Entreprise, Son poste, Poste visé ; bouton « Générer les messages » (désactivé si un champ est vide) ; lien « Menu ».
5. **Résultat** — lettre : une textarea éditable + « Copier » + « Télécharger en PDF » ; spontané : trois blocs éditables (Objet, Email, LinkedIn) chacun avec « Copier » ; bouton « Nouvelle candidature » → écran 3 ou 4 vide selon le type ; bouton « Menu ».

Pendant un appel API, le bouton concerné affiche un spinner et est désactivé. Au chargement de la page : si `sessionStorage` contient un CV → écran 2, sinon écran 1.

## 8. Gestion des erreurs

| Situation | Comportement |
|---|---|
| Fichier non PDF ou PDF illisible | Message sous l'input, CV non enregistré |
| CV tronqué | Bandeau d'avertissement, on continue |
| Champ requis vide | Bouton Générer désactivé |
| Erreur OpenAI / réseau / timeout | Message « Génération impossible, réessayez » + bouton Réessayer qui relance la même requête |
| Session absente (onglet fermé) | Retour écran 1 |
| Clé OpenAI absente au démarrage | Le serveur refuse de démarrer avec un message explicite |

## 9. Maîtrise des coûts

- Limites de taille sur chaque champ (section 5).
- `max_tokens=1200` par réponse.
- Une seule génération par clic ; pas de variantes multiples.
- README : configurer un plafond mensuel de dépenses sur le compte OpenAI.

Estimation : ~4 000 tokens en entrée + ~600 en sortie par lettre ≈ 0,4 centime avec GPT-4o.

## 10. Tests

- `test_cv_parser.py` — extraction sur `fixtures/cv_test.pdf` ; erreur sur un fichier texte renommé `.pdf` ; erreur sur un PDF sans texte ; troncature au-delà de `MAX_CV_CHARS`.
- `test_prompts.py` — avec modèle → `lettre_avec_modele.md` utilisé et modèle présent dans le message utilisateur ; sans modèle → `lettre_sans_modele.md` utilisé ; bloc CS et offre présents dans le message utilisateur ; spontané contient les quatre champs contact.
- `test_generator.py` — client OpenAI mocké : lettre renvoyée telle quelle ; spontané parse un JSON valide ; JSON invalide → `GenerationError` ; exception OpenAI → `GenerationError`.
- `test_api.py` — `/api/parse-cv` 200 / 400 / 413 ; `/api/generate` 200 lettre, 200 spontané, 422 champ manquant ou trop long, 502 quand le générateur lève.

Le frontend est testé manuellement selon une checklist dans le README (parcours complet des deux flux, rechargement de page, fermeture d'onglet, erreur réseau simulée).

## 11. Déploiement

- Local : `pip install -r requirements.txt`, copier `.env.example` en `.env`, `uvicorn app.main:app --reload`, ouvrir `http://localhost:8000`.
- Hébergé : Render / Railway / Fly.io, commande de démarrage `uvicorn app.main:app --host 0.0.0.0 --port $PORT`, variable d'environnement `OPENAI_API_KEY`. Documenté dans le README.
