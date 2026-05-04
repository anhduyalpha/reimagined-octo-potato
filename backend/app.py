"""FastAPI backend for the Dotfiles Manager."""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Any, AsyncGenerator

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pathlib import Path
from pydantic import BaseModel

import db
import sync as sync_module

# ---------------------------------------------------------------------------
# Initialise
# ---------------------------------------------------------------------------

_dashboard_dir = Path(__file__).parent.parent / "dashboard"


@asynccontextmanager
async def lifespan(application: FastAPI) -> AsyncGenerator[None, None]:
    db.init_db()
    yield


app = FastAPI(title="Dotfiles Manager", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve the web dashboard from ../dashboard
if _dashboard_dir.exists():
    app.mount("/static", StaticFiles(directory=str(_dashboard_dir)), name="static")


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------


class DotfileIn(BaseModel):
    name: str
    source_path: str
    target_path: str


class ConfigIn(BaseModel):
    key: str
    value: str


class ApplyIn(BaseModel):
    names: list[str] | None = None


# ---------------------------------------------------------------------------
# Routes — dashboard
# ---------------------------------------------------------------------------


@app.get("/", include_in_schema=False)
def serve_dashboard() -> FileResponse:
    index = _dashboard_dir / "index.html"
    if not index.exists():
        raise HTTPException(status_code=404, detail="Dashboard not found.")
    return FileResponse(str(index))


# ---------------------------------------------------------------------------
# Routes — health
# ---------------------------------------------------------------------------


@app.get("/api/health", tags=["health"])
def health() -> dict[str, str]:
    return {"status": "ok"}


# ---------------------------------------------------------------------------
# Routes — dotfiles
# ---------------------------------------------------------------------------


@app.get("/api/dotfiles", tags=["dotfiles"])
def list_dotfiles() -> list[dict[str, Any]]:
    return db.list_dotfiles()


@app.post("/api/dotfiles", tags=["dotfiles"], status_code=201)
def add_dotfile(body: DotfileIn) -> dict[str, Any]:
    existing = db.get_dotfile(body.name)
    if existing:
        raise HTTPException(status_code=409, detail=f"Dotfile '{body.name}' already exists.")
    return db.add_dotfile(body.name, body.source_path, body.target_path)


@app.get("/api/dotfiles/{name}", tags=["dotfiles"])
def get_dotfile(name: str) -> dict[str, Any]:
    row = db.get_dotfile(name)
    if not row:
        raise HTTPException(status_code=404, detail=f"Dotfile '{name}' not found.")
    return row


@app.delete("/api/dotfiles/{name}", tags=["dotfiles"])
def remove_dotfile(name: str) -> dict[str, str]:
    deleted = db.remove_dotfile(name)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Dotfile '{name}' not found.")
    return {"detail": f"Dotfile '{name}' removed."}


# ---------------------------------------------------------------------------
# Routes — sync & apply
# ---------------------------------------------------------------------------


@app.post("/api/sync", tags=["sync"])
def sync_dotfiles() -> dict[str, Any]:
    return sync_module.sync_dotfiles()


@app.post("/api/apply", tags=["sync"])
def apply_dotfiles(body: ApplyIn = ApplyIn()) -> list[dict[str, Any]]:
    return sync_module.apply_dotfiles(body.names)


# ---------------------------------------------------------------------------
# Routes — config
# ---------------------------------------------------------------------------


@app.get("/api/config", tags=["config"])
def get_all_config() -> dict[str, str]:
    return db.list_config()


@app.post("/api/config", tags=["config"])
def set_config(body: ConfigIn) -> dict[str, str]:
    db.set_config(body.key, body.value)
    return {"key": body.key, "value": body.value}
