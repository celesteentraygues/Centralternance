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
