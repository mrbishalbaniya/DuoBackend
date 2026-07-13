# Celery async task architecture

Duo uses **Celery** with **Redis** as the message broker and **django-celery-results** for durable task status in PostgreSQL.

## Quick start (local)

```bash
pip install -r requirements-prod.txt
export REDIS_URL=redis://127.0.0.1:6379/0
export CELERY_ENABLED=true
export CELERY_TASK_EAGER=false

# Terminal 1 — Django / Daphne
python manage.py migrate
daphne -b 0.0.0.0 -p 8000 duo_project.asgi:application

# Terminal 2 — worker
celery -A duo_project worker -l info

# Terminal 3 — beat (scheduled jobs)
celery -A duo_project beat -l info
```

### Dev without workers

Set `CELERY_TASK_EAGER=true` (default when `CELERY_ENABLED=false`). Tasks run synchronously in the web process — APIs remain compatible.

## Environment variables

| Variable | Default | Description |
|----------|---------|-------------|
| `CELERY_ENABLED` | `true` when `REDIS_URL` set | Enable async dispatch |
| `CELERY_TASK_EAGER` | inverse of `CELERY_ENABLED` | Run tasks in-process (dev) |
| `CELERY_BROKER_URL` | Redis DB `1` derived from `REDIS_URL` | Message broker |
| `CELERY_RESULT_BACKEND` | `django-db` | Task results stored in DB |
| `CELERY_TASK_TIME_LIMIT` | `300` | Hard kill (seconds) |
| `CELERY_TASK_SOFT_TIME_LIMIT` | `240` | Soft limit (seconds) |

## Architecture

```
HTTP / WebSocket request
  → View returns immediately
  → safe_delay(celery_task, …)
       ├─ Celery worker (production)
       └─ Daemon thread fallback (broker down)

Beat scheduler → maintenance tasks (cleanup, subscription checks)
```

## Background tasks

| Task | Module | Trigger |
|------|--------|---------|
| `send_email_task` | `duo_project.tasks.email` | OTP, password reset, 2FA, handoff |
| `send_*_push_task` | `notifications.tasks` | Chat, match, like, payment, etc. |
| `create_photo_embedding_task` | `duo_project.tasks.verification` | Photo upload approved |
| Maintenance cleanup / subscription | `duo_project.tasks.maintenance` | Celery Beat |

## Scheduled jobs (Beat)

| Schedule | Task |
|----------|------|
| Daily 03:15 | Cleanup inactive device tokens (90d) |
| Daily 03:45 | Cleanup push delivery logs (60d) |
| Daily 04:00 | Cleanup email logs (90d) |
| Daily 04:30 | Prune expired JWT blacklist rows |
| Daily 02:30 | Log expired subscriptions |
| Daily 09:00 | Notify users with premium expiring in 3 days |

## Retry policy

Network-oriented tasks (`email`, `notifications`, `verification`) use exponential backoff with jitter:

- **Max retries:** 5
- **Backoff max:** 300s
- **Retried exceptions:** `ConnectionError`, `TimeoutError`, `OSError`, `requests.RequestException`

Email delivery also retries internally (3 attempts per provider) before Celery retry.

## Admin observability

- **Django Admin → Task results** (`django_celery_results.TaskResult`)
  - View status, traceback, args
  - **Retry selected failed tasks** admin action
- **Analytics system health** includes Celery worker count and recent failures
- **Push delivery logs** and **Email logs** remain in their respective admin sections

## Production (Render)

`render.yaml` defines:

- `duo-celery-worker` — `celery -A duo_project worker`
- `duo-celery-beat` — `celery -A duo_project beat`

Run `python manage.py migrate` on the web service to create `django_celery_results` tables.

## API compatibility

- All REST and WebSocket response shapes are unchanged
- Clients receive the same payloads; heavy work runs after the response
- When Celery is unavailable, thread fallback preserves delivery attempts
