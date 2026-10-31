import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

from catalog.models import Item, ItemUnit
from shifts.models import Shift


@pytest.mark.django_db
def test_payment_mismatch_underpay():
    User = get_user_model()
    u = User.objects.create_user(username="pm1", password="x")
    item = Item.objects.create(name_en="PM1", name_sw="PM1", category=Item.BEER, base_unit=Item.BOTTLE, buy_price=1000, par_level=1)
    unit = ItemUnit.objects.create(item=item, label="Bottle", qty_in_base_unit=1, sell_price=3000, can_sell=True)
    shift = Shift.objects.create(opened_by=u, status=Shift.OPEN)
    c = APIClient()
    c.force_authenticate(user=u)
    r = c.post("/api/v1/sales/", {"shift_id": shift.id, "lines": [{"item_unit_id": unit.id, "qty": 1}], "payments": [{"method": "CASH", "amount": 2000}]}, format="json")
    assert r.status_code == 400
    assert r.data["code"] == "PAYMENT_MISMATCH"


@pytest.mark.django_db
def test_payment_mismatch_overpay():
    User = get_user_model()
    u = User.objects.create_user(username="pm2", password="x")
    item = Item.objects.create(name_en="PM2", name_sw="PM2", category=Item.BEER, base_unit=Item.BOTTLE, buy_price=1000, par_level=1)
    unit = ItemUnit.objects.create(item=item, label="Bottle", qty_in_base_unit=1, sell_price=3000, can_sell=True)
    shift = Shift.objects.create(opened_by=u, status=Shift.OPEN)
    c = APIClient()
    c.force_authenticate(user=u)
    r = c.post("/api/v1/sales/", {"shift_id": shift.id, "lines": [{"item_unit_id": unit.id, "qty": 1}], "payments": [{"method": "CASH", "amount": 4000}]}, format="json")
    assert r.status_code == 400
    assert r.data["code"] == "PAYMENT_MISMATCH"


@pytest.mark.django_db
def test_payment_exact_ok():
    User = get_user_model()
    u = User.objects.create_user(username="pm3", password="x")
    item = Item.objects.create(name_en="PM3", name_sw="PM3", category=Item.BEER, base_unit=Item.BOTTLE, buy_price=1000, par_level=1)
    unit = ItemUnit.objects.create(item=item, label="Bottle", qty_in_base_unit=1, sell_price=3000, can_sell=True)
    shift = Shift.objects.create(opened_by=u, status=Shift.OPEN)
    c = APIClient()
    c.force_authenticate(user=u)
    r = c.post("/api/v1/sales/", {"shift_id": shift.id, "lines": [{"item_unit_id": unit.id, "qty": 1}], "payments": [{"method": "CASH", "amount": 3000}]}, format="json")
    assert r.status_code == 201
