import uuid

import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

from catalog.models import Item, ItemUnit
from sales.models import Sale
from shifts.models import Shift
from stock.models import StockMovement


@pytest.mark.django_db
def test_void_with_wrong_pin_is_rejected():
    User = get_user_model()
    owner = User.objects.create_user(username="ow", password="x", role=User.OWNER, pin_hash="9999")
    b = User.objects.create_user(username="bw", password="x", role=User.BARTENDER)
    item = Item.objects.create(name_en="X", name_sw="X", category=Item.BEER, base_unit=Item.BOTTLE, buy_price=1, par_level=1)
    unit = ItemUnit.objects.create(item=item, label="Bottle", qty_in_base_unit=1, sell_price=1, can_sell=True)
    shift = Shift.objects.create(opened_by=b, status=Shift.OPEN)
    c = APIClient()
    c.force_authenticate(user=b)
    r = c.post("/api/v1/sales/", {"shift_id": shift.id, "lines": [{"item_unit_id": unit.id, "qty": 1}], "payments": [{"method": "CASH", "amount": 1}]}, format="json")
    sale_id = r.data["id"]
    c2 = APIClient()
    c2.force_authenticate(user=owner)
    rv = c2.post(f"/api/v1/sales/{sale_id}/void/", {"pin": "0000", "reason": "x"}, format="json")
    assert rv.status_code == 403


@pytest.mark.django_db
def test_void_twice_rejected():
    User = get_user_model()
    owner = User.objects.create_user(username="ow2", password="x", role=User.OWNER, pin_hash="9999")
    b = User.objects.create_user(username="bw2", password="x", role=User.BARTENDER)
    item = Item.objects.create(name_en="Y", name_sw="Y", category=Item.BEER, base_unit=Item.BOTTLE, buy_price=1, par_level=1)
    unit = ItemUnit.objects.create(item=item, label="Bottle", qty_in_base_unit=1, sell_price=1, can_sell=True)
    shift = Shift.objects.create(opened_by=b, status=Shift.OPEN)
    c = APIClient()
    c.force_authenticate(user=b)
    r = c.post("/api/v1/sales/", {"shift_id": shift.id, "lines": [{"item_unit_id": unit.id, "qty": 1}], "payments": [{"method": "CASH", "amount": 1}]}, format="json")
    sale_id = r.data["id"]
    c2 = APIClient()
    c2.force_authenticate(user=owner)
    c2.post(f"/api/v1/sales/{sale_id}/void/", {"pin": "9999", "reason": "x"}, format="json")
    r2 = c2.post(f"/api/v1/sales/{sale_id}/void/", {"pin": "9999", "reason": "x"}, format="json")
    assert r2.status_code == 400


@pytest.mark.django_db
def test_bartender_void_gets_403():
    User = get_user_model()
    b = User.objects.create_user(username="bw3", password="x", role=User.BARTENDER, pin_hash="1111")
    item = Item.objects.create(name_en="Z", name_sw="Z", category=Item.BEER, base_unit=Item.BOTTLE, buy_price=1, par_level=1)
    unit = ItemUnit.objects.create(item=item, label="Bottle", qty_in_base_unit=1, sell_price=1, can_sell=True)
    shift = Shift.objects.create(opened_by=b, status=Shift.OPEN)
    c = APIClient()
    c.force_authenticate(user=b)
    r = c.post("/api/v1/sales/", {"shift_id": shift.id, "lines": [{"item_unit_id": unit.id, "qty": 1}], "payments": [{"method": "CASH", "amount": 1}]}, format="json")
    sale_id = r.data["id"]
    rv = c.post(f"/api/v1/sales/{sale_id}/void/", {"pin": "1111", "reason": "x"}, format="json")
    assert rv.status_code == 403


@pytest.mark.django_db
def test_zero_negative_quantity_rejected():
    User = get_user_model()
    u = User.objects.create_user(username="bq", password="x")
    item = Item.objects.create(name_en="Q", name_sw="Q", category=Item.BEER, base_unit=Item.BOTTLE, buy_price=1, par_level=1)
    unit = ItemUnit.objects.create(item=item, label="Bottle", qty_in_base_unit=1, sell_price=1, can_sell=True)
    shift = Shift.objects.create(opened_by=u, status=Shift.OPEN)
    c = APIClient()
    c.force_authenticate(user=u)
    r = c.post("/api/v1/sales/", {"shift_id": shift.id, "lines": [{"item_unit_id": unit.id, "qty": 0}], "payments": [{"method": "CASH", "amount": 0}]}, format="json")
    assert r.status_code == 400


@pytest.mark.django_db
def test_sale_on_closed_shift_rejected():
    User = get_user_model()
    u = User.objects.create_user(username="bs", password="x")
    item = Item.objects.create(name_en="S2", name_sw="S2", category=Item.BEER, base_unit=Item.BOTTLE, buy_price=1, par_level=1)
    unit = ItemUnit.objects.create(item=item, label="Bottle", qty_in_base_unit=1, sell_price=1, can_sell=True)
    shift = Shift.objects.create(opened_by=u, status="APPROVED")
    c = APIClient()
    c.force_authenticate(user=u)
    r = c.post("/api/v1/sales/", {"shift_id": shift.id, "lines": [{"item_unit_id": unit.id, "qty": 1}], "payments": [{"method": "CASH", "amount": 1}]}, format="json")
    assert r.status_code == 400


@pytest.mark.django_db
def test_bartender_cannot_create_adjustment():
    User = get_user_model()
    u = User.objects.create_user(username="ba2", password="x", role="BARTENDER")
    item = Item.objects.create(name_en="A2", name_sw="A2", category=Item.BEER, base_unit=Item.BOTTLE, buy_price=1, par_level=1)
    shift = Shift.objects.create(opened_by=u, status=Shift.OPEN)
    c = APIClient()
    c.force_authenticate(user=u)
    r = c.post("/api/v1/stock-movements/", {"item_id": item.id, "shift_id": shift.id, "type": "ADJUSTMENT", "qty_base": 5, "reason": "x"}, format="json")
    assert r.status_code == 403


@pytest.mark.django_db
def test_pin_lockout_after_five_failures():
    User = get_user_model()
    owner = User.objects.create_user(username="lock", password="x", role=User.OWNER, pin_hash="1234")
    b = User.objects.create_user(username="lockb", password="x", role=User.BARTENDER)
    item = Item.objects.create(name_en="L", name_sw="L", category=Item.BEER, base_unit=Item.BOTTLE, buy_price=1, par_level=1)
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
    rv2 = c2.post(f"/api/v1/sales/{sale_id}/void/", {"pin": "1234", "reason": "x"}, format="json")
    assert rv2.status_code == 403
    assert rv2.data.get("code") == "PIN_LOCKED"


@pytest.mark.django_db
def test_idempotent_sale_by_client_uuid():
    User = get_user_model()
    u = User.objects.create_user(username="bi", password="x")
    item = Item.objects.create(name_en="I", name_sw="I", category=Item.BEER, base_unit=Item.BOTTLE, buy_price=1, par_level=100)
    unit = ItemUnit.objects.create(item=item, label="Bottle", qty_in_base_unit=1, sell_price=2, can_sell=True)
    shift = Shift.objects.create(opened_by=u, status=Shift.OPEN)
    c = APIClient()
    c.force_authenticate(user=u)
    cid = str(uuid.uuid4())
    r1 = c.post("/api/v1/sales/", {"client_uuid": cid, "shift_id": shift.id, "lines": [{"item_unit_id": unit.id, "qty": 1}], "payments": [{"method": "CASH", "amount": 2}]}, format="json")
    assert r1.status_code == 201
    r2 = c.post("/api/v1/sales/", {"client_uuid": cid, "shift_id": shift.id, "lines": [{"item_unit_id": unit.id, "qty": 1}], "payments": [{"method": "CASH", "amount": 2}]}, format="json")
    assert r2.status_code == 201
    assert Sale.objects.filter(client_uuid=cid).count() == 1
    assert StockMovement.objects.filter(type=StockMovement.SALE, item=item).count() == 1


@pytest.mark.django_db
def test_negative_stock_allowed_but_flagged():
    User = get_user_model()
    u = User.objects.create_user(username="bn", password="x")
    item = Item.objects.create(name_en="N", name_sw="N", category=Item.BEER, base_unit=Item.BOTTLE, buy_price=1, par_level=1)
    unit = ItemUnit.objects.create(item=item, label="Bottle", qty_in_base_unit=1, sell_price=5, can_sell=True)
    shift = Shift.objects.create(opened_by=u, status=Shift.OPEN)
    c = APIClient()
    c.force_authenticate(user=u)
    r = c.post("/api/v1/sales/", {"shift_id": shift.id, "lines": [{"item_unit_id": unit.id, "qty": 10}], "payments": [{"method": "CASH", "amount": 50}]}, format="json")
    assert r.status_code == 201
    assert r.data.get("negative_stock_flag") is True
    from audit.models import AuditLog
    assert AuditLog.objects.filter(action="NEGATIVE_STOCK_SALE").exists()
