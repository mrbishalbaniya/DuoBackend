from django.db import models

from email_service.constants import EmailEvent, EmailProvider, EmailStatus


class EmailEventSetting(models.Model):
    event = models.CharField(max_length=64, choices=EmailEvent.choices, unique=True)
    enabled = models.BooleanField(default=True)
    subject_template = models.CharField(max_length=255, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Email event"
        verbose_name_plural = "Email events"

    def __str__(self) -> str:
        return self.get_event_display()


class EmailTemplate(models.Model):
    event = models.CharField(max_length=64, choices=EmailEvent.choices, unique=True)
    subject = models.CharField(max_length=255)
    text_body = models.TextField()
    html_body = models.TextField(blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Email template"
        verbose_name_plural = "Email templates"

    def __str__(self) -> str:
        return f"{self.get_event_display()} template"


class EmailLog(models.Model):
    event = models.CharField(max_length=64, choices=EmailEvent.choices, db_index=True)
    recipient = models.EmailField(db_index=True)
    subject = models.CharField(max_length=255)
    provider = models.CharField(max_length=32, choices=EmailProvider.choices)
    status = models.CharField(max_length=16, choices=EmailStatus.choices, db_index=True)
    attempt_count = models.PositiveSmallIntegerField(default=1)
    error_message = models.TextField(blank=True)
    provider_message_id = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Email log"
        verbose_name_plural = "Email logs"

    def __str__(self) -> str:
        return f"{self.event} → {self.recipient} ({self.status})"
