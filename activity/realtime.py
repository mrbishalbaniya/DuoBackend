"""Broadcast activity zone updates to connected map clients."""

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer

ACTIVITY_GROUP = "activity_feed"


def broadcast_activity_refresh():
    channel_layer = get_channel_layer()
    if not channel_layer:
        return
    async_to_sync(channel_layer.group_send)(
        ACTIVITY_GROUP,
        {"type": "activity.refresh"},
    )
