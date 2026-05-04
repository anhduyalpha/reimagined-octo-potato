"""Tests for the Dotfiles Manager backend."""

import os
import sys
import tempfile

import pytest

# Use a temp DB so tests are isolated and don't touch the real dotfiles.db
_tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
_tmp.close()
_TEST_DB = _tmp.name

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# Patch DB_PATH before any backend module imports so every module uses the test DB
import db as db_module  # noqa: E402

db_module.DB_PATH = _TEST_DB  # type: ignore[assignment]

import db  # noqa: E402
import sync as sync_module  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
import app as app_module  # noqa: E402

client = TestClient(app_module.app)


@pytest.fixture(autouse=True)
def fresh_db():
    """Re-initialise DB and wipe all rows between tests."""
    db.init_db()
    with db.get_connection() as conn:
        conn.execute("DELETE FROM dotfiles")
        conn.execute("DELETE FROM config")
        conn.commit()
    yield


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------


def test_health():
    resp = client.get("/api/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


# ---------------------------------------------------------------------------
# Dotfiles CRUD
# ---------------------------------------------------------------------------


def test_list_empty():
    resp = client.get("/api/dotfiles")
    assert resp.status_code == 200
    assert resp.json() == []


def test_add_and_list():
    body = {"name": "vimrc", "source_path": "/dots/vimrc", "target_path": "~/.vimrc"}
    resp = client.post("/api/dotfiles", json=body)
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "vimrc"
    assert data["status"] == "pending"

    resp2 = client.get("/api/dotfiles")
    assert len(resp2.json()) == 1


def test_get_single():
    client.post("/api/dotfiles", json={"name": "bashrc", "source_path": "/d/bashrc", "target_path": "~/.bashrc"})
    resp = client.get("/api/dotfiles/bashrc")
    assert resp.status_code == 200
    assert resp.json()["name"] == "bashrc"


def test_get_missing():
    resp = client.get("/api/dotfiles/nope")
    assert resp.status_code == 404


def test_duplicate_add():
    body = {"name": "vimrc", "source_path": "/a", "target_path": "/b"}
    client.post("/api/dotfiles", json=body)
    resp = client.post("/api/dotfiles", json=body)
    assert resp.status_code == 409


def test_remove():
    client.post("/api/dotfiles", json={"name": "zshrc", "source_path": "/a", "target_path": "/b"})
    resp = client.delete("/api/dotfiles/zshrc")
    assert resp.status_code == 200
    assert client.get("/api/dotfiles/zshrc").status_code == 404


def test_remove_missing():
    resp = client.delete("/api/dotfiles/ghost")
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------


def test_config_empty():
    resp = client.get("/api/config")
    assert resp.status_code == 200
    assert resp.json() == {}


def test_config_set_and_get():
    client.post("/api/config", json={"key": "remote_url", "value": "https://github.com/x/dots.git"})
    resp = client.get("/api/config")
    assert resp.json()["remote_url"] == "https://github.com/x/dots.git"


# ---------------------------------------------------------------------------
# Sync — no remote
# ---------------------------------------------------------------------------


def test_sync_no_remote():
    client.post("/api/dotfiles", json={"name": "vimrc", "source_path": "/nonexistent/vimrc", "target_path": "~/.vimrc"})
    resp = client.post("/api/sync")
    assert resp.status_code == 200
    result = resp.json()
    # Without remote_url it should still refresh status
    assert "dotfiles" in result
    df_status = {d["name"]: d["status"] for d in result["dotfiles"]}
    assert df_status["vimrc"] == "missing"


# ---------------------------------------------------------------------------
# Apply — real file
# ---------------------------------------------------------------------------


def test_apply_real_file(tmp_path):
    src = tmp_path / "vimrc"
    src.write_text("set number\n")
    tgt = tmp_path / "link_vimrc"

    client.post("/api/dotfiles", json={
        "name": "vimrc",
        "source_path": str(src),
        "target_path": str(tgt),
    })

    resp = client.post("/api/apply", json={})
    assert resp.status_code == 200
    results = resp.json()
    assert results[0]["status"] == "applied"
    assert tgt.is_symlink()
    assert tgt.read_text() == "set number\n"


def test_apply_missing_source(tmp_path):
    tgt = tmp_path / "missing_link"
    client.post("/api/dotfiles", json={
        "name": "ghostrc",
        "source_path": str(tmp_path / "does_not_exist"),
        "target_path": str(tgt),
    })
    resp = client.post("/api/apply", json={})
    assert resp.status_code == 200
    results = resp.json()
    assert results[0]["status"] == "error"
