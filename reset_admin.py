#!/usr/bin/env python
"""Reset or create admin user with password 'admin123'"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'duo_project.settings')
django.setup()

from django.contrib.auth import get_user_model

User = get_user_model()

username = 'admin'
email = 'admin@example.com'
password = 'admin123'

try:
    user = User.objects.get(username=username)
    print(f"User '{username}' already exists. Updating password...")
    user.set_password(password)
    user.is_superuser = True
    user.is_staff = True
    user.is_active = True
    user.save()
    print(f"✓ Password updated for user '{username}'")
except User.DoesNotExist:
    print(f"Creating new superuser '{username}'...")
    user = User.objects.create_superuser(
        username=username,
        email=email,
        password=password
    )
    print(f"✓ Superuser '{username}' created successfully")

print(f"\nLogin credentials:")
print(f"  URL: http://localhost:8000/admin/")
print(f"  Username: {username}")
print(f"  Password: {password}")
