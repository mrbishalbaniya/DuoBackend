"""Admin form for sending an announcement email to a group of users."""

from __future__ import annotations

from django import forms
from django.contrib.auth import get_user_model

User = get_user_model()


class AnnouncementForm(forms.Form):
    AUDIENCES = [
        ("onboarded", "All members who finished sign-up"),
        ("verified", "Verified members only"),
        ("all_active", "Every active account (including unfinished sign-ups)"),
    ]

    audience = forms.ChoiceField(choices=AUDIENCES, initial="onboarded")
    title = forms.CharField(max_length=120, help_text="Shown as the email subject and heading.")
    message = forms.CharField(
        widget=forms.Textarea(attrs={"rows": 7}),
        help_text="Plain text. Blank lines start a new paragraph.",
    )
    button_label = forms.CharField(max_length=40, required=False, help_text="Optional, e.g. “Recharge now”.")
    button_url = forms.URLField(required=False, help_text="Optional link for the button.")

    def clean(self):
        data = super().clean()
        if bool(data.get("button_label")) != bool(data.get("button_url")):
            raise forms.ValidationError("Fill in both the button label and the button link, or neither.")
        return data

    @staticmethod
    def audience_queryset(audience: str):
        users = User.objects.filter(is_active=True).exclude(email="")
        if audience == "onboarded":
            users = users.filter(profile__is_onboarded=True)
        elif audience == "verified":
            users = users.filter(profile__is_onboarded=True, profile__is_verified=True)
        return users.order_by("id")
