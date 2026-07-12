from django.db import models
from django.utils import timezone


class AppVersion(models.Model):
    PLATFORM_ANDROID = "android"
    PLATFORM_IOS = "ios"
    PLATFORM_CHOICES = [
        (PLATFORM_ANDROID, "Android"),
        (PLATFORM_IOS, "iOS"),
    ]

    CHANNEL_STABLE = "stable"
    CHANNEL_BETA = "beta"
    CHANNEL_CHOICES = [
        (CHANNEL_STABLE, "Stable"),
        (CHANNEL_BETA, "Beta"),
    ]

    version = models.CharField(max_length=32, help_text="Semantic version, e.g. 1.0.8")
    build_number = models.PositiveIntegerField(help_text="Monotonic build number, e.g. 108")
    platform = models.CharField(max_length=16, choices=PLATFORM_CHOICES, default=PLATFORM_ANDROID)
    channel = models.CharField(max_length=16, choices=CHANNEL_CHOICES, default=CHANNEL_STABLE)

    apk_file = models.FileField(upload_to="apk/", blank=True, null=True)
    apk_url = models.URLField(
        max_length=1024,
        blank=True,
        help_text="Public HTTPS URL when APK is hosted on S3/R2/GitHub.",
    )

    release_notes = models.JSONField(default=list, blank=True)
    minimum_version = models.CharField(
        max_length=32,
        blank=True,
        help_text="Users below this version must update when force_update is enabled.",
    )
    force_update = models.BooleanField(default=False)
    soft_update = models.BooleanField(default=True)
    emergency_update = models.BooleanField(default=False)

    file_size_bytes = models.BigIntegerField(default=0)
    checksum_sha256 = models.CharField(max_length=64, blank=True)

    is_active = models.BooleanField(default=False, help_text="Only one active release per platform/channel.")
    is_published = models.BooleanField(default=False)
    published_at = models.DateTimeField(blank=True, null=True)

    download_count = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-build_number", "-published_at", "-created_at"]
        indexes = [
            models.Index(fields=["platform", "channel", "is_active"]),
            models.Index(fields=["platform", "build_number"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["platform", "channel", "version", "build_number"],
                name="update_unique_platform_channel_version_build",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.platform} {self.version}+{self.build_number} ({self.channel})"

    def normalized_release_notes(self) -> list[str]:
        from update.services.version import parse_release_notes

        return parse_release_notes(self.release_notes)

    @property
    def file_size_label(self) -> str:
        if self.file_size_bytes <= 0:
            return "Unknown"
        size = float(self.file_size_bytes)
        if size < 1024:
            return f"{int(size)} B"
        if size < 1024 * 1024:
            return f"{size / 1024:.1f} KB"
        if size < 1024 * 1024 * 1024:
            return f"{size / (1024 * 1024):.1f} MB"
        return f"{size / (1024 * 1024 * 1024):.2f} GB"

    def mark_published(self) -> None:
        self.is_published = True
        self.published_at = timezone.now()
