from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("photo_verification", "0002_faceembedding_userverification"),
    ]

    operations = [
        migrations.AddIndex(
            model_name="photoanalysis",
            index=models.Index(
                fields=["user", "image_hash"],
                name="photo_user_hash_idx",
            ),
        ),
    ]
