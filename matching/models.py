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
        unique_together = ('user1', 'user2')

    def get_other_user(self, user):
        return self.user2 if self.user1 == user else self.user1

    def __str__(self):
        return f"Match: {self.user1.username} ❤ {self.user2.username} ({self.compatibility_score}%)"
