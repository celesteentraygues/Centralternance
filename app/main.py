from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.config import STATIC_DIR

app = FastAPI(title="Centralternance")

# Les routes API seront ajoutées avant ce montage (Task 6).
app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="static")
