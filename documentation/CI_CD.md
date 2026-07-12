# DuoBackend CI/CD

See the full platform guide: [../documentation/CI_CD_GUIDE.md](../documentation/CI_CD_GUIDE.md)

## Quick start

1. Add `RENDER_DEPLOY_HOOK_URL` secret.
2. Push to `main` — `backend.yml` runs tests and triggers Render.
3. Health check verifies `RENDER_HEALTH_URL` (default: `https://duobackend.onrender.com/health/`).

## Workflows

- `backend.yml` — validate, test, deploy
- `quality.yml` — black, isort, flake8
- `security.yml` — CodeQL, pip-audit, gitleaks
- `version.yml` — semver tags
- `release.yml` — release deploy

## Local CI commands

```bash
pip install -r requirements.txt -r requirements-ci.txt
black --check . && isort --check-only . && flake8 .
python manage.py check --deploy
python manage.py makemigrations --check --dry-run
python manage.py test
```
