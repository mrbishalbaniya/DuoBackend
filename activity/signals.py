from django.db.models.signals import post_save
from django.dispatch import receiver

from chat.models import Message
from matching.models import Match, ProfileVisit, Swipe

from .realtime import broadcast_activity_refresh


@receiver(post_save, sender=ProfileVisit)
@receiver(post_save, sender=Swipe)
@receiver(post_save, sender=Match)
@receiver(post_save, sender=Message)
def on_activity_signal(sender, **kwargs):
    broadcast_activity_refresh()
