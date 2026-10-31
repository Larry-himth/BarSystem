import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework.test import APIClient

from catalog.models import Item
from shifts.models import Shift, StockCount
from stock.models import StockMovement
from stock.services import current_stock


def make_item(name, buy_price=1000):
    return Item.objects.create(
        name_en=name,
        name_sw=name,
        category=Item.BEER,
        base_unit=Item.BOTTLE,
        buy_price=buy_price,
        par_level=1,
        is_active=True,
    )


def add_movement(shift, item, user, movement_type, qty):
    return StockMovement.objects.create(
        shift=shift,
        item=item,
        type=movement_type,
        qty_base=qty,
        created_by=user,
    )


@pytest.mark.django_db
def test_counts_never_change_current_stock():
    User = get_user_model()
    bartender = User.objects.create_user(username="count-invariant", password="x", role=User.BARTENDER)
    item = make_item("Invariant")
    shift = Shift.objects.create(opened_by=bartender, status=Shift.OPEN)
    add_movement(shift, item, bartender, StockMovement.OPENING, 24)

    client = APIClient()
    client.force_authenticate(user=bartender)
    for kind, counted_qty in [
        ("OPENING", 5),
        ("OPENING", 6),
        ("CLOSING", 20),
        ("CLOSING", 21),
    ]:
        response = client.post(
            f"/api/v1/shifts/{shift.id}/count/",
            {"type": kind, "counts": [{"item_id": item.id, "counted_qty": counted_qty}]},
            format="json",
        )
        assert response.status_code == 201
        assert current_stock(item) == 24

    assert StockMovement.objects.filter(shift=shift).count() == 1
    assert StockCount.objects.filter(shift=shift, kind=StockCount.OPENING).count() == 1
    assert StockCount.objects.filter(shift=shift, kind=StockCount.CLOSING).count() == 1


@pytest.mark.django_db
def test_bartender_opening_count_records_expected_without_leaking_it():
    User = get_user_model()
    bartender = User.objects.create_user(username="count-blind", password="x", role=User.BARTENDER)
    item = make_item("Blind")
    shift = Shift.objects.create(opened_by=bartender, status=Shift.OPEN)
    add_movement(shift, item, bartender, StockMovement.OPENING, 24)

    client = APIClient()
    client.force_authenticate(user=bartender)
    response = client.post(
        f"/api/v1/shifts/{shift.id}/count/",
        {"type": "OPENING", "counts": [{"item_id": item.id, "counted_qty": 5}]},
        format="json",
    )

    assert response.status_code == 201
    assert response.data == {"status": "recorded"}
    assert current_stock(item) == 24
    count = StockCount.objects.get(shift=shift, item=item, kind=StockCount.OPENING)
    assert count.counted_qty == 5
    assert count.expected_qty == 24


@pytest.mark.django_db
def test_report_and_approval_reconcile_closing_count_to_ledger():
    User = get_user_model()
    bartender = User.objects.create_user(username="count-close", password="x", role=User.BARTENDER)
    manager = User.objects.create_user(username="count-approve", password="x", role=User.MANAGER)
    item = make_item("Reconcile")
    shift = Shift.objects.create(opened_by=bartender, status=Shift.OPEN)
    add_movement(shift, item, bartender, StockMovement.OPENING, 10)
    add_movement(shift, item, bartender, StockMovement.DELIVERY, 5)
    add_movement(shift, item, bartender, StockMovement.SALE, -3)

    bartender_client = APIClient()
    bartender_client.force_authenticate(user=bartender)
    close_response = bartender_client.post(
        f"/api/v1/shifts/{shift.id}/close/",
        {"counts": [{"item_id": item.id, "counted_qty": 11}], "pin": ""},
        format="json",
    )
    assert close_response.status_code == 200
    assert close_response.data["code"] == "SHIFT_CLOSED"
    assert current_stock(item) == 12

    manager_client = APIClient()
    manager_client.force_authenticate(user=manager)
    report_response = manager_client.get(f"/api/v1/shifts/{shift.id}/report/")
    assert report_response.status_code == 200
    row = report_response.data["items"][0]
    assert row["opening"] == 10
    assert row["deliveries"] == 5
    assert row["sales"] == 3
    assert row["expected"] == 12
    assert row["counted"] == 11
    assert row["variance"] == -1
    assert row["variance_ugx"] == -1000

    approve_response = manager_client.post(f"/api/v1/shifts/{shift.id}/approve/", {}, format="json")
    assert approve_response.status_code == 200
    assert approve_response.data["code"] == "SHIFT_APPROVED"
    assert current_stock(item) == 11
    adjustments = StockMovement.objects.filter(
        shift=shift,
        item=item,
        type=StockMovement.ADJUSTMENT,
    )
    assert adjustments.count() == 1
    adjustment = adjustments.get()
    assert adjustment.qty_base == -1
    assert adjustment.created_by == manager
    assert adjustment.reason == f"count reconciliation shift {shift.id}"


@pytest.mark.django_db
def test_approving_twice_rejects_without_second_adjustment():
    User = get_user_model()
    bartender = User.objects.create_user(username="count-twice-b", password="x", role=User.BARTENDER)
    manager = User.objects.create_user(username="count-twice-m", password="x", role=User.MANAGER)
    item = make_item("Twice")
    shift = Shift.objects.create(opened_by=bartender, status=Shift.OPEN)
    add_movement(shift, item, bartender, StockMovement.OPENING, 10)

    bartender_client = APIClient()
    bartender_client.force_authenticate(user=bartender)
    bartender_client.post(
        f"/api/v1/shifts/{shift.id}/close/",
        {"counts": [{"item_id": item.id, "counted_qty": 8}], "pin": ""},
        format="json",
    )

    manager_client = APIClient()
    manager_client.force_authenticate(user=manager)
    assert manager_client.post(f"/api/v1/shifts/{shift.id}/approve/", {}, format="json").status_code == 200
    second_response = manager_client.post(f"/api/v1/shifts/{shift.id}/approve/", {}, format="json")

    assert second_response.status_code == 400
    assert StockMovement.objects.filter(
        shift=shift,
        type=StockMovement.ADJUSTMENT,
        reason=f"count reconciliation shift {shift.id}",
    ).count() == 1


@pytest.mark.django_db
def test_bartender_cannot_approve_count_reconciliation():
    User = get_user_model()
    bartender = User.objects.create_user(username="count-no-approve", password="x", role=User.BARTENDER)
    item = make_item("No approve")
    shift = Shift.objects.create(opened_by=bartender, status=Shift.SUBMITTED, closed_at=timezone.now())
    StockCount.objects.create(
        shift=shift,
        item=item,
        kind=StockCount.CLOSING,
        counted_qty=9,
        expected_qty=10,
        counted_by=bartender,
    )

    client = APIClient()
    client.force_authenticate(user=bartender)
    response = client.post(f"/api/v1/shifts/{shift.id}/approve/", {}, format="json")

    assert response.status_code == 403
    assert response.data["code"] == "FORBIDDEN"
    assert not StockMovement.objects.filter(shift=shift, type=StockMovement.ADJUSTMENT).exists()


@pytest.mark.django_db
def test_approval_skips_zero_count_adjustment():
    User = get_user_model()
    bartender = User.objects.create_user(username="count-zero-b", password="x", role=User.BARTENDER)
    manager = User.objects.create_user(username="count-zero-m", password="x", role=User.MANAGER)
    item = make_item("Zero")
    shift = Shift.objects.create(opened_by=bartender, status=Shift.OPEN)
    add_movement(shift, item, bartender, StockMovement.OPENING, 10)

    bartender_client = APIClient()
    bartender_client.force_authenticate(user=bartender)
    bartender_client.post(
        f"/api/v1/shifts/{shift.id}/close/",
        {"counts": [{"item_id": item.id, "counted_qty": 10}], "pin": ""},
        format="json",
    )

    manager_client = APIClient()
    manager_client.force_authenticate(user=manager)
    response = manager_client.post(f"/api/v1/shifts/{shift.id}/approve/", {}, format="json")

    assert response.status_code == 200
    assert not StockMovement.objects.filter(shift=shift, type=StockMovement.ADJUSTMENT).exists()
    assert current_stock(item) == 10

