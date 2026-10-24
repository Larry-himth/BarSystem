import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

from catalog.models import Item, ItemUnit
from sales.models import Sale
from shifts.models import Shift


@pytest.mark.django_db
def test_lockout_survives_transaction_and_correct_pin_still_rejected():
    User = get_user_model()
    owner = User.objects.create_user(username="lock2", password="x", role=User.OWNER, pin_hash="1234")
    b = User.objects.create_user(username="lock2b", password="x", role=User.BARTENDER)
    item = Item.objects.create(name_en="L2", name_sw="L2", category=Item.BEER, base_unit=Item.BOTTLE, buy_price=1, par_level=1)
    unit = ItemUnit.objects.create(item=item, label="Bottle", qty_in_base_unit=1, sell_price=1, can_sell=True)
    shift = Shift.objects.create(opened_by=b, status=Shift.OPEN)
    c = APIClient()
    c.force_authenticate(user=b)
    r = c.post("/api/v1/sales/", {"shift_id": shift.id, "lines": [{"item_unit_id": unit.id, "qty": 1}], "payments": [{"method": "CASH", "amount": 1}]}, format="json")
    sale_id = r.data["id"]
    c2 = APIClient()
    c2.force_authenticate(user=owner)

    for _ in range(5):
        rv = c2.post(f"/api/v1/sales/{sale_id}/void/", {"pin": "wrong", "reason": "x"}, format="json")
        assert rv.status_code == 403

    owner.refresh_from_db()
    assert owner.pin_failed_attempts >= 5
    assert owner.pin_locked_until is not None

    rv2 = c2.post(f"/api/v1/sales/{sale_id}/void/", {"pin": "1234", "reason": "x"}, format="json")
    assert rv2.status_code == 403
    assert rv2.data.get("code") == "PIN_LOCKED"
