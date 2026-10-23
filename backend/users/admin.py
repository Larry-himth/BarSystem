from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import User


@admin.register(User)
class CustomUserAdmin(UserAdmin):
    fieldsets = UserAdmin.fieldsets + (
        (
            "Bar POS",
            {
                "fields": ("name", "role", "language", "pin_hash"),
            },
        ),
    )
    list_display = ("username", "name", "role", "is_active")
