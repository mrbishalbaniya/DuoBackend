#!/usr/bin/env python
"""Standalone seed script (avoids cloud-blocked management __init__ files)."""
import os
import random
import sys

import django

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "duo_project.settings")
django.setup()

from django.contrib.auth import get_user_model  # noqa: E402
from accounts.models import Profile  # noqa: E402

User = get_user_model()

FIRST_NAMES_F = [
    "Aarati", "Binita", "Chandani", "Deepa", "Esha", "Gita", "Hema", "Isha",
    "Jyoti", "Kritika", "Laxmi", "Maya", "Nisha", "Ojaswi", "Pooja", "Riya",
]
FIRST_NAMES_M = [
    "Aakash", "Bikash", "Chirag", "Dipesh", "Gaurav", "Hari", "Ishan", "Jenish",
    "Kiran", "Lokesh", "Manish", "Nabin", "Prakash", "Rajan", "Suman",
]
LAST_NAMES = [
    "Sharma", "Thapa", "Gurung", "Rai", "Tamang", "Karki", "Shrestha", "Maharjan",
    "Adhikari", "Basnet", "Poudel", "KC", "Bhandari",
]
LOCATIONS = [
    "Kathmandu, Nepal", "Pokhara, Nepal", "Lalitpur, Nepal", "Bhaktapur, Nepal",
    "Chitwan, Nepal", "Biratnagar, Nepal",
]
EDUCATIONS = ["Bachelor's Degree", "Master's Degree", "MBA Graduate", "Engineering Degree"]
OCCUPATIONS = [
    "Software Engineer", "Doctor", "Teacher", "Designer", "Entrepreneur", "Consultant",
]
RELIGIONS = ["Hindu", "Buddhist", "Christian", "Secular"]
BIOS = [
    "Love hiking, coffee, and meaningful conversations.",
    "Foodie who enjoys travel and live music on weekends.",
    "Family-oriented, ambitious, and always up for a new adventure.",
    "Yoga enthusiast seeking a genuine connection and shared values.",
]
LIFESTYLE = [
    ["Fitness", "Travel", "Cooking"],
    ["Reading", "Music", "Movies"],
    ["Yoga", "Meditation", "Tea Lover"],
    ["Hiking", "Photography", "Volunteering"],
]

COUNT = int(sys.argv[1]) if len(sys.argv) > 1 else 15
PASSWORD = "demo1234"


def main():
    created = 0
    for _ in range(COUNT):
        gender = random.choice(["F", "M"])
        first = random.choice(FIRST_NAMES_F if gender == "F" else FIRST_NAMES_M)
        last = random.choice(LAST_NAMES)
        full_name = f"{first} {last}"
        username = f"seed_{first.lower()}_{last.lower()}_{random.randint(1000, 9999)}"
        email = f"{username}@seed.duo.local"

        if User.objects.filter(username=username).exists():
            continue

        user = User.objects.create_user(username=username, email=email, password=PASSWORD)
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
        profile.photo_urls = [
            f"https://picsum.photos/seed/{username}-1/600/800",
            f"https://picsum.photos/seed/{username}-2/600/800",
            f"https://picsum.photos/seed/{user.id}-3/600/800",
        ]
        profile.photo_url = profile.photo_urls[0]
        profile.pref_age_min = 21
        profile.pref_age_max = 40
        profile.pref_min_height = "5'4\" (163cm)"
        profile.pref_occupation = random.choice(EDUCATIONS)
        profile.pref_values = "Kindness, honesty, ambition"
        profile.is_verified = random.choice([True, True, False])
        profile.is_onboarded = True
        profile.save()
        created += 1

    print(f"Created {created} random users. Total profiles: {Profile.objects.count()}")
    print("Refresh http://localhost:3000/dashboard (login: demo / demo1234)")


if __name__ == "__main__":
    main()
