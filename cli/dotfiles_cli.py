#!/usr/bin/env python3
"""
dotfiles — CLI tool for managing and syncing dotfiles.

Usage examples
--------------
  dotfiles list
  dotfiles add vimrc ~/.dotfiles/vimrc ~/.vimrc
  dotfiles remove vimrc
  dotfiles pull
  dotfiles apply
  dotfiles apply vimrc bashrc
  dotfiles status
  dotfiles config set remote_url https://github.com/user/dots.git
  dotfiles config set local_repo ~/.dotfiles
  dotfiles config list
"""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime
from typing import Any

import click
import requests

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

DEFAULT_API = os.environ.get("DOTFILES_API", "http://localhost:8000")


def _api(path: str, method: str = "GET", **kwargs: Any) -> Any:
    url = DEFAULT_API.rstrip("/") + path
    try:
        resp = requests.request(method, url, timeout=15, **kwargs)
        resp.raise_for_status()
        return resp.json()
    except requests.exceptions.ConnectionError:
        click.secho(
            f"✗  Cannot connect to the backend at {DEFAULT_API}.\n"
            "   Start it with: uvicorn app:app --app-dir backend",
            fg="red",
            err=True,
        )
        sys.exit(1)
    except requests.exceptions.HTTPError as exc:
        try:
            detail = exc.response.json().get("detail", str(exc))
        except Exception:
            detail = str(exc)
        click.secho(f"✗  API error: {detail}", fg="red", err=True)
        sys.exit(1)


# ---------------------------------------------------------------------------
# Formatting helpers
# ---------------------------------------------------------------------------

STATUS_COLORS = {
    "applied": "green",
    "synced":  "cyan",
    "missing": "red",
    "error":   "red",
    "pending": "yellow",
}

STATUS_ICONS = {
    "applied": "✓",
    "synced":  "⟳",
    "missing": "✗",
    "error":   "!",
    "pending": "…",
}


def _fmt_status(status: str) -> str:
    icon  = STATUS_ICONS.get(status, "?")
    color = STATUS_COLORS.get(status, "white")
    return click.style(f"{icon} {status}", fg=color)


def _fmt_ts(ts: float | None) -> str:
    if ts is None:
        return "—"
    return datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M:%S")


# ---------------------------------------------------------------------------
# CLI root
# ---------------------------------------------------------------------------


@click.group()
@click.version_option("1.0.0", prog_name="dotfiles")
def cli() -> None:
    """Dotfiles Manager CLI — manage and sync your dotfiles."""


# ---------------------------------------------------------------------------
# list
# ---------------------------------------------------------------------------


@cli.command("list")
def list_cmd() -> None:
    """List all registered dotfiles."""
    data = _api("/api/dotfiles")
    if not data:
        click.echo("No dotfiles registered. Use 'dotfiles add' to add one.")
        return
    click.echo(f"\n{'NAME':<20} {'STATUS':<10} {'SOURCE':<40} {'TARGET':<30} {'SYNCED'}")
    click.echo("─" * 120)
    for df in data:
        # Build the plain-text status first so format width is predictable,
        # then apply colour separately to avoid ANSI escape codes distorting alignment.
        status_plain = f"{STATUS_ICONS.get(df['status'], '?')} {df['status']}"
        status_colored = click.style(status_plain, fg=STATUS_COLORS.get(df["status"], "white"))
        click.echo(
            f"{df['name']:<20} "
            f"{status_colored:<10} "
            f"{df['source_path']:<40} "
            f"{df['target_path']:<30} "
            f"{_fmt_ts(df.get('synced_at'))}"
        )
    click.echo()


# ---------------------------------------------------------------------------
# add
# ---------------------------------------------------------------------------


@cli.command()
@click.argument("name")
@click.argument("source")
@click.argument("target")
def add(name: str, source: str, target: str) -> None:
    """Register a new dotfile.

    \b
    NAME    — short identifier (e.g. vimrc)
    SOURCE  — path to the dotfile in your dotfiles repo
    TARGET  — where it should be linked/applied (e.g. ~/.vimrc)
    """
    df = _api(
        "/api/dotfiles",
        method="POST",
        json={"name": name, "source_path": source, "target_path": target},
    )
    click.secho(f"✓  Added '{df['name']}'  ({df['source_path']} → {df['target_path']})", fg="green")


# ---------------------------------------------------------------------------
# remove
# ---------------------------------------------------------------------------


@cli.command()
@click.argument("name")
@click.confirmation_option(prompt="Are you sure you want to remove this dotfile?")
def remove(name: str) -> None:
    """Remove a registered dotfile by NAME."""
    _api(f"/api/dotfiles/{name}", method="DELETE")
    click.secho(f"✓  Removed '{name}'", fg="yellow")


# ---------------------------------------------------------------------------
# pull  (wraps /api/sync)
# ---------------------------------------------------------------------------


@cli.command()
def pull() -> None:
    """Pull latest dotfiles from the remote repository and refresh status."""
    click.echo("Pulling…")
    result = _api("/api/sync", method="POST")
    msg = result.get("message") or ""
    if msg:
        click.echo(f"  git: {msg}")
    for df in result.get("dotfiles", []):
        status_str = _fmt_status(df["status"])
        click.echo(f"  {df['name']:<25} {status_str}")
    click.secho("✓  Sync complete.", fg="green")


# ---------------------------------------------------------------------------
# apply
# ---------------------------------------------------------------------------


@cli.command()
@click.argument("names", nargs=-1)
def apply(names: tuple[str, ...]) -> None:
    """Symlink dotfiles to their target paths.

    Optionally specify one or more NAME(s); defaults to applying all.
    """
    payload: dict[str, Any] = {}
    if names:
        payload["names"] = list(names)
    results = _api("/api/apply", method="POST", json=payload)
    for r in results:
        color = "green" if r["status"] == "applied" else "red"
        click.secho(f"  {r['name']:<25} {r['status']:<10}  {r['message']}", fg=color)
    applied = sum(1 for r in results if r["status"] == "applied")
    click.echo(f"\n{applied}/{len(results)} applied.")


# ---------------------------------------------------------------------------
# status
# ---------------------------------------------------------------------------


@cli.command()
def status() -> None:
    """Show a summary of dotfile status."""
    data = _api("/api/dotfiles")
    counts: dict[str, int] = {}
    for df in data:
        counts[df["status"]] = counts.get(df["status"], 0) + 1
    click.echo("\nStatus summary:")
    for st, n in sorted(counts.items()):
        click.echo(f"  {_fmt_status(st):<22}  {n}")
    click.echo(f"\nTotal: {len(data)}")
    click.echo()


# ---------------------------------------------------------------------------
# config
# ---------------------------------------------------------------------------


@cli.group()
def config() -> None:
    """Get or set backend configuration values."""


@config.command("set")
@click.argument("key")
@click.argument("value")
def config_set(key: str, value: str) -> None:
    """Set a configuration KEY to VALUE."""
    _api("/api/config", method="POST", json={"key": key, "value": value})
    click.secho(f"✓  {key} = {value}", fg="green")


@config.command("list")
def config_list() -> None:
    """List all configuration values."""
    cfg = _api("/api/config")
    if not cfg:
        click.echo("No configuration set.")
        return
    click.echo()
    for k, v in cfg.items():
        click.echo(f"  {k:<25}  {v}")
    click.echo()


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    cli()
