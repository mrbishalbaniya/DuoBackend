from django.contrib.admin.views.decorators import staff_member_required
from django.shortcuts import render


@staff_member_required
def admin_account(request):
    """Visible account hub — profile, password, logout (Django 5 requires POST logout)."""
    return render(request, "admin/account.html", {"title": "My account"})
