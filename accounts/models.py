from django.conf import settings
from django.db import models


class Profile(models.Model):
    GENDER_CHOICES = [
        ("M", "Male"),
        ("F", "Female"),
        ("O", "Other"),
    ]
    RELIGION_CHOICES = [
        ("Hindu", "Hindu"),
        ("Buddhist", "Buddhist"),
        ("Christian", "Christian"),
        ("Muslim", "Muslim"),
        ("Other", "Other"),
    ]
    WORK_PREF_CHOICES = [
        ("Private", "Private Sector"),
        ("Government", "Government"),
        ("Business", "Business/Self-Employed"),
        ("NotWorking", "Not Working"),
    ]
    GENDER_PREF_CHOICES = [
        ("everyone", "Everyone"),
        ("women", "Women"),
        ("men", "Men"),
    ]
    RELATIONSHIP_GOAL_CHOICES = [
        ("serious", "Serious"),
        ("casual", "Casual"),
        ("dating", "Dating"),
    ]
    RELATIONSHIP_GOAL_PREF_CHOICES = [
        ("everyone", "Everyone"),
        ("serious", "Serious"),
        ("casual", "Casual"),
        ("dating", "Dating"),
    ]

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="profile"
    )
    full_name = models.CharField(max_length=200, blank=True)
    phone_country_code = models.CharField(max_length=8, blank=True, default="+977")
    phone_number = models.CharField(max_length=20, blank=True)
    age = models.IntegerField(null=True, blank=True)
    gender = models.CharField(max_length=1, choices=GENDER_CHOICES, blank=True)
    location = models.CharField(max_length=200, default="Kathmandu, Nepal")
    bio = models.TextField(blank=True)
    religion = models.CharField(max_length=20, choices=RELIGION_CHOICES, blank=True)
    education = models.CharField(max_length=300, blank=True)
    occupation = models.CharField(max_length=300, blank=True)
    work_preference = models.CharField(
        max_length=20, choices=WORK_PREF_CHOICES, blank=True
    )
    lifestyle_tags = models.JSONField(default=list, blank=True)
    photo_url = models.URLField(max_length=1000, blank=True)
    photo_urls = models.JSONField(default=list, blank=True)

    pref_age_min = models.IntegerField(default=22)
    pref_age_max = models.IntegerField(default=35)
    pref_min_height = models.CharField(
        max_length=20, blank=True, default='5\'2" (157cm)'
    )
    pref_occupation = models.CharField(
        max_length=200, blank=True, default="Professional Degree"
    )
    pref_values = models.TextField(blank=True)
    pref_gender = models.CharField(
        max_length=10, choices=GENDER_PREF_CHOICES, default="everyone"
    )
    pref_location = models.CharField(max_length=200, blank=True, default="")
    pref_max_distance_km = models.IntegerField(default=50)
    pref_relationship_goal = models.CharField(
        max_length=20, choices=RELATIONSHIP_GOAL_PREF_CHOICES, default="everyone"
    )
    pref_verified_only = models.BooleanField(default=False)
    relationship_goal = models.CharField(
        max_length=20, choices=RELATIONSHIP_GOAL_CHOICES, blank=True, default=""
    )

    is_verified = models.BooleanField(default=False)
    is_onboarded = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    @property
    def profile_completeness(self):
        fields = [
            self.full_name,
            self.age,
            self.gender,
            self.bio,
            self.religion,
            self.education,
            self.occupation,
            self.photo_url,
        ]
        filled = sum(1 for f in fields if f)
        return int(filled / len(fields) * 100)

    def __str__(self):
        return f"{self.full_name or self.user.username} ({self.user.email})"
