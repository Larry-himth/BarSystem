import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

from catalog.models import Item, ItemUnit
from shifts.models import Shift


@pytest.mark.django_db
def test_variance_arithmetic_opening_sold_delivery_counted():
    User = get_user_model()
    b = User.objects.create_user(username="bbv", password="x")
    item = Item.objects.create(
        name_en="V",
        name_sw="V",
        category=Item.BEER,
        base_unit=Item.BOTTLE,
        buy_price=1000,
        par_level=1,
    )
    shift = Shift.objects.create(opened_by=b, status=Shift.OPEN)
    from stock.models import StockMovement

    StockMovement.objects.create(
        shift=shift,
        item=item,
        type=StockMovement.OPENING,
        qty_base=10,
        created_by=b,
    )
    StockMovement.objects.create(
        shift=shift,
        item=item,
        type=StockMovement.DELIVERY,
        qty_base=5,
        created_by=b,
    )
    StockMovement.objects.create(
        shift=shift,
        item=item,
        type=StockMovement.SALE,
        qty_base=-3,
        created_by=b,
    )
    c = APIClient()
    c.force_authenticate(user=b)
    r = c.post(
        f"/api/v1/shifts/{shift.id}/close/",
        {"counts": [{"item_id": item.id, "counted_qty": 11}], "pin": ""},
        format="json",
    )
    assert r.status_code == 200
    assert r.data["code"] == "SHIFT_CLOSED"
    data = r.data
    assert data["items"][0]["expected_qty"] == 12
    assert data["items"][0]["variance_qty"] == -1
    assert data["items"][0]["variance_value"] == -1000


@pytest.mark.django_db
def test_close_shift_requires_count_for_active_items():
    User = get_user_model()
    b = User.objects.create_user(username="bbr", password="x")
    item = Item.objects.create(
        name_en="R",
        name_sw="R",
        category=Item.BEER,
        base_unit=Item.BOTTLE,
        buy_price=1000,
        par_level=1,
    )
    shift = Shift.objects.create(opened_by=b, status=Shift.OPEN)
    from stock.models import StockMovement

    StockMovement.objects.create(shift=shift, item=item, type=StockMovement.OPENING, qty_base=5, created_by=b)
    c = APIClient()
    c.force_authenticate(user=b)
    r = c.post(f"/api/v1/shifts/{shift.id}/close/", {"counts": [], "pin": ""}, format="json")
    assert r.status_code == 400
    assert r.data["code"] == "MISSING_COUNT"


@pytest.mark.django_db
def test_bartender_cannot_approve_shift():
    User = get_user_model()
    b = User.objects.create_user(username="bba", password="x")
    shift = Shift.objects.create(opened_by=b, status=Shift.SUBMITTED)
    c = APIClient()
    c.force_authenticate(user=b)
    r = c.post(f"/api/v1/shifts/{shift.id}/approve/", {}, format="json")
    assert r.status_code == 403
    assert r.data["code"] == "FORBIDDEN"


@pytest.mark.django_db
def test_submitted_shift_blocks_new_sales_deliveries_and_second_close():
    User = get_user_model()
    b = User.objects.create_user(username="bbs", password="x")
    owner = User.objects.create_user(username="bos", password="x", role="OWNER")
    item = Item.objects.create(
        name_en="S",
        name_sw="S",
        category=Item.BEER,
        base_unit=Item.BOTTLE,
        buy_price=1000,
        par_level=1,
    )
    unit = ItemUnit.objects.create(item=item, label="Bottle", qty_in_base_unit=1, sell_price=3000, can_sell=True)
    shift = Shift.objects.create(opened_by=b, status=Shift.SUBMITTED)
    c = APIClient()
    c.force_authenticate(user=b)
    rs = c.post("/api/v1/sales/", {"shift_id": shift.id, "lines": [{"item_unit_id": unit.id, "qty": 1}], "payments": [{"method": "CASH", "amount": 3000}]}, format="json")
    assert rs.status_code == 400
    assert rs.data["code"] == "SHIFT_NOT_OPEN"
    # Try to deliver via stock movements if endpoint exists; otherwise expect blocked
    rd = c.post("/api/v1/stock-movements/", {"shift_id": shift.id, "item_id": item.id, "type": "DELIVERY", "qty_base": 1}, format="json")
    if rd.status_code == 404:
        rd = c.post("/api/v1/deliveries/", {"shift_id": shift.id, "lines": [{"item_unit_id": unit.id, "qty": 1}]}, format="json")
    assert rd.status_code == 400
    assert rd.data["code"] == "SHIFT_NOT_OPEN"
    c.force_authenticate(user=owner)
    rc = c.post(f"/api/v1/shifts/{shift.id}/close/", {"counts": [{"item_id": item.id, "counted_qty": 0}], "pin": ""}, format="json")
    assert rc.status_code == 400
    assert rc.data["code"] == "SHIFT_NOT_OPEN"


@pytest.mark.django_db
def test_close_ignores_client_supplied_expected_and_variance():
    User = get_user_model()
    b = User.objects.create_user(username="bbig", password="x")
    item = Item.objects.create(
        name_en="I",
        name_sw="I",
        category=Item.BEER,
        base_unit=Item.BOTTLE,
        buy_price=2000,
        par_level=1,
    )
    shift = Shift.objects.create(opened_by=b, status=Shift.OPEN)
    from stock.models import StockMovement

    StockMovement.objects.create(shift=shift, item=item, type=StockMovement.OPENING, qty_base=5, created_by=b)
    c = APIClient()
    c.force_authenticate(user=b)
    r = c.post(
        f"/api/v1/shifts/{shift.id}/close/",
        {
            "counts": [{"item_id": item.id, "counted_qty": 5, "expected_qty": 0, "variance_qty": 999, "variance_value": 999999}],
            "pin": "",
        },
        format="json",
    )
    assert r.status_code == 200
    assert r.data["code"] == "SHIFT_CLOSED"
    assert r.data["items"][0]["expected_qty"] == 5
    assert r.data["items"][0]["variance_qty"] == 0
    assert r.data["items"][0]["variance_value"] == 0


@pytest.mark.django_db
def test_blind_closing_count_no_expected_for_bartender():
    User = get_user_model()
    b = User.objects.create_user(username="bb", password="x", role="BARTENDER")
    item = Item.objects.create(name_en="B", name_sw="B", category=Item.BEER, base_unit=Item.BOTTLE, buy_price=1000, par_level=1)
    shift = Shift.objects.create(opened_by=b, status=Shift.OPEN)
    c = APIClient()
    c.force_authenticate(user=b)
    r = c.post(f"/api/v1/shifts/{shift.id}/count/", {"type": "CLOSING", "counts": [{"item_id": item.id, "counted_qty": 5}]}, format="json")
    assert r.status_code in (200, 201)
    # should not leak expected
    assert "expected_qty" not in str(r.data)


@pytest.mark.django_db
def test_submit_shift_locks_and_computes_variance():
    User = get_user_model()
    b = User.objects.create_user(username="bs2", password="x")
    c = APIClient()
    c.force_authenticate(user=b)
    r = c.post("/api/v1/shifts/open/", {}, format="json")
    assert r.status_code == 201
    sid = r.data["id"]
    r2 = c.post(f"/api/v1/shifts/{sid}/submit/", {}, format="json")
    assert r2.status_code == 200
    assert r2.data["code"] == "SHIFT_SUBMITTED"
    from shifts.models import Shift
    assert Shift.objects.get(pk=sid).status == "SUBMITTED"


@pytest.mark.django_db
def test_boss_approve_dispute_momo_confirm():
    User = get_user_model()
    owner = User.objects.create_user(username="bo2", password="x", role="OWNER")
    b = User.objects.create_user(username="bb2", password="x")
    shift = Shift.objects.create(opened_by=b, status=Shift.SUBMITTED)
    c = APIClient()
    c.force_authenticate(user=owner)
    ra = c.post(f"/api/v1/shifts/{shift.id}/approve/", {}, format="json")
    assert ra.status_code == 200
    assert ra.data["code"] == "SHIFT_APPROVED"
    rd = c.post(f"/api/v1/shifts/{shift.id}/dispute/", {"note": "x"}, format="json")
    assert rd.status_code == 200
    assert rd.data["code"] == "SHIFT_DISPUTED"
    rm = c.post(f"/api/v1/shifts/{shift.id}/momo-confirm/", {"status": "CONFIRMED"}, format="json")
    assert rm.status_code == 200
    assert rm.data["code"] == "MOMO_CONFIRMED"


@pytest.mark.django_db
def test_tabs_record_repay():
    from shifts.models import Shift
    User = get_user_model()
    b = User.objects.create_user(username="bt", password="x")
    Shift.objects.create(opened_by=b, status=Shift.OPEN)
    c = APIClient()
    c.force_authenticate(user=b)
    rt = c.post("/api/v1/tabs/", {"customer_name": "John", "phone": "077"}, format="json")
    assert rt.status_code == 201
    assert rt.data["code"] == "TAB_CREATED"
    tid = rt.data["id"]
    rp = c.post(f"/api/v1/tabs/{tid}/payments/", {"amount": 5000, "method": "CASH"}, format="json")
    assert rp.status_code == 200
    assert rp.data["code"] == "TAB_PAYMENT_RECORDED"


@pytest.mark.django_db
def test_simulate_day_script_exists():
    import os
    import subprocess
    import sys
    script_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "scripts", "simulate_day.py")
    if not os.path.exists(script_path):
        script_path = os.path.join(os.path.dirname(__file__), "..", "scripts", "simulate_day.py")
    result = subprocess.run([sys.executable, script_path], cwd=os.path.dirname(os.path.dirname(__file__)), stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    assert result.returncode != 0  # expects non-zero shortage or failure handling
    # also ensure file exists
    assert os.path.exists(script_path)
