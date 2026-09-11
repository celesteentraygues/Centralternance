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
| `commun.md` | Règles valables pour tout (ne rien inventer, date de début/durée, pas de texte hors contenu) |
| `lettre_sans_modele.md` | Lettre quand l'étudiant n'a pas fourni de modèle |
| `lettre_avec_modele.md` | Lettre quand l'étudiant a fourni un modèle |
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
2. Offre : bouton grisé si vide, génération, lettre en français avec date de début et durée.
3. Résultat : édition puis Copier copie le texte édité ; Télécharger en PDF n'imprime que la lettre.
4. Nouvelle candidature → formulaire vide du même type ; ← Menu → menu.
5. Spontané : bouton actif seulement avec les 4 champs ; objet, email, LinkedIn affichés et copiables.
6. F5 → menu direct ; fermeture de l'onglet → retour onboarding.
7. Modifier mon CV : champs pré-remplis, CV conservé sans re-upload.
8. Clé invalide → « Génération impossible, réessayez. » + Réessayer.
