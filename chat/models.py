from django.db import models
from django.contrib.auth.models import User
from matching.models import Match


class Conversation(models.Model):
    match = models.OneToOneField(Match, on_delete=models.CASCADE, related_name='conversation')
    user1_last_typed = models.DateTimeField(null=True, blank=True)
    user2_last_typed = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Conversation for {self.match}"

    def get_other_user(self, user):
        return self.match.get_other_user(user)


class ConversationPreference(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='conversation_preferences')
    conversation = models.ForeignKey(
        Conversation,
        on_delete=models.CASCADE,
        related_name='preferences',
    )
    nickname = models.CharField(max_length=64, blank=True, default='')
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('user', 'conversation')

    def __str__(self):
        return f"{self.user_id} nickname for conversation {self.conversation_id}"


class UserBlock(models.Model):
    blocker = models.ForeignKey(User, on_delete=models.CASCADE, related_name='blocks_made')
    blocked = models.ForeignKey(User, on_delete=models.CASCADE, related_name='blocks_received')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('blocker', 'blocked')

    def __str__(self):
        return f"{self.blocker_id} blocked {self.blocked_id}"


class UserReport(models.Model):
    reporter = models.ForeignKey(User, on_delete=models.CASCADE, related_name='reports_made')
    reported = models.ForeignKey(User, on_delete=models.CASCADE, related_name='reports_received')
    conversation = models.ForeignKey(
        Conversation,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='reports',
    )
    reason = models.TextField(blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Report {self.reporter_id} -> {self.reported_id}"


class Message(models.Model):
    conversation = models.ForeignKey(Conversation, on_delete=models.CASCADE, related_name='messages')
    sender = models.ForeignKey(User, on_delete=models.CASCADE)
    content = models.TextField(blank=True)
    image_url = models.CharField(max_length=1000, blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)
    is_read = models.BooleanField(default=False)
    
    # Deletion flags
    is_deleted_for_everyone = models.BooleanField(default=False)
    deleted_by = models.ManyToManyField(User, related_name='deleted_messages', blank=True)

    class Meta:
        ordering = ['timestamp']

    def __str__(self):
        if self.is_deleted_for_everyone:
            return f"Deleted message by {self.sender.username}"
        return f"{self.sender.username}: {self.content[:50]}"


class MessageReaction(models.Model):
    message = models.ForeignKey(Message, on_delete=models.CASCADE, related_name='reactions')
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    emoji = models.CharField(max_length=20)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('message', 'user', 'emoji')

    def __str__(self):
        return f"{self.user.username} reacted {self.emoji} to message {self.message.id}"
