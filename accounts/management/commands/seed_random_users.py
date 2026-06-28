"""
Create random demo users with complete profiles for the discover feed.
Usage: python manage.py seed_random_users
       python manage.py seed_random_users --count 15
"""

import random
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from accounts.models import Profile

User = get_user_model()

FIRST_NAMES_F = [
    "Aarati", "Binita", "Chandani", "Deepa", "Esha", "Gita", "Hema", "Isha",
    "Jyoti", "Kritika", "Laxmi", "Maya", "Nisha", "Ojaswi", "Pooja", "Riya",
    "Sita", "Tara", "Uma", "Yamuna",
]
FIRST_NAMES_M = [
    "Aakash", "Bikash", "Chirag", "Dipesh", "Gaurav", "Hari", "Ishan", "Jenish",
    "Kiran", "Lokesh", "Manish", "Nabin", "Prakash", "Rajan", "Suman", "Tilak",
]
LAST_NAMES = [
    "Sharma", "Thapa", "Gurung", "Rai", "Tamang", "Karki", "Shrestha", "Maharjan",
    "Adhikari", "Basnet", "Poudel", "KC", "Bhandari", "Nepal", "Bhattarai",
]
LOCATIONS = [
    "Kathmandu, Nepal", "Pokhara, Nepal", "Lalitpur, Nepal", "Bhaktapur, Nepal",
    "Chitwan, Nepal", "Biratnagar, Nepal", "Dharan, Nepal", "Butwal, Nepal",
]
EDUCATIONS = [
    "Bachelor's Degree", "Master's Degree", "MBA Graduate", "Engineering Degree",
    "Medical Degree", "Law Degree", "PhD Candidate",
]
OCCUPATIONS = [
    "Software Engineer", "Doctor", "Teacher", "Architect", "Designer",
    "Business Analyst", "Entrepreneur", "Marketing Manager", "Nurse", "Consultant",
]
RELIGIONS = ["Hindu", "Buddhist", "Christian", "Kirat", "Secular"]
BIOS = [
    "Love hiking, coffee, and meaningful conversations.",
    "Foodie who enjoys travel and live music on weekends.",
    "Family-oriented, ambitious, and always up for a new adventure.",
    "Yoga enthusiast seeking a genuine connection and shared values.",
    "Book lover, amateur photographer, and sunset chaser.",
    "Passionate about community work and exploring new cultures.",
]
LIFESTYLE = [
    ["Fitness", "Travel", "Cooking"],
    ["Reading", "Music", "Movies"],
    ["Yoga", "Meditation", "Tea Lover"],
    ["Hiking", "Photography", "Volunteering"],
    ["Art", "Dancing", "Foodie"],
]


class Command(BaseCommand):
    help = "Seed random users with complete profiles for the dashboard discover feed"

    def add_arguments(self, parser):
        parser.add_argument(
            "--count",
            type=int,
            default=12,
            help="Number of random users to create (default: 12)",
        )
        parser.add_argument(
            "--password",
            type=str,
            default="demo1234",
            help="Password for all seeded users (default: demo1234)",
        )

    def handle(self, *args, **options):
        count = options["count"]
        password = options["password"]
        created = 0
        skipped = 0

        for i in range(count):
            gender = random.choice(["F", "M"])
            first = random.choice(FIRST_NAMES_F if gender == "F" else FIRST_NAMES_M)
            last = random.choice(LAST_NAMES)
            full_name = f"{first} {last}"
            username = f"seed_{first.lower()}_{last.lower()}_{random.randint(1000, 9999)}"
            email = f"{username}@seed.duo.local"

            if User.objects.filter(username=username).exists():
                skipped += 1
                continue

            user = User.objects.create_user(
                username=username,
                email=email,
                password=password,
            )
            profile, _ = Profile.objects.get_or_create(user=user)
            profile.full_name = full_name
            profile.age = random.randint(22, 35)
            profile.gender = gender
            profile.location = random.choice(LOCATIONS)
            profile.bio = random.choice(BIOS)
            profile.religion = random.choice(RELIGIONS)
            profile.education = random.choice(EDUCATIONS)
            profile.occupation = random.choice(OCCUPATIONS)
            profile.work_preference = random.choice(["Private", "Government", "Business"])
            profile.lifestyle_tags = random.choice(LIFESTYLE)
            from duo_project.placeholder_photos import photo_urls_for_seed

            profile.photo_urls = photo_urls_for_seed(username, user.id)
            profile.photo_url = profile.photo_urls[0]
            profile.pref_age_min = 21
            profile.pref_age_max = 40
            profile.pref_min_height = random.choice(["5'0\" (152cm)", "5'4\" (163cm)", "5'8\" (173cm)"])
            profile.pref_occupation = random.choice(EDUCATIONS)
            profile.pref_values = "Kindness, honesty, ambition"
            profile.is_verified = random.choice([True, True, False])
            profile.is_onboarded = True
            profile.save()
            created += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"Done. Created {created} users (skipped {skipped}). "
                f"Total profiles: {Profile.objects.count()}. "
                f"Log in as demo / demo1234 and refresh /dashboard."
            )
        )
