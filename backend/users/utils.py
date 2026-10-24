from datetime import timedelta

from django.contrib.auth.hashers import check_password, identify_hasher
from django.utils import timezone


def is_pin_locked(user):
    if user.pin_locked_until and user.pin_locked_until > timezone.now():
        return True
    return False


def record_pin_failure(user):
    user.pin_failed_attempts = (user.pin_failed_attempts or 0) + 1
    if user.pin_failed_attempts >= 5:
        user.pin_locked_until = timezone.now() + timedelta(minutes=15)
    user.save(update_fields=["pin_failed_attempts", "pin_locked_until"])


def reset_pin_failures(user):
    if user.pin_failed_attempts or user.pin_locked_until:
        user.pin_failed_attempts = 0
        user.pin_locked_until = None
        user.save(update_fields=["pin_failed_attempts", "pin_locked_until"])


def verify_pin(user, pin):
    if is_pin_locked(user):
        raise PermissionError("PIN locked")
    stored = getattr(user, "pin_hash", "") or ""
    if not stored or pin is None:
        record_pin_failure(user)
        return False
    pin = str(pin)
    try:
        identify_hasher(stored)
    except ValueError:
        record_pin_failure(user)
        return False
    if check_password(pin, stored):
        reset_pin_failures(user)
        return True
    record_pin_failure(user)
    return False
