from django.db.models.signals import post_migrate
from django.dispatch import receiver

from email_service.constants import EmailEvent
from email_service.defaults import ensure_default_templates


@receiver(post_migrate)
def seed_email_defaults(sender, **kwargs):
    if sender.name != "email_service":
        return
    ensure_default_templates()
