"""Import Celery app so `@shared_task` binds to duo_project.celery."""

try:
    from duo_project.celery import app as celery_app
    __all__ = ["celery_app"]
except ImportError:
    # Celery is optional - server can run without it
    celery_app = None
    __all__ = []

