# reimagined-octo-potato

# Dotfiles Manager

A full-stack dotfiles management system with a Python/FastAPI backend, glassy glassmorphism web dashboard, and a feature-rich CLI tool.

![Dashboard Screenshot](https://github.com/user-attachments/assets/53f2318c-3fae-49d8-aa7e-73fac33b692e)

---

## Features

| Layer | Stack | Highlights |
|---|---|---|
| **Backend** | Python · FastAPI · SQLite | REST API, git sync, symlink apply |
| **Dashboard** | Vanilla JS · CSS glassmorphism | Live stats, add/remove/apply/sync |
| **CLI** | Python · Click | `pull`, `apply`, `list`, `add`, `remove`, `status`, `config` |

---

## Project Layout

```
.
├── backend/
│   ├── app.py            # FastAPI application (REST API + dashboard serving)
│   ├── db.py             # SQLite data layer
│   ├── sync.py           # git pull / symlink apply logic
│   ├── requirements.txt
│   ├── Dockerfile
│   └── test_backend.py   # pytest suite (13 tests)
├── dashboard/
│   ├── index.html        # Single-page app
│   ├── style.css         # Glassmorphism UI
│   └── app.js            # Fetch-based frontend
├── cli/
│   ├── dotfiles_cli.py   # Click CLI tool
│   └── requirements.txt
├── docker-compose.yml
└── README.md
```

---

## Quick Start

### 1 — Backend (serves the dashboard too)

```bash
cd backend
pip install -r requirements.txt
uvicorn app:app --reload
# → http://localhost:8000  (dashboard)
# → http://localhost:8000/docs  (OpenAPI)
```

### 2 — CLI tool

```bash
cd cli
pip install -r requirements.txt

# point at your backend (default: http://localhost:8000)
export DOTFILES_API=http://localhost:8000

python dotfiles_cli.py --help
```

### 3 — Docker Compose

```bash
docker compose up --build
# dashboard → http://localhost:8000
```

---

## REST API

| Method | Path | Description |
|---|---|---|
| `GET` | `/api/health` | Health check |
| `GET` | `/api/dotfiles` | List all dotfiles |
| `POST` | `/api/dotfiles` | Register a dotfile |
| `GET` | `/api/dotfiles/{name}` | Get a single dotfile |
| `DELETE` | `/api/dotfiles/{name}` | Remove a dotfile |
| `POST` | `/api/sync` | Pull remote repo & refresh status |
| `POST` | `/api/apply` | Symlink dotfiles to target paths |
| `GET` | `/api/config` | List config values |
| `POST` | `/api/config` | Set a config value |

Interactive docs at **`/docs`** when the server is running.

---

## CLI Reference

```
dotfiles list                          # list all dotfiles
dotfiles add <name> <source> <target>  # register a new dotfile
dotfiles remove <name>                 # remove a dotfile
dotfiles pull                          # git pull remote repo + refresh status
dotfiles apply [name ...]              # symlink dotfiles to target paths
dotfiles status                        # show status summary
dotfiles config set <key> <value>      # set a config value
dotfiles config list                   # list config values
```

**Key config values**

| Key | Description |
|---|---|
| `remote_url` | Git remote URL to pull from (e.g. `https://github.com/user/dots.git`) |
| `local_repo` | Local path for the cloned repo (default: `~/.dotfiles`) |

**Environment**

| Variable | Default | Description |
|---|---|---|
| `DOTFILES_API` | `http://localhost:8000` | Backend URL used by the CLI |

---

## Running Tests

```bash
cd backend
pip install -r requirements.txt httpx pytest
pytest test_backend.py -v
```

All 13 tests cover: health, CRUD, config, sync (no remote), apply (real file & missing source).
