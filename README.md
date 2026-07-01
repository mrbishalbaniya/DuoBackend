# DuoBackend

[![Backend CI/CD](https://github.com/mrbishalbaniya/DuoBackend/actions/workflows/ci.yml/badge.svg)](https://github.com/mrbishalbaniya/DuoBackend/actions/workflows/ci.yml)

Django REST API and WebSocket backend for **Duo** — accounts, matching, and real-time chat.

## Project layout

```
DuoBackend/
  accounts/          Django app
  chat/              Django app
  matching/          Django app
  duo_project/       Django settings & URLs
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
cd d:\8sem\DuoBackend
python manage.py runserver 8001
```

In a **new external terminal**, activate the venv once per session:

```powershell
.\activate.ps1
python manage.py runserver 8001
```

Or use the helper script:

```powershell
.\runserver.ps1
```

## Cloudinary (required for uploads)

Profile photos and chat media upload to [Cloudinary](https://cloudinary.com/). Copy `.env.example` to `.env` and set:

```
CLOUDINARY_CLOUD_NAME=
CLOUDINARY_API_KEY=
CLOUDINARY_API_SECRET=
```

Optional folders (defaults shown):

```
CLOUDINARY_PROFILE_FOLDER=duo/profile_photos
CLOUDINARY_CHAT_FOLDER=duo/chat_media
```

Local `DuoBackend/media/` is not used for user uploads.

## CI/CD

GitHub Actions runs on every push and pull request to `main`:

| Workflow | File | What it does |
|----------|------|--------------|
| **CI/CD** | `.github/workflows/ci.yml` | CI tests + optional Render deploy hook on push to `main` |

### Deploy backend (Render)

1. Push this repo to GitHub.
2. In [Render](https://render.com), create a **Blueprint** from `render.yaml` (or create a Web Service manually).
3. Set environment variables from `.env.example` (Cloudinary, Google OAuth, `FRONTEND_URL`, `CORS_ALLOWED_ORIGINS`, etc.).
4. Copy the service **Deploy Hook** URL from Render → Settings → Deploy Hook.
5. Add it as `RENDER_DEPLOY_HOOK_URL` in GitHub → Settings → Secrets → Actions.

Alternatively, connect the GitHub repo directly in Render for automatic deploys without the hook.

### Docker

```bash
docker build -t duo-backend .
docker run -p 8000:8000 --env-file .env duo-backend
```

Production expects `DATABASE_URL` (PostgreSQL) and `DEBUG=False`. SQLite is used when `DATABASE_URL` is unset.

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
