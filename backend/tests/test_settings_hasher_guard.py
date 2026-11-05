from django.conf import global_settings

from config import settings as production_settings


def test_production_settings_do_not_use_fast_password_hashers():
    hashers = getattr(
        production_settings,
        "PASSWORD_HASHERS",
        global_settings.PASSWORD_HASHERS,
    )

    forbidden = ("md5", "plaintext")
    assert not any(
        marker in hasher.lower()
        for hasher in hashers
        for marker in forbidden
    )
