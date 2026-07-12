# Generated manually for Conversation.public_id

import secrets

from django.db import migrations, models


def generate_public_id():
    return str(secrets.randbelow(9_000_000_000) + 1_000_000_000)


def backfill_public_ids(schema_editor):
    """Backfill via SQL — historical ORM state lacks public_id during database_operations."""
    connection = schema_editor.connection
    table = "chat_conversation"

    with connection.cursor() as cursor:
        cursor.execute(f"SELECT id, public_id FROM {table}")
        rows = cursor.fetchall()

    used = {public_id for _, public_id in rows if public_id}
    updates = []

    for row_id, public_id in rows:
        if public_id:
            continue
        for _ in range(40):
            candidate = generate_public_id()
            if candidate not in used:
                used.add(candidate)
                updates.append((candidate, row_id))
                break
        else:
            raise RuntimeError(f"Could not allocate public_id for conversation {row_id}")

    if not updates:
        return

    with connection.cursor() as cursor:
        cursor.executemany(
            f"UPDATE {table} SET public_id = %s WHERE id = %s",
            updates,
        )


def _column_exists(cursor, vendor, table, column):
    if vendor == "postgresql":
        cursor.execute(
            """
            SELECT 1
            FROM information_schema.columns
            WHERE table_schema = 'public'
              AND table_name = %s
              AND column_name = %s
            """,
            [table, column],
        )
        return cursor.fetchone() is not None

    cursor.execute(f"PRAGMA table_info({table})")
    return any(row[1] == column for row in cursor.fetchall())


def _pg_index_exists(cursor, name):
    cursor.execute("SELECT 1 FROM pg_indexes WHERE indexname = %s", [name])
    return cursor.fetchone() is not None


def apply_public_id_schema(apps, schema_editor):
    """
    Idempotent DB changes for production DBs where a prior deploy partially
    applied this migration (column/index exists but django_migrations row missing).
    """
    connection = schema_editor.connection
    vendor = connection.vendor
    table = "chat_conversation"

    with connection.cursor() as cursor:
        if not _column_exists(cursor, vendor, table, "public_id"):
            if vendor == "postgresql":
                cursor.execute(
                    f"ALTER TABLE {table} "
                    "ADD COLUMN public_id varchar(10) NOT NULL DEFAULT ''"
                )
            else:
                cursor.execute(
                    f"ALTER TABLE {table} "
                    "ADD COLUMN public_id varchar(10) NOT NULL DEFAULT ''"
                )

    backfill_public_ids(schema_editor)

    with connection.cursor() as cursor:
        if vendor == "postgresql":
            cursor.execute(
                f"ALTER TABLE {table} ALTER COLUMN public_id DROP DEFAULT"
            )

            cursor.execute(
                f"""
                DO $$
                BEGIN
                    ALTER TABLE {table}
                    ADD CONSTRAINT chat_conversation_public_id_key UNIQUE (public_id);
                EXCEPTION
                    WHEN duplicate_object THEN NULL;
                    WHEN duplicate_table THEN NULL;
                END $$;
                """
            )

            # Django CharField(db_index=True) indexes — create only if missing.
            if not _pg_index_exists(cursor, "chat_conversation_public_id_7019d3ab"):
                cursor.execute(
                    "CREATE INDEX chat_conversation_public_id_7019d3ab "
                    f"ON {table} (public_id)"
                )
            if not _pg_index_exists(
                cursor, "chat_conversation_public_id_7019d3ab_like"
            ):
                cursor.execute(
                    "CREATE INDEX chat_conversation_public_id_7019d3ab_like "
                    f"ON {table} (public_id varchar_pattern_ops)"
                )
        else:
            cursor.execute(
                "CREATE UNIQUE INDEX IF NOT EXISTS "
                "chat_conversation_public_id_uniq ON chat_conversation (public_id)"
            )


class Migration(migrations.Migration):

    dependencies = [
        ("chat", "0004_conversation_actions"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.AddField(
                    model_name="conversation",
                    name="public_id",
                    field=models.CharField(
                        blank=True,
                        db_index=True,
                        default="",
                        editable=False,
                        max_length=10,
                    ),
                ),
                migrations.AlterField(
                    model_name="conversation",
                    name="public_id",
                    field=models.CharField(
                        db_index=True,
                        editable=False,
                        max_length=10,
                        unique=True,
                    ),
                ),
            ],
            database_operations=[
                migrations.RunPython(
                    apply_public_id_schema,
                    migrations.RunPython.noop,
                ),
            ],
        ),
    ]
