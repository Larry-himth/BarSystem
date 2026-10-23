import uuid

import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

from catalog.models import Item, ItemUnit
from shifts.models import Shift
from stock.models import StockMovement


@pytest.mark.django_db
def test_void_override_caller_any_staff_with_open_shift_approver_different_manager():
    User = get_user_model()
    bartender = User.objects.create_user(username="bo", password="x", role=User.BARTENDER)
    manager = User.objects.create_user(username="mo", password="x", role=User.MANAGER, pin_hash="5555")
    item = Item.objects.create(name_en="O", name_sw="O", category=Item.BEER, base_unit=Item.BOTTLE, buy_price=1, par_level=1)
    unit = ItemUnit.objects.create(item=item, label="Bottle", qty_in_base_unit=1, sell_price=3, can_sell=True)
    shift = Shift.objects.create(opened_by=bartender, status=Shift.OPEN)
    c = APIClient()
    c.force_authenticate(user=bartender)
    r = c.post("/api/v1/sales/", {"shift_id": shift.id, "lines": [{"item_unit_id": unit.id, "qty": 1}], "payments": [{"method": "CASH", "amount": 3}]}, format="json")
    sale_id = r.data["id"]
    rv = c.post(f"/api/v1/sales/{sale_id}/void/", {"reason": "mistake", "approver_username": "mo", "approver_pin": "5555"}, format="json")
    assert rv.status_code == 200
    assert rv.data.get("override") is True
    assert StockMovement.objects.filter(type=StockMovement.VOID_REVERSAL).count() == 1
