#!/usr/bin/env python
"""Reset demo user password to demo1234."""
import sqlite3
import sys
from pathlib import Path

from django.conf import settings

settings.configure(PASSWORD_HASHERS=["django.contrib.auth.hashers.PBKDF2PasswordHasher"])
from django.contrib.auth.hashers import make_password  # noqa: E402

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DB = PROJECT_ROOT / "db.sqlite3"
USERNAME = "demo"
PASSWORD = "demo1234"


def main():
    if not DB.exists():
        print(f"Database not found: {DB}", file=sys.stderr)
        sys.exit(1)

    conn = sqlite3.connect(DB)
    cur = conn.cursor()
    cur.execute("SELECT id FROM auth_user WHERE username = ?", (USERNAME,))
    row = cur.fetchone()
    if not row:
        print(f"User '{USERNAME}' not found.", file=sys.stderr)
        sys.exit(1)

    cur.execute(
        "UPDATE auth_user SET password = ?, is_active = 1 WHERE id = ?",
        (make_password(PASSWORD), row[0]),
    )
    conn.commit()
    conn.close()
    print(f"Reset password for '{USERNAME}' (id={row[0]}) to '{PASSWORD}'")


if __name__ == "__main__":
    main()
