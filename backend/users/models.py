from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    OWNER = "OWNER"
    MANAGER = "MANAGER"
    BARTENDER = "BARTENDER"

    ROLE_CHOICES = [
        (OWNER, "Owner"),
        (MANAGER, "Manager"),
        (BARTENDER, "Bartender"),
    ]

    EN = "en"
    SW = "sw"
    LANG_CHOICES = [(EN, "English"), (SW, "Swahili")]

    name = models.CharField(max_length=255)
    pin_hash = models.CharField(max_length=255, blank=True)
    role = models.CharField(max_length=16, choices=ROLE_CHOICES, default=BARTENDER)
    language = models.CharField(max_length=8, choices=LANG_CHOICES, default=EN)
    is_active = models.BooleanField(default=True)
    pin_failed_attempts = models.IntegerField(default=0)
    pin_locked_until = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.username
