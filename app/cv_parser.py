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
