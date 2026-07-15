from django.db import models
from django.contrib.auth.models import User


class Swipe(models.Model):
    ACTION_CHOICES = [('LIKE', 'Like'), ('SKIP', 'Skip'), ('SUPERLIKE', 'Super Like')]

    from_user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='swipes_made')
    to_user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='swipes_received')
    action = models.CharField(max_length=10, choices=ACTION_CHOICES)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('from_user', 'to_user')
        indexes = [
            models.Index(fields=["from_user", "-created_at"], name="swipe_from_created_idx"),
            models.Index(fields=["to_user", "action", "-created_at"], name="swipe_to_action_idx"),
        ]

    def __str__(self):
        return f"{self.from_user.username} → {self.action} → {self.to_user.username}"


class Match(models.Model):
    user1 = models.ForeignKey(User, on_delete=models.CASCADE, related_name='matches_as_user1')
    user2 = models.ForeignKey(User, on_delete=models.CASCADE, related_name='matches_as_user2')
    compatibility_score = models.IntegerField(default=0)
    matched_at = models.DateTimeField(auto_now_add=True)

    # Detailed compatibility breakdown
    values_score = models.IntegerField(default=0)
    lifestyle_score = models.IntegerField(default=0)
    career_score = models.IntegerField(default=0)
    hobbies_score = models.IntegerField(default=0)
    spark_factors = models.JSONField(default=list, blank=True)
    shared_interests = models.JSONField(default=list, blank=True)
    vision_insight = models.TextField(blank=True)
    communication_insight = models.TextField(blank=True)

    class Meta:
        verbose_name = "match"
        verbose_name_plural = "matches"
        unique_together = ('user1', 'user2')
        indexes = [
            models.Index(fields=["-matched_at"], name="match_matched_at_idx"),
        ]

    def get_other_user(self, user):
        return self.user2 if self.user1 == user else self.user1

    def __str__(self):
        return f"Match: {self.user1.username} ❤ {self.user2.username} ({self.compatibility_score}%)"


class ProfileVisit(models.Model):
    """Someone viewed another user's profile (Discover detail, profile page, etc.)."""

    viewer = models.ForeignKey(User, on_delete=models.CASCADE, related_name="profile_visits_made")
    viewed_user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="profile_visits_received"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    last_visited_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("viewer", "viewed_user")
        ordering = ["-last_visited_at"]
        indexes = [
            models.Index(fields=["viewed_user", "-last_visited_at"]),
        ]

    def __str__(self):
        return f"{self.viewer.username} viewed {self.viewed_user.username}"
