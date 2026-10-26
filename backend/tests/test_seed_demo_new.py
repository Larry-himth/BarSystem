import pytest
from django.contrib.auth import get_user_model
from django.core.management import call_command
from rest_framework.test import APIClient

from catalog.models import ItemUnit
from shifts.models import Shift


@pytest.mark.django_db
def test_seed_demo_creates_approved_closed_shift_no_open_and_b1_can_open_sell():
    call_command("seed_demo")
    assert Shift.objects.filter(status=Shift.OPEN).count() == 0
    approved = Shift.objects.filter(status=Shift.APPROVED).first()
    assert approved is not None
    assert approved.closed_at is not None

    User = get_user_model()
    b1 = User.objects.get(username="b1")
    c = APIClient()
    c.force_authenticate(user=b1)
    r = c.post("/api/v1/shifts/open/", {}, format="json")
    assert r.status_code == 201

    unit = ItemUnit.objects.filter(can_sell=True).first()
    assert unit is not None
    sid = r.data["id"]
    total = unit.sell_price * 1
    rs = c.post(
        "/api/v1/sales/",
        {"shift_id": sid, "lines": [{"item_unit_id": unit.id, "qty": 1}], "payments": [{"method": "CASH", "amount": total}]},
        format="json",
    )
    assert rs.status_code == 201
    assert rs.data["negative_stock_flag"] is False
