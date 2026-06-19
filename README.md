# DuoBackend

Django REST API and WebSocket backend for **Duo** — accounts, matching, and real-time chat.

## Project layout

```
DuoBackend/
  accounts/          Django app
  chat/              Django app
  matching/          Django app
  duo_project/       Django settings & URLs
  media/             Uploaded files
  scripts/           Setup, run, and seed utilities
  manage.py
  requirements.txt
```

## Setup

```powershell
cd d:\8sem\DuoBackend
.\scripts\install-deps.ps1
.\venv\Scripts\python.exe manage.py migrate
```

## Run server

```powershell
.\scripts\run-server.ps1
```

Server: http://localhost:8001/api

## Utility scripts

| Script | Purpose |
|--------|---------|
| `scripts\run-server.ps1` | Start dev server on port 8001 |
| `scripts\install-deps.ps1` | Install Python dependencies into `venv` |
| `scripts\setup_project.ps1` | Create venv, install deps, run migrations |
| `scripts\run_seed_random_users.py` | Seed demo users |
| `scripts\run_seed_profile_photos.py` | Seed profile photos |
| `scripts\reset_demo_password.py` | Reset demo user password |

Windows setup guides live in `scripts\docs\`.
