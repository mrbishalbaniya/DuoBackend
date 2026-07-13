"""Broadcast activity zone updates to connected map clients."""

from duo_project.realtime.broadcast import broadcast_activity_refresh

ACTIVITY_GROUP = "activity_feed"

__all__ = ["ACTIVITY_GROUP", "broadcast_activity_refresh"]
