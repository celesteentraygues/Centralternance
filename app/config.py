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
