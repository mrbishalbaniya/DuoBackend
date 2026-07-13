"""Drop legacy 3D avatar studio tables (avatars app removed)."""

from django.db import migrations


def drop_avatar_tables(apps, schema_editor):
    connection = schema_editor.connection
    tables = ["avatars_avataroutfit", "avatars_avatarconfig"]
    with connection.cursor() as cursor:
        for table in tables:
            if connection.vendor == "postgresql":
                cursor.execute(f'DROP TABLE IF EXISTS "{table}" CASCADE')
            else:
                cursor.execute(f"DROP TABLE IF EXISTS {table}")


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0006_performance_indexes"),
    ]

    operations = [
        migrations.RunPython(drop_avatar_tables, migrations.RunPython.noop),
    ]
