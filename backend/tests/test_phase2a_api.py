import uuid

import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

from catalog.models import Item, ItemUnit
from shifts.models import Shift
from stock.models import StockMovement


@pytest.mark.django_db
def test_pin_login_and_jwt():
    User = get_user_model()
    from django.contrib.auth.hashers import make_password

    u = User.objects.create_user(username="b", password="x", pin_hash=make_password("1111"))
    c = APIClient()
    r = c.post("/api/v1/auth/login/", {"username": "b", "pin": "1111"}, format="json")
    assert r.status_code == 200
    assert "access" in r.data


@pytest.mark.django_db
def test_open_shift_only_one():
    User = get_user_model()
    u = User.objects.create_user(username="b2", password="x")
    c = APIClient()
    c.force_authenticate(user=u)
    r1 = c.post("/api/v1/shifts/open/", {}, format="json")
    assert r1.status_code == 201
    r2 = c.post("/api/v1/shifts/open/", {}, format="json")
    assert r2.status_code in (400, 409)


@pytest.mark.django_db
def test_sell_creates_sale_and_negative_movements():
    User = get_user_model()
    u = User.objects.create_user(username="b3", password="x", role="BARTENDER")
    item = Item.objects.create(
        name_en="Nile",
        name_sw="Nile",
        category=Item.BEER,
        base_unit=Item.BOTTLE,
        buy_price=2000,
        par_level=24,
        is_active=True,
    )
    unit = ItemUnit.objects.create(item=item, label="Bottle", qty_in_base_unit=1, sell_price=3000, can_sell=True)
    shift = Shift.objects.create(opened_by=u, status=Shift.OPEN)
    StockMovement.objects.create(uuid=uuid.uuid4(), item=item, shift=shift, qty_base=10, type=StockMovement.OPENING, reason="", created_by=u)

    c = APIClient()
    c.force_authenticate(user=u)
    r = c.post(
        "/api/v1/sales/",
        {
            "shift_id": shift.id,
            "lines": [{"item_unit_id": unit.id, "qty": 2}],
            "payments": [{"method": "CASH", "amount": 6000}],
        },
        format="json",
    )
    assert r.status_code == 201
    assert StockMovement.objects.filter(type=StockMovement.SALE, qty_base=-2).exists()


@pytest.mark.django_db
def test_void_requires_manager_pin_and_writes_reversing():
    User = get_user_model()
    from django.contrib.auth.hashers import make_password

    owner = User.objects.create_user(username="o", password="x", role="OWNER", pin_hash=make_password("9999"))
    b = User.objects.create_user(username="b4", password="x", role="BARTENDER")
    item = Item.objects.create(name_en="S", name_sw="S", category=Item.BEER, base_unit=Item.BOTTLE, buy_price=1, par_level=1)
    unit = ItemUnit.objects.create(item=item, label="Bottle", qty_in_base_unit=1, sell_price=1, can_sell=True)
    shift = Shift.objects.create(opened_by=b, status=Shift.OPEN)
    c = APIClient()
    c.force_authenticate(user=b)
    r = c.post("/api/v1/sales/", {"shift_id": shift.id, "lines": [{"item_unit_id": unit.id, "qty": 1}], "payments": [{"method": "CASH", "amount": 1}]}, format="json")
    sale_id = r.data["id"]
    c2 = APIClient()
    c2.force_authenticate(user=owner)
    rv = c2.post(f"/api/v1/sales/{sale_id}/void/", {"pin": "9999", "reason": "mistake"}, format="json")
    assert rv.status_code == 200
    assert StockMovement.objects.filter(type=StockMovement.VOID_REVERSAL).count() >= 1


@pytest.mark.django_db
def test_delivery_spillage_comp_create_movements():
    User = get_user_model()
    u = User.objects.create_user(username="b5", password="x")
    item = Item.objects.create(name_en="D", name_sw="D", category=Item.BEER, base_unit=Item.BOTTLE, buy_price=1, par_level=1)
    shift = Shift.objects.create(opened_by=u, status=Shift.OPEN)
    c = APIClient()
    c.force_authenticate(user=u)
    rd = c.post("/api/v1/stock-movements/", {"item_id": item.id, "shift_id": shift.id, "type": "DELIVERY", "qty_base": 12, "reason": ""}, format="json")
    assert rd.status_code == 201
    rs = c.post("/api/v1/stock-movements/", {"item_id": item.id, "shift_id": shift.id, "type": "SPILLAGE", "qty_base": -1, "reason": "broke"}, format="json")
    assert rs.status_status_code if False else rs.status_code == 201
    rs2 = c.post("/api/v1/stock-movements/", {"item_id": item.id, "shift_id": shift.id, "type": "SPILLAGE", "qty_base": -1, "reason": "broke"}, format="json")
    assert rs2.status_code == 201
    rc = c.post("/api/v1/stock-movements/", {"item_id": item.id, "shift_id": shift.id, "type": "COMP", "qty_base": -1, "reason": "comp"}, format="json")
    assert rc.status_code == 201


@pytest.mark.django_db
def test_audit_log_written_on_void():
    User = get_user_model()
    from django.contrib.auth.hashers import make_password

    owner = User.objects.create_user(username="oa", password="x", role="OWNER", pin_hash=make_password("8888"))
    b = User.objects.create_user(username="ba", password="x", role="BARTENDER")
    item = Item.objects.create(name_en="A", name_sw="A", category=Item.BEER, base_unit=Item.BOTTLE, buy_price=1, par_level=1)
    unit = ItemUnit.objects.create(item=item, label="Bottle", qty_in_base_unit=1, sell_price=1, can_sell=True)
    shift = Shift.objects.create(opened_by=b, status=Shift.OPEN)
    c = APIClient()
    c.force_authenticate(user=b)
    r = c.post("/api/v1/sales/", {"shift_id": shift.id, "lines": [{"item_unit_id": unit.id, "qty": 1}], "payments": [{"method": "CASH", "amount": 1}]}, format="json")
    sale_id = r.data["id"]
    c2 = APIClient()
    c2.force_authenticate(user=owner)
    c2.post(f"/api/v1/sales/{sale_id}/void/", {"pin": "8888", "reason": "err"}, format="json")
    from audit.models import AuditLog
    assert AuditLog.objects.filter(action="VOID").exists()
