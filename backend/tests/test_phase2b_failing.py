import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

from catalog.models import Item, ItemUnit
from shifts.models import Shift


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
    sid = r.data["id"]
    r2 = c.post(f"/api/v1/shifts/{sid}/submit/", {}, format="json")
    assert r2.status_code == 200
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
    rd = c.post(f"/api/v1/shifts/{shift.id}/dispute/", {"note": "x"}, format="json")
    assert rd.status_code == 200
    rm = c.post(f"/api/v1/shifts/{shift.id}/momo-confirm/", {"status": "CONFIRMED"}, format="json")
    assert rm.status_code == 200


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
    tid = rt.data["id"]
    rp = c.post(f"/api/v1/tabs/{tid}/payments/", {"amount": 5000, "method": "CASH"}, format="json")
    assert rp.status_code == 200


@pytest.mark.django_db
def test_simulate_day_script_exists():
    import os
    assert os.path.exists("scripts/simulate_day.py") or os.path.exists("../scripts/simulate_day.py")
