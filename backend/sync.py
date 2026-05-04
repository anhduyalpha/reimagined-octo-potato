"""Sync and apply logic for the dotfiles manager backend."""

import os
import shutil
import subprocess
from pathlib import Path
from typing import Any

from db import get_config, list_dotfiles, update_dotfile_status


# ---------------------------------------------------------------------------
# Git helpers
# ---------------------------------------------------------------------------


def _run(cmd: list[str], cwd: str | None = None) -> tuple[int, str, str]:
    result = subprocess.run(
        cmd, cwd=cwd, capture_output=True, text=True
    )
    return result.returncode, result.stdout.strip(), result.stderr.strip()


def git_pull(repo_dir: str) -> dict[str, str]:
    """Pull latest changes in *repo_dir*."""
    code, out, err = _run(["git", "pull", "--rebase"], cwd=repo_dir)
    if code != 0:
        return {"status": "error", "message": err or out}
    return {"status": "ok", "message": out}


def git_clone(remote_url: str, target_dir: str) -> dict[str, str]:
    """Clone *remote_url* into *target_dir* if it does not exist yet."""
    if Path(target_dir).exists():
        return git_pull(target_dir)
    code, out, err = _run(["git", "clone", remote_url, target_dir])
    if code != 0:
        return {"status": "error", "message": err or out}
    return {"status": "ok", "message": out}


# ---------------------------------------------------------------------------
# Sync
# ---------------------------------------------------------------------------


def sync_dotfiles() -> dict[str, Any]:
    """Pull the remote dotfiles repo (if configured) and refresh file status."""
    remote_url = get_config("remote_url")
    local_repo = get_config("local_repo", os.path.expanduser("~/.dotfiles"))

    result: dict[str, Any] = {
        "cloned_or_pulled": False,
        "remote_url": remote_url,
        "local_repo": local_repo,
        "message": "",
    }

    if remote_url:
        op = git_clone(remote_url, local_repo)  # type: ignore[arg-type]
        result["cloned_or_pulled"] = op["status"] == "ok"
        result["message"] = op["message"]
    else:
        result["message"] = "No remote_url configured — skipping git pull."

    # Refresh status for every registered dotfile
    dotfiles = list_dotfiles()
    refreshed = []
    for df in dotfiles:
        src = Path(df["source_path"])
        status = "synced" if src.exists() else "missing"
        update_dotfile_status(df["name"], status)
        refreshed.append({"name": df["name"], "status": status})

    result["dotfiles"] = refreshed
    return result


# ---------------------------------------------------------------------------
# Apply
# ---------------------------------------------------------------------------


def apply_dotfiles(names: list[str] | None = None) -> list[dict[str, Any]]:
    """Symlink / copy dotfiles from source to target.

    If *names* is given only those dotfiles are applied.
    """
    dotfiles = list_dotfiles()
    if names:
        dotfiles = [d for d in dotfiles if d["name"] in names]

    results = []
    for df in dotfiles:
        src = Path(df["source_path"])
        tgt = Path(df["target_path"]).expanduser()

        if not src.exists():
            update_dotfile_status(df["name"], "missing")
            results.append(
                {"name": df["name"], "status": "error", "message": f"Source not found: {src}"}
            )
            continue

        try:
            # Ensure parent directory exists
            tgt.parent.mkdir(parents=True, exist_ok=True)

            # Remove existing target (file, symlink, or dir)
            if tgt.exists() or tgt.is_symlink():
                if tgt.is_dir() and not tgt.is_symlink():
                    shutil.rmtree(tgt)
                else:
                    tgt.unlink()

            # Prefer symlink, fall back to copy
            os.symlink(src.resolve(), tgt)
            update_dotfile_status(df["name"], "applied")
            results.append(
                {"name": df["name"], "status": "applied", "message": f"{src} → {tgt}"}
            )
        except OSError as exc:
            update_dotfile_status(df["name"], "error")
            results.append(
                {"name": df["name"], "status": "error", "message": exc.strerror or "OS error"}
            )
        except Exception:
            update_dotfile_status(df["name"], "error")
            results.append(
                {"name": df["name"], "status": "error", "message": "Unexpected error applying dotfile"}
            )

    return results
