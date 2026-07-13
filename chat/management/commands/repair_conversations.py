from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError

from chat.services import ensure_conversations_for_user

User = get_user_model()


class Command(BaseCommand):
    help = "Create missing chat conversations for existing mutual matches."

    def add_arguments(self, parser):
        parser.add_argument(
            "identifier",
            nargs="?",
            help="Optional username or email to repair for one user only.",
        )

    def handle(self, *args, **options):
        identifier = (options.get("identifier") or "").strip()
        if identifier:
            user = (
                User.objects.filter(email__iexact=identifier).first()
                or User.objects.filter(username__iexact=identifier).first()
            )
            if user is None:
                raise CommandError(f"No user found for {identifier!r}.")
            created = ensure_conversations_for_user(user)
            self.stdout.write(
                self.style.SUCCESS(
                    f"Repaired conversations for {user.username}: created {created}."
                )
            )
            return

        from matching.models import Match

        total = 0
        user_ids = set()
        for user1_id, user2_id in Match.objects.values_list("user1_id", "user2_id"):
            user_ids.add(user1_id)
            user_ids.add(user2_id)

        for user_id in user_ids:
            user = User.objects.filter(id=user_id).first()
            if user is None:
                continue
            total += ensure_conversations_for_user(user)

        self.stdout.write(self.style.SUCCESS(f"Created {total} missing conversation(s)."))
