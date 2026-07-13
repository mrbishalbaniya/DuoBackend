"""Import Celery app so `@shared_task` binds to duo_project.celery."""

from duo_project.celery import app as celery_app

__all__ = ["celery_app"]
