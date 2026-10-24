import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from shifts.models import Shift


@pytest.mark.django_db
def test_tabs_record_repay():
    User = get_user_model()
    b = User.objects.create_user(username="btfix2", password="x")
    Shift.objects.create(opened_by=b, status=Shift.OPEN)
    c = APIClient()
    c.force_authenticate(user=b)
    rt = c.post("/api/v1/tabs/", {"customer_name": "John", "phone": "077"}, format="json")
    assert rt.status_code == 201
    tid = rt.data["id"]
    rp = c.post(f"/api/v1/tabs/{tid}/payments/", {"amount": 5000, "method": "CASH"}, format="json")
    assert rp.status_code == 200
