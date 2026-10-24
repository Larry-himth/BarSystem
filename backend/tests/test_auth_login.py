import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient


@pytest.mark.django_db
def test_login_succeeds_with_invalid_bearer_token():
    User = get_user_model()
    from django.contrib.auth.hashers import make_password

    User.objects.create_user(username="bolt", password="x", pin_hash=make_password("4321"))

    client = APIClient()
    response = client.post(
        "/api/v1/auth/login/",
        {"username": "bolt", "pin": "4321"},
        format="json",
        HTTP_AUTHORIZATION="Bearer definitely-not-a-valid-jwt",
    )

    assert response.status_code == 200
    assert "access" in response.data
    assert "refresh" in response.data
