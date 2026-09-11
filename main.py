import os
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI, File, HTTPException, Request, UploadFile
from fastapi.staticfiles import StaticFiles
from openai import OpenAI
from starlette.concurrency import run_in_threadpool

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
    if file.size is not None and file.size > MAX_PDF_BYTES:
        raise HTTPException(status_code=413, detail=MSG_PDF_TROP_GROS)
    data = await file.read()
    if len(data) > MAX_PDF_BYTES:
        raise HTTPException(status_code=413, detail=MSG_PDF_TROP_GROS)
    try:
        parsed = await run_in_threadpool(cv_parser.extract_text, data)
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
