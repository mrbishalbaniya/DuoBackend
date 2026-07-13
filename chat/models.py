from django.db import models
from django.contrib.auth.models import User
from matching.models import Match
import secrets


def generate_conversation_public_id() -> str:
    """Return a unique-looking 10-digit public id (1_000_000_000 … 9_999_999_999)."""
    return str(secrets.randbelow(9_000_000_000) + 1_000_000_000)


class Conversation(models.Model):
    match = models.OneToOneField(Match, on_delete=models.CASCADE, related_name='conversation')
    # Stable shareable id used in /chat?conversation=… (never the autoincrement pk).
    public_id = models.CharField(max_length=10, unique=True, db_index=True, editable=False)
    user1_last_typed = models.DateTimeField(null=True, blank=True)
    user2_last_typed = models.DateTimeField(null=True, blank=True)
    last_message_at = models.DateTimeField(null=True, blank=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Conversation for {self.match}"

    def get_other_user(self, user):
        return self.match.get_other_user(user)

    def save(self, *args, **kwargs):
        if not self.public_id:
            for _ in range(20):
                candidate = generate_conversation_public_id()
                if not Conversation.objects.filter(public_id=candidate).exists():
                    self.public_id = candidate
                    break
            else:
                raise RuntimeError("Could not allocate a unique conversation public_id")
        super().save(*args, **kwargs)


class ConversationPreference(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='conversation_preferences')
    conversation = models.ForeignKey(
        Conversation,
        on_delete=models.CASCADE,
        related_name='preferences',
    )
    nickname = models.CharField(max_length=64, blank=True, default='')
    is_archived = models.BooleanField(default=False)
    is_muted = models.BooleanField(default=False)
    is_pinned = models.BooleanField(default=False)
    notify_screenshots = models.BooleanField(default=True)
    secure_chat = models.BooleanField(default=False)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('user', 'conversation')
        indexes = [
            models.Index(fields=["user", "is_archived"], name="convpref_user_arch_idx"),
        ]

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
    MESSAGE_TYPE_TEXT = "text"
    MESSAGE_TYPE_IMAGE = "image"
    MESSAGE_TYPE_VOICE = "voice"
    MESSAGE_TYPE_SYSTEM = "system"
    MESSAGE_TYPE_CHOICES = [
        (MESSAGE_TYPE_TEXT, "Text"),
        (MESSAGE_TYPE_IMAGE, "Image"),
        (MESSAGE_TYPE_VOICE, "Voice"),
        (MESSAGE_TYPE_SYSTEM, "System"),
    ]

    conversation = models.ForeignKey(Conversation, on_delete=models.CASCADE, related_name='messages')
    sender = models.ForeignKey(User, on_delete=models.CASCADE)
    content = models.TextField(blank=True)
    image_url = models.CharField(max_length=1000, blank=True)
    message_type = models.CharField(max_length=10, choices=MESSAGE_TYPE_CHOICES, default=MESSAGE_TYPE_TEXT)
    event_code = models.CharField(max_length=32, blank=True, default="")
    reply_to = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="replies",
    )
    timestamp = models.DateTimeField(auto_now_add=True)
    delivered_at = models.DateTimeField(null=True, blank=True)
    read_at = models.DateTimeField(null=True, blank=True)
    edited_at = models.DateTimeField(null=True, blank=True)
    is_read = models.BooleanField(default=False)
    
    # Deletion flags
    is_deleted_for_everyone = models.BooleanField(default=False)
    deleted_by = models.ManyToManyField(User, related_name='deleted_messages', blank=True)

    class Meta:
        ordering = ['timestamp']
        indexes = [
            models.Index(fields=["conversation", "-timestamp"], name="msg_convo_ts_idx"),
            models.Index(
                fields=["conversation", "is_read", "sender"],
                name="msg_convo_read_sender_idx",
            ),
        ]

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
