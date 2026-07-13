"""Scheduled maintenance and cleanup tasks."""

from __future__ import annotations

import logging
from datetime import timedelta

from celery import shared_task
from django.utils import timezone

logger = logging.getLogger("duo.celery")

DEVICE_TOKEN_INACTIVE_DAYS = 90
PUSH_LOG_RETENTION_DAYS = 60
EMAIL_LOG_RETENTION_DAYS = 90


@shared_task(name="duo_project.tasks.maintenance.cleanup_inactive_device_tokens")
def cleanup_inactive_device_tokens() -> int:
    from notifications.models import DeviceToken

    cutoff = timezone.now() - timedelta(days=DEVICE_TOKEN_INACTIVE_DAYS)
    deleted, _ = DeviceToken.objects.filter(is_active=False, updated_at__lt=cutoff).delete()
    logger.info("maintenance_cleanup_inactive_device_tokens deleted=%s", deleted)
    return deleted


@shared_task(name="duo_project.tasks.maintenance.cleanup_old_push_delivery_logs")
def cleanup_old_push_delivery_logs() -> int:
    from notifications.models import PushDeliveryLog

    cutoff = timezone.now() - timedelta(days=PUSH_LOG_RETENTION_DAYS)
    deleted, _ = PushDeliveryLog.objects.filter(created_at__lt=cutoff).delete()
    logger.info("maintenance_cleanup_push_logs deleted=%s", deleted)
    return deleted


@shared_task(name="duo_project.tasks.maintenance.cleanup_old_email_logs")
def cleanup_old_email_logs() -> int:
    from email_service.models import EmailLog

    cutoff = timezone.now() - timedelta(days=EMAIL_LOG_RETENTION_DAYS)
    deleted, _ = EmailLog.objects.filter(created_at__lt=cutoff).delete()
    logger.info("maintenance_cleanup_email_logs deleted=%s", deleted)
    return deleted


@shared_task(name="duo_project.tasks.maintenance.notify_expiring_subscriptions")
def notify_expiring_subscriptions() -> int:
    """Notify users whose premium subscription expires within 3 days."""
    from subscriptions.models import SubscriptionPayment

    now = timezone.now()
    window_end = now + timedelta(days=3)
    seen_users: set[int] = set()
    notified = 0
    for payment in SubscriptionPayment.objects.filter(
        status=SubscriptionPayment.STATUS_COMPLETE,
        expires_at__gt=now,
        expires_at__lte=window_end,
    ).select_related("user"):
        if payment.user_id in seen_users:
            continue
        seen_users.add(payment.user_id)
        days_left = max(1, (payment.expires_at - now).days)
        from duo_project.tasks.enqueue import safe_delay
        from notifications.tasks import send_verification_update_push_task

        safe_delay(
            send_verification_update_push_task,
            payment.user_id,
            "Premium expiring soon",
            (
                f"Your Duo Premium subscription expires in {days_left} day(s). "
                "Renew to keep premium features."
            ),
        )
        notified += 1

    logger.info("maintenance_notify_expiring_subscriptions notified=%s", notified)
    return notified


@shared_task(name="duo_project.tasks.maintenance.process_expired_subscriptions")
def process_expired_subscriptions() -> int:
    """Log expired subscriptions for observability (premium access is time-gated at read time)."""
    from subscriptions.models import SubscriptionPayment

    now = timezone.now()
    count = SubscriptionPayment.objects.filter(
        status=SubscriptionPayment.STATUS_COMPLETE,
        expires_at__lte=now,
    ).count()
    logger.info("maintenance_expired_subscriptions count=%s", count)
    return count


@shared_task(name="duo_project.tasks.maintenance.prune_expired_jwt_blacklist")
def prune_expired_jwt_blacklist() -> int:
    from rest_framework_simplejwt.token_blacklist.models import BlacklistedToken, OutstandingToken

    now = timezone.now()
    blacklisted, _ = BlacklistedToken.objects.filter(token__expires_at__lt=now).delete()
    outstanding, _ = OutstandingToken.objects.filter(expires_at__lt=now).delete()
    total = blacklisted + outstanding
    logger.info("maintenance_prune_jwt_blacklist deleted=%s", total)
    return total
