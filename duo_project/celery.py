"""Celery application for Duo backend."""

from __future__ import annotations

import os

from celery import Celery
from celery.schedules import crontab

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "duo_project.settings")

app = Celery("duo")

app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()

app.conf.beat_schedule = {
    "maintenance-cleanup-inactive-device-tokens": {
        "task": "duo_project.tasks.maintenance.cleanup_inactive_device_tokens",
        "schedule": crontab(hour=3, minute=15),
    },
    "maintenance-cleanup-push-delivery-logs": {
        "task": "duo_project.tasks.maintenance.cleanup_old_push_delivery_logs",
        "schedule": crontab(hour=3, minute=45),
    },
    "maintenance-cleanup-stale-email-logs": {
        "task": "duo_project.tasks.maintenance.cleanup_old_email_logs",
        "schedule": crontab(hour=4, minute=0),
    },
    "maintenance-check-expiring-subscriptions": {
        "task": "duo_project.tasks.maintenance.notify_expiring_subscriptions",
        "schedule": crontab(hour=9, minute=0),
    },
    "maintenance-check-expired-subscriptions": {
        "task": "duo_project.tasks.maintenance.process_expired_subscriptions",
        "schedule": crontab(hour=2, minute=30),
    },
    "maintenance-prune-token-blacklist": {
        "task": "duo_project.tasks.maintenance.prune_expired_jwt_blacklist",
        "schedule": crontab(hour=4, minute=30),
    },
}
