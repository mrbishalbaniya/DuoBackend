from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

from accounts.models import Profile
from matching.recommendation import discover_profiles
from matching.recommendation.queries import (
    build_broad_queryset,
    build_eligible_queryset,
    build_recycled_queryset,
)

User = get_user_model()


class Command(BaseCommand):
    help = "Diagnose discover pool sizes for a user (username or email)."

    def add_arguments(self, parser):
        parser.add_argument("identifier", help="Username or email")
        parser.add_argument(
            "--send",
            action="store_true",
            help="Print sample recommended usernames",
        )

    def handle(self, *args, **options):
        identifier = options["identifier"].strip()
        user = User.objects.filter(username=identifier).first()
        if not user:
            user = User.objects.filter(email__iexact=identifier).first()
        if not user:
            self.stderr.write(self.style.ERROR(f"User not found: {identifier}"))
            return

        profile = Profile.objects.filter(user=user).first()
        onboarded_total = Profile.objects.filter(is_onboarded=True).exclude(user=user).count()
        fresh = build_eligible_queryset(user).count()
        recycled = build_recycled_queryset(user).count()
        broad = build_broad_queryset(user).count()
        result = discover_profiles(user)

        self.stdout.write(f"User: {user.username} ({user.email})")
        self.stdout.write(f"Onboarded profiles (excl. self): {onboarded_total}")
        self.stdout.write(f"Fresh pool (unswiped): {fresh}")
        self.stdout.write(f"Recycled pool (includes skipped): {recycled}")
        self.stdout.write(f"Broad pool (excl. matches/blocks): {broad}")
        self.stdout.write(
            f"Recommendations: {len(result.profiles)} "
            f"(stage={result.relaxation_stage}, expanded={result.expanded_search}, "
            f"recycled={result.recycled_skips})"
        )

        if options["send"] and result.profiles:
            names = [p.user.username for p in result.profiles[:10]]
            self.stdout.write(self.style.SUCCESS(f"Sample: {', '.join(names)}"))

        if not result.profiles and broad == 0:
            self.stdout.write(
                self.style.WARNING(
                    "No discoverable users in database. Run: python manage.py seed_random_users --count 20"
                )
            )
