"""
Seed users who have liked a target account (Liked you tab).
Usage:
  python manage.py seed_likes_you --email mr.bishal.baniya@gmail.com
  python manage.py seed_likes_you --username bishalbaniya --count 8
"""

import random

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError

from accounts.models import Profile
from matching.models import Swipe

User = get_user_model()

LIKER_PROFILES = [
    {
        "full_name": "Priya Sharma",
        "gender": "F",
        "age": 26,
        "location": "Kathmandu, Nepal",
        "bio": "Coffee lover looking for someone genuine and kind.",
        "education": "Master's Degree",
        "occupation": "Marketing Manager",
        "photo_seed": "priya-sharma-duo",
    },
    {
        "full_name": "Anisha Thapa",
        "gender": "F",
        "age": 24,
        "location": "Lalitpur, Nepal",
        "bio": "Travel, music festivals, and long evening walks.",
        "education": "Bachelor's Degree",
        "occupation": "Designer",
        "photo_seed": "anisha-thapa-duo",
    },
    {
        "full_name": "Sneha Gurung",
        "gender": "F",
        "age": 28,
        "location": "Pokhara, Nepal",
        "bio": "Yoga instructor who values honesty and ambition.",
        "education": "Bachelor's Degree",
        "occupation": "Teacher",
        "photo_seed": "sneha-gurung-duo",
    },
    {
        "full_name": "Riya Maharjan",
        "gender": "F",
        "age": 25,
        "location": "Bhaktapur, Nepal",
        "bio": "Foodie, photographer, and sunset chaser.",
        "education": "Engineering Degree",
        "occupation": "Software Engineer",
        "photo_seed": "riya-maharjan-duo",
    },
    {
        "full_name": "Kritika Rai",
        "gender": "F",
        "age": 27,
        "location": "Kathmandu, Nepal",
        "bio": "Bookworm seeking meaningful conversations.",
        "education": "MBA Graduate",
        "occupation": "Business Analyst",
        "photo_seed": "kritika-rai-duo",
    },
    {
        "full_name": "Nisha Karki",
        "gender": "F",
        "age": 23,
        "location": "Chitwan, Nepal",
        "bio": "Adventure seeker with a soft spot for dogs.",
        "education": "Bachelor's Degree",
        "occupation": "Nurse",
        "photo_seed": "nisha-karki-duo",
    },
    {
        "full_name": "Aarati Shrestha",
        "gender": "F",
        "age": 29,
        "location": "Kathmandu, Nepal",
        "bio": "Family-oriented and ready for something serious.",
        "education": "Medical Degree",
        "occupation": "Doctor",
        "photo_seed": "aarati-shrestha-duo",
    },
    {
        "full_name": "Esha Basnet",
        "gender": "F",
        "age": 26,
        "location": "Dharan, Nepal",
        "bio": "Dancer, tea lover, and hopeless romantic.",
        "education": "Bachelor's Degree",
        "occupation": "Architect",
        "photo_seed": "esha-basnet-duo",
    },
]


class Command(BaseCommand):
    help = "Seed demo users who liked a target account (Discover > Liked you)"

    def add_arguments(self, parser):
        parser.add_argument("--email", type=str, help="Target user email")
        parser.add_argument("--username", type=str, help="Target username")
        parser.add_argument(
            "--count",
            type=int,
            default=6,
            help="Number of likers to create (default: 6, max 8)",
        )
        parser.add_argument(
            "--password",
            type=str,
            default="demo1234",
            help="Password for newly created liker accounts",
        )

    def handle(self, *args, **options):
        target = self._resolve_target(options)
        count = min(max(options["count"], 1), len(LIKER_PROFILES))
        password = options["password"]
        created_users = 0
        created_swipes = 0

        for liker_data in LIKER_PROFILES[:count]:
            slug = liker_data["full_name"].lower().replace(" ", "_")
            username = f"liker_{slug}"
            email = f"{username}@seed.duo.local"

            user, user_created = User.objects.get_or_create(
                username=username,
                defaults={"email": email},
            )
            if user_created:
                user.set_password(password)
                user.save(update_fields=["password"])
                created_users += 1

            profile, _ = Profile.objects.get_or_create(user=user)
            from duo_project.placeholder_photos import photo_urls_for_seed

            photo_urls = photo_urls_for_seed(liker_data["photo_seed"], user.id)
            profile.full_name = liker_data["full_name"]
            profile.age = liker_data["age"]
            profile.gender = liker_data["gender"]
            profile.location = liker_data["location"]
            profile.bio = liker_data["bio"]
            profile.education = liker_data["education"]
            profile.occupation = liker_data["occupation"]
            profile.religion = "Hindu"
            profile.work_preference = "Private"
            profile.lifestyle_tags = ["Travel", "Music", "Fitness"]
            profile.photo_urls = photo_urls
            profile.photo_url = photo_urls[0]
            profile.pref_age_min = 22
            profile.pref_age_max = 35
            profile.pref_gender = "everyone"
            profile.is_verified = random.choice([True, True, False])
            profile.is_onboarded = True
            profile.save()

            action = random.choice(["LIKE", "LIKE", "SUPERLIKE"])
            swipe, swipe_created = Swipe.objects.update_or_create(
                from_user=user,
                to_user=target,
                defaults={"action": action},
            )
            if swipe_created:
                created_swipes += 1

            self.stdout.write(
                f"  {liker_data['full_name']} -> {action} -> {target.username}"
            )

        self.stdout.write(
            self.style.SUCCESS(
                f"Done for {target.username} (id={target.id}). "
                f"Created {created_users} liker users, {created_swipes} new swipes. "
                f"Refresh /discover > Liked you."
            )
        )

    def _resolve_target(self, options):
        if options.get("username"):
            try:
                return User.objects.get(username=options["username"])
            except User.DoesNotExist as exc:
                raise CommandError(f"User not found: {options['username']}") from exc

        email = options.get("email") or "mr.bishal.baniya@gmail.com"
        users = User.objects.filter(email=email).order_by("-id")
        if not users.exists():
            raise CommandError(f"No user found with email: {email}")

        # Prefer the Google/OAuth account (username usually equals email).
        preferred = users.filter(username=email).first()
        if preferred:
            return preferred

        return users.first()
