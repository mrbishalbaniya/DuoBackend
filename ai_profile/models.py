from django.conf import settings
from django.db import models


class SentenceTemplate(models.Model):
    """Database-driven NLG phrase used by the offline profile generator."""

    CATEGORY_INTEREST = "interest"
    CATEGORY_OCCUPATION = "occupation"
    CATEGORY_EDUCATION = "education"
    CATEGORY_LIFESTYLE = "lifestyle"
    CATEGORY_LOCATION = "location"
    CATEGORY_RELIGION = "religion"
    CATEGORY_PERSONALITY = "personality"
    CATEGORY_CONNECTOR = "connector"
    CATEGORY_OPENER = "opener"
    CATEGORY_CLOSER = "closer"
    CATEGORY_FUTURE = "future"
    CATEGORY_LOOKING = "looking"
    CATEGORY_VALUE = "value"

    CATEGORY_CHOICES = [
        (CATEGORY_INTEREST, "Interest"),
        (CATEGORY_OCCUPATION, "Occupation"),
        (CATEGORY_EDUCATION, "Education"),
        (CATEGORY_LIFESTYLE, "Lifestyle"),
        (CATEGORY_LOCATION, "Location"),
        (CATEGORY_RELIGION, "Religion"),
        (CATEGORY_PERSONALITY, "Personality"),
        (CATEGORY_CONNECTOR, "Connector"),
        (CATEGORY_OPENER, "Opener"),
        (CATEGORY_CLOSER, "Closer"),
        (CATEGORY_FUTURE, "Future goals"),
        (CATEGORY_LOOKING, "Looking for"),
        (CATEGORY_VALUE, "Values"),
    ]

    STYLE_CHOICES = [
        ("any", "Any / Neutral"),
        ("professional", "Professional"),
        ("romantic", "Romantic"),
        ("funny", "Funny"),
        ("minimal", "Minimal"),
        ("confident", "Confident"),
        ("adventurous", "Adventurous"),
        ("intellectual", "Intellectual"),
        ("friendly", "Friendly"),
    ]

    LANGUAGE_CHOICES = [
        ("en", "English"),
        ("ne", "Nepali"),
        ("hi", "Hindi"),
    ]

    category = models.CharField(max_length=32, choices=CATEGORY_CHOICES, db_index=True)
    subcategory = models.CharField(
        max_length=64,
        blank=True,
        default="",
        db_index=True,
        help_text="e.g. gym, travel, smoking:never, career, marriage",
    )
    text = models.TextField()
    weight = models.PositiveSmallIntegerField(default=5)
    language = models.CharField(max_length=8, choices=LANGUAGE_CHOICES, default="en", db_index=True)
    style = models.CharField(max_length=20, choices=STYLE_CHOICES, default="any", db_index=True)
    active = models.BooleanField(default=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["category", "subcategory", "-weight", "id"]
        indexes = [
            models.Index(
                fields=["active", "language", "category", "subcategory"],
                name="ai_tpl_lookup_idx",
            ),
            models.Index(
                fields=["active", "language", "style", "category"],
                name="ai_tpl_style_idx",
            ),
        ]

    def __str__(self) -> str:
        return f"[{self.category}/{self.subcategory}] {self.text[:48]}"


class GeneratedProfileContent(models.Model):
    """Cached offline-generated bio sections for a user profile."""

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="ai_profile_content",
    )
    generated_bio = models.TextField(blank=True, default="")
    generated_future_goals = models.TextField(blank=True, default="")
    generated_looking_for = models.TextField(blank=True, default="")
    style = models.CharField(max_length=20, default="friendly")
    language = models.CharField(max_length=8, default="en")
    traits = models.JSONField(default=list, blank=True)
    source_fingerprint = models.CharField(max_length=64, blank=True, default="", db_index=True)
    generation_version = models.PositiveSmallIntegerField(default=1)
    generated_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Generated profile content"
        verbose_name_plural = "Generated profile content"

    def __str__(self) -> str:
        return f"AI profile for user {self.user_id}"
