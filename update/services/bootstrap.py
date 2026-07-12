"""Database readiness, migration helpers, and initial seed for the update app."""

from __future__ import annotations

import logging

from django.core.management import call_command
from django.db import connection
from django.db.migrations.recorder import MigrationRecorder
from django.utils import timezone

from update.models import AppVersion

logger = logging.getLogger("update")

DEFAULT_SEED_VERSIONS = (
    {
        "version": "1.0.0",
        "build_number": 1,
        "platform": AppVersion.PLATFORM_ANDROID,
        "channel": AppVersion.CHANNEL_STABLE,
        "release_notes": ["Initial Duo Android release."],
    },
    {
        "version": "1.0.0",
        "build_number": 1,
        "platform": AppVersion.PLATFORM_IOS,
        "channel": AppVersion.CHANNEL_STABLE,
        "release_notes": ["Initial Duo iOS release."],
    },
)


def update_table_exists() -> bool:
    """Return True when the AppVersion table is present in the active database."""
    try:
        table = AppVersion._meta.db_table
        tables = set(connection.introspection.table_names())
        exists = table in tables
        logger.debug("update_table_exists table=%s exists=%s", table, exists)
        return exists
    except Exception:
        logger.exception("Failed to introspect update tables")
        return False


def update_migration_recorded() -> bool:
    """Return True when update.0001_initial is recorded in django_migrations."""
    try:
        recorded = MigrationRecorder.Migration.objects.filter(
            app="update",
            name="0001_initial",
        ).exists()
        logger.debug("update_migration_recorded=%s", recorded)
        return recorded
    except Exception:
        logger.exception("Failed to read django_migrations for update app")
        return False


def apply_update_migrations() -> bool:
    """Apply pending migrations for the update app only."""
    logger.info("Applying update app migrations")
    try:
        call_command("migrate", "update", interactive=False, verbosity=1)
    except Exception:
        logger.exception("migrate update failed")
        return False

    ready = update_table_exists()
    if ready:
        logger.info("update app migrations applied successfully")
    else:
        logger.error("update app migrations finished but update_appversion table is still missing")
    return ready


def ensure_update_database(*, apply_migrations: bool = True) -> bool:
    """
    Ensure the update service database is ready.

    When apply_migrations is True (startup/deploy), missing tables trigger
    `python manage.py migrate update`. Request handlers should pass False and
    rely on startup initialization instead.
    """
    if update_table_exists():
        return True

    logger.warning(
        "Update service database is not ready (table missing, migration_recorded=%s)",
        update_migration_recorded(),
    )

    if not apply_migrations:
        return False

    return apply_update_migrations()


def seed_initial_versions() -> int:
    """
    Create baseline AppVersion rows when the table is empty.

    Returns the number of records created.
    """
    if not update_table_exists():
        logger.warning("Skipping update seed because update_appversion table is missing")
        return 0

    if AppVersion.objects.exists():
        logger.debug("AppVersion table already has data — seed skipped")
        return 0

    created = 0
    now = timezone.now()
    for item in DEFAULT_SEED_VERSIONS:
        AppVersion.objects.create(
            version=item["version"],
            build_number=item["build_number"],
            platform=item["platform"],
            channel=item["channel"],
            release_notes=item["release_notes"],
            minimum_version=item["version"],
            force_update=False,
            soft_update=False,
            emergency_update=False,
            is_active=True,
            is_published=True,
            published_at=now,
        )
        created += 1
        logger.info(
            "Seeded baseline AppVersion platform=%s version=%s+%s",
            item["platform"],
            item["version"],
            item["build_number"],
        )

    return created


def initialize_update_service(*, apply_migrations: bool = True) -> dict:
    """Full startup bootstrap: migrations + seed. Used by deploy scripts."""
    db_ready = ensure_update_database(apply_migrations=apply_migrations)
    seeded = seed_initial_versions() if db_ready else 0
    status = {
        "database_ready": db_ready,
        "migration_recorded": update_migration_recorded(),
        "table_exists": update_table_exists(),
        "seeded": seeded,
        "version_count": AppVersion.objects.count() if db_ready else 0,
    }
    logger.info("Update service initialization: %s", status)
    return status
