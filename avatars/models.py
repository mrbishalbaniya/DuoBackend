from django.conf import settings
from django.db import models


class AvatarConfig(models.Model):
    """Saved procedural 3D avatar configuration for a user."""

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="avatar_config",
    )
    config = models.JSONField(default=dict, blank=True)
    version = models.PositiveSmallIntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Avatar config"
        verbose_name_plural = "Avatar configs"

    def __str__(self):
        return f"Avatar for {self.user_id}"


class AvatarOutfit(models.Model):
    """Named outfit preset saved by a user."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="avatar_outfits",
    )
    name = models.CharField(max_length=80)
    config = models.JSONField(default=dict, blank=True)
    is_favorite = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at"]
        unique_together = ("user", "name")

    def __str__(self):
        return f"{self.name} ({self.user_id})"
