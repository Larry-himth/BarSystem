import secrets

from django.contrib.auth.hashers import check_password, identify_hasher


def verify_pin(user, pin):
    stored = getattr(user, "pin_hash", "") or ""
    if not stored or pin is None:
        return False
    pin = str(pin)
    try:
        identify_hasher(stored)
    except ValueError:
        return secrets.compare_digest(stored, pin)
    return check_password(pin, stored)
