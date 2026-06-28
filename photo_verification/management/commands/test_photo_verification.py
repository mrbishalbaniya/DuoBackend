import io

from PIL import Image

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

from photo_verification.services.pipeline import PhotoVerificationPipeline


class Command(BaseCommand):
    help = "Smoke-test the photo verification pipeline on a generated image."

    def handle(self, *args, **options):
        User = get_user_model()
        user = User.objects.first()
        if not user:
            self.stderr.write("No users in database.")
            return

        img = Image.new("RGB", (640, 640), color=(200, 160, 140))
        buf = io.BytesIO()
        img.save(buf, format="JPEG")

        result = PhotoVerificationPipeline().analyze_bytes(
            buf.getvalue(),
            user_id=user.id,
            is_primary=True,
        )
        self.stdout.write(self.style.SUCCESS(result.to_analysis_dict()))
