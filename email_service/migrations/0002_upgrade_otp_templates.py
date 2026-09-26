from django.db import migrations


def upgrade(apps, schema_editor):
    # Uses the live defaults module: it only touches EmailTemplate/EmailEventSetting
    # fields that exist since 0001, and skips admin-customised templates.
    from email_service.defaults import ensure_default_templates

    ensure_default_templates()


class Migration(migrations.Migration):
    dependencies = [("email_service", "0001_initial")]

    operations = [migrations.RunPython(upgrade, migrations.RunPython.noop)]
