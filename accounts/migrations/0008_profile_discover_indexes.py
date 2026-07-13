from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0007_drop_avatar_tables"),
        ("matching", "0003_performance_indexes"),
    ]

    operations = [
        migrations.AddIndex(
            model_name="profile",
            index=models.Index(
                fields=["is_onboarded", "age", "gender", "is_verified"],
                name="profile_discover_core_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="profile",
            index=models.Index(fields=["relationship_goal"], name="profile_rel_goal_idx"),
        ),
        migrations.AddIndex(
            model_name="profile",
            index=models.Index(fields=["-created_at"], name="profile_created_desc_idx"),
        ),
    ]
