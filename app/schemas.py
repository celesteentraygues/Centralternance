from typing import Literal

from pydantic import BaseModel, Field, model_validator

from app.config import (
    MAX_CONTACT_FIELD_CHARS,
    MAX_CV_CHARS,
    MAX_MODELE_CHARS,
    MAX_OFFRE_CHARS,
)


class BlocCS(BaseModel):
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
