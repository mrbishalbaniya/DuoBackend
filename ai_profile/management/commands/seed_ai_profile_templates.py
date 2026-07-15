from django.core.management.base import BaseCommand

from ai_profile.models import SentenceTemplate
from ai_profile.services.template_engine import clear_template_cache

# (category, subcategory, text, weight, style)
SEED: list[tuple[str, str, str, int, str]] = [
    # Openers
    ("opener", "generic", "I'm {name} — curious about people, places, and everyday adventures.", 8, "any"),
    ("opener", "generic", "Hi, I'm {name}. I like keeping life simple, warm, and intentional.", 7, "friendly"),
    ("opener", "generic", "I'm {name}, and I bring a thoughtful energy to the connections I build.", 7, "professional"),
    ("opener", "funny", "Warning: I take chai breaks seriously and bad movies personally.", 6, "funny"),
    # Occupation
    ("occupation", "generic", "Professionally, I work as a {occupation} and care about doing meaningful work.", 8, "any"),
    ("occupation", "no_role", "I care about doing meaningful work and growing in my career.", 8, "any"),
    ("occupation", "no_role", "I'm focused on building a career I feel proud of.", 7, "any"),
    ("occupation", "engineer", "As an engineer, I enjoy turning complex ideas into reliable solutions.", 9, "any"),
    ("occupation", "developer", "I spend my days building software and solving practical problems with code.", 9, "any"),
    ("occupation", "doctor", "Working in healthcare keeps me grounded in empathy and purpose.", 8, "any"),
    ("occupation", "teacher", "Teaching keeps me learning every day and connecting with people.", 8, "any"),
    ("occupation", "student", "I'm currently focused on my studies and growing into my next chapter.", 8, "any"),
    ("occupation", "business", "I'm building my path in business with curiosity and steady ambition.", 8, "confident"),
    ("occupation", "manager", "In my role, I enjoy leading teams and creating clarity under pressure.", 7, "professional"),
    # Education
    ("education", "generic", "My education in {education} shaped how I think and learn.", 7, "any"),
    ("education", "computer_science", "I enjoy solving problems and learning new technology.", 9, "any"),
    ("education", "computer_science", "I love technology and the creativity behind building digital products.", 8, "any"),
    ("education", "engineering", "I enjoy learning systems and applying practical problem-solving skills.", 8, "any"),
    ("education", "medical", "My studies taught me patience, discipline, and care for people.", 8, "any"),
    ("education", "business", "I enjoy learning about strategy, people, and how ideas become results.", 7, "any"),
    ("education", "law", "I value careful thinking, fairness, and clear communication.", 7, "intellectual"),
    # Location
    ("location", "generic", "I currently call {location} home and enjoy the rhythm of life here.", 8, "any"),
    ("location", "generic", "Based in {location}, I love discovering local cafes and quiet evening walks.", 7, "friendly"),
    ("location", "generic", "Living in {location} keeps me close to culture, community, and mountains nearby.", 7, "adventurous"),
    # Interests
    ("interest", "gym", "I enjoy staying active.", 8, "any"),
    ("interest", "gym", "Fitness keeps me motivated.", 8, "any"),
    ("interest", "gym", "I like maintaining a healthy lifestyle.", 7, "any"),
    ("interest", "gym", "I enjoy challenging myself physically.", 7, "confident"),
    ("interest", "gym", "Fitness is part of my daily routine.", 6, "any"),
    ("interest", "travel", "I love exploring new places.", 9, "any"),
    ("interest", "travel", "I enjoy experiencing different cultures.", 8, "adventurous"),
    ("interest", "travel", "Travel refreshes my perspective and curiosity.", 7, "any"),
    ("interest", "hiking", "I feel most grounded outdoors on a good trail.", 8, "adventurous"),
    ("interest", "coding", "I enjoy building creative projects.", 8, "any"),
    ("interest", "coding", "I like solving challenging problems.", 8, "intellectual"),
    ("interest", "reading", "I lose track of time in a good book.", 8, "intellectual"),
    ("interest", "reading", "Reading helps me stay curious and reflective.", 7, "any"),
    ("interest", "music", "Music is my easy reset after a busy day.", 8, "creative"),
    ("interest", "movies", "I love a great story on screen — from thrillers to gentle dramas.", 7, "friendly"),
    ("interest", "cooking", "I enjoy cooking simple meals and sharing them with people I care about.", 8, "any"),
    ("interest", "photography", "I like capturing quiet moments through photography.", 7, "creative"),
    ("interest", "yoga", "Yoga keeps me balanced in body and mind.", 7, "any"),
    ("interest", "sports", "Sports keep me competitive in a healthy way.", 7, "confident"),
    ("interest", "dance", "Dancing is my favorite way to unwind and feel present.", 6, "funny"),
    ("interest", "art", "Art inspires me to notice details I might otherwise miss.", 6, "creative"),
    ("interest", "pets", "I have soft spot for animals and the calm they bring.", 7, "friendly"),
    ("interest", "generic", "I enjoy hobbies that keep me curious and connected.", 5, "any"),
    # Lifestyle
    ("lifestyle", "smoking:never", "I don't smoke and prefer fresh, healthy surroundings.", 8, "any"),
    ("lifestyle", "smoking:occasionally", "I smoke only occasionally and keep it infrequent.", 6, "any"),
    ("lifestyle", "drinking:never", "I don't drink and still love a good social evening.", 8, "any"),
    ("lifestyle", "drinking:socially", "I enjoy an occasional drink socially, always in balance.", 7, "any"),
    ("lifestyle", "exercise:daily", "Movement is part of my everyday rhythm.", 8, "any"),
    ("lifestyle", "exercise:often", "I try to stay consistent with exercise through the week.", 7, "any"),
    ("lifestyle", "pace:outgoing", "I recharge best around people and lively conversations.", 7, "friendly"),
    ("lifestyle", "pace:homebody", "I appreciate cozy evenings and slow, intentional days.", 7, "minimal"),
    ("lifestyle", "pace:balanced", "I like a balance of social energy and quiet downtime.", 8, "any"),
    ("lifestyle", "generic", "I try to keep habits that support long-term wellbeing.", 5, "any"),
    # Personality
    ("personality", "active", "Friends would describe me as energetic and outdoorsy.", 8, "any"),
    ("personality", "analytical", "I tend to think things through carefully before I decide.", 8, "intellectual"),
    ("personality", "adventurous", "I'm always open to trying something new.", 8, "adventurous"),
    ("personality", "caring", "I pay attention to the people around me and show up for them.", 8, "romantic"),
    ("personality", "ambitious", "I'm motivated by growth and building something lasting.", 8, "confident"),
    ("personality", "creative", "Creativity shows up in how I work, relax, and connect.", 7, "any"),
    ("personality", "family_oriented", "Family and close bonds are central to how I live.", 8, "any"),
    ("personality", "curious", "I'm endlessly curious about people and ideas.", 7, "any"),
    ("personality", "grounded", "I value calm confidence and emotional steadiness.", 7, "professional"),
    ("personality", "compassionate", "Kindness is a non-negotiable in my circle.", 7, "romantic"),
    ("personality", "friendly", "I'm approachable, easygoing, and warm once you know me.", 8, "friendly"),
    ("personality", "generic", "I aim to be honest, respectful, and emotionally available.", 5, "any"),
    # Values
    ("value", "serious", "I'm looking to build something real and lasting when the connection feels right.", 9, "any"),
    ("value", "dating", "I enjoy dating with honesty and an open heart.", 8, "any"),
    ("value", "generic", "I value honesty, kindness, humor, and good communication.", 8, "any"),
    ("value", "generic", "Mutual respect and emotional maturity matter deeply to me.", 7, "professional"),
    # Connectors / closers
    ("connector", "generic", "In my free time,", 8, "any"),
    ("connector", "generic", "Outside of work,", 8, "any"),
    ("connector", "generic", "On weekends,", 7, "any"),
    ("connector", "generic", "Additionally,", 6, "any"),
    ("connector", "generic", "I also enjoy", 8, "any"),
    ("connector", "generic", "As someone who values balance,", 6, "professional"),
    ("closer", "generic", "If that resonates, I'd love to start a conversation.", 8, "friendly"),
    ("closer", "generic", "Looking forward to meeting someone genuine.", 7, "any"),
    ("closer", "funny", "If you can debate chai brands with me, we might be onto something.", 6, "funny"),
    ("closer", "romantic", "I'm hopeful about finding a thoughtful connection that feels like home.", 7, "romantic"),
    # Future goals
    ("future", "career", "I'm focused on growing in my career with purpose and consistency.", 9, "any"),
    ("future", "career", "Professionally, I want to keep learning and building work I'm proud of.", 8, "professional"),
    ("future", "education", "I hope to keep expanding my skills and knowledge over time.", 7, "intellectual"),
    ("future", "family", "Family remains an important part of the future I want to create.", 9, "any"),
    ("future", "marriage", "When the time is right, I envision a partnership built on trust and teamwork.", 9, "romantic"),
    ("future", "travel", "I want to travel more and collect meaningful experiences along the way.", 8, "adventurous"),
    ("future", "health", "Staying healthy in body and mind is a long-term priority for me.", 7, "any"),
    ("future", "financial", "I'm working toward financial stability that supports freedom and security.", 7, "confident"),
    ("future", "generic", "Overall, I want a future that balances ambition with warmth and presence.", 8, "any"),
    # Looking for
    ("looking", "goal:serious", "I'm looking for a serious relationship with someone emotionally mature.", 9, "any"),
    ("looking", "goal:dating", "I'm open to dating and seeing where authentic chemistry leads.", 8, "any"),
    ("looking", "goal:casual", "I'm open to a lighthearted connection that still feels respectful.", 7, "any"),
    ("looking", "goal:everyone", "I'm open-minded about how a meaningful connection might unfold.", 7, "any"),
    ("looking", "age_range", "Ideally, I'm hoping to connect with someone around {age_min}-{age_max}.", 8, "any"),
    ("looking", "religion", "Shared respect around faith — ideally {religion} — is meaningful for me.", 7, "any"),
    ("looking", "values", "I care more about shared values than perfection.", 8, "any"),
    ("looking", "lifestyle_active", "Someone who enjoys an active lifestyle would be a great fit.", 7, "any"),
    ("looking", "lifestyle_intellectual", "I connect best with people who love thoughtful conversation.", 8, "intellectual"),
    ("looking", "lifestyle_adventurous", "A partner who's open to spontaneous plans and new places lights me up.", 7, "adventurous"),
    ("looking", "communication", "Clear communication and emotional honesty are essential for me.", 9, "any"),
    ("looking", "generic", "I'm hoping to meet someone kind, grounded, and ready for real partnership.", 8, "any"),
]


class Command(BaseCommand):
    help = "Seed SentenceTemplate rows for the offline AI profile generator."

    def add_arguments(self, parser):
        parser.add_argument(
            "--reset",
            action="store_true",
            help="Delete existing English templates before seeding.",
        )

    def handle(self, *args, **options):
        if options["reset"]:
            deleted, _ = SentenceTemplate.objects.filter(language="en").delete()
            self.stdout.write(self.style.WARNING(f"Deleted {deleted} English templates."))

        created = 0
        for category, subcategory, text, weight, style in SEED:
            obj, was_created = SentenceTemplate.objects.get_or_create(
                category=category,
                subcategory=subcategory,
                text=text,
                language="en",
                style=style,
                defaults={"weight": weight, "active": True},
            )
            if was_created:
                created += 1
            else:
                if obj.weight != weight or not obj.active:
                    obj.weight = weight
                    obj.active = True
                    obj.save(update_fields=["weight", "active", "updated_at"])

        clear_template_cache()
        self.stdout.write(
            self.style.SUCCESS(
                f"Seed complete. Created {created} templates. Total active EN: "
                f"{SentenceTemplate.objects.filter(language='en', active=True).count()}"
            )
        )
