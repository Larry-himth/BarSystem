import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

from catalog.models import Item
from shifts.models import Shift, StockCount
from stock.models import StockMovement


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


@pytest.mark.parametrize("count_type", ["OPENING", "CLOSING"])
@pytest.mark.django_db
def test_bartender_count_never_includes_expected_or_variance(count_type):
    User = get_user_model()
    bartender = User.objects.create_user(username=f"count-bartender-{count_type}", password="x", role=User.BARTENDER)
    item = make_item(f"Count {count_type}")
    shift = Shift.objects.create(opened_by=bartender, status=Shift.OPEN)

    client = APIClient()
    client.force_authenticate(user=bartender)
    response = client.post(
        f"/api/v1/shifts/{shift.id}/count/",
        {"type": count_type, "counts": [{"item_id": item.id, "counted_qty": 5}]},
        format="json",
    )

    assert response.status_code == 201
    assert "variances" not in response.data
    response_text = str(response.data).lower()
    assert "expected" not in response_text
    assert "variance" not in response_text


@pytest.mark.django_db
def test_count_on_submitted_shift_returns_shift_not_open():
    User = get_user_model()
    user = User.objects.create_user(username="count-submitted", password="x")
    item = make_item("Submitted count")
    shift = Shift.objects.create(opened_by=user, status=Shift.SUBMITTED)

    client = APIClient()
    client.force_authenticate(user=user)
    response = client.post(
        f"/api/v1/shifts/{shift.id}/count/",
        {"type": "CLOSING", "counts": [{"item_id": item.id, "counted_qty": 5}]},
        format="json",
    )

    assert response.status_code == 400
    assert response.data["code"] == "SHIFT_NOT_OPEN"


@pytest.mark.django_db
def test_submit_without_counts_is_rejected():
    User = get_user_model()
    user = User.objects.create_user(username="submit-no-counts", password="x")
    item = make_item("Submit item")
    shift = Shift.objects.create(opened_by=user, status=Shift.OPEN)
    StockMovement.objects.create(
        shift=shift,
        item=item,
        type=StockMovement.OPENING,
        qty_base=10,
        created_by=user,
    )

    client = APIClient()
    client.force_authenticate(user=user)
    response = client.post(f"/api/v1/shifts/{shift.id}/submit/", {}, format="json")

    assert response.status_code == 400
    assert response.data["code"] == "COUNT_INCOMPLETE"
    shift.refresh_from_db()
    assert shift.status == Shift.OPEN


@pytest.mark.django_db
def test_close_requires_counts_for_every_active_item():
    User = get_user_model()
    user = User.objects.create_user(username="close-two-items", password="x")
    counted_item = make_item("Counted item")
    missing_item = make_item("Missing item")
    shift = Shift.objects.create(opened_by=user, status=Shift.OPEN)
    StockMovement.objects.create(
        shift=shift,
        item=counted_item,
        type=StockMovement.OPENING,
        qty_base=10,
        created_by=user,
    )

    client = APIClient()
    client.force_authenticate(user=user)
    response = client.post(
        f"/api/v1/shifts/{shift.id}/close/",
        {"counts": [{"item_id": counted_item.id, "counted_qty": 10}], "pin": ""},
        format="json",
    )

    assert response.status_code == 400
    assert response.data["code"] == "COUNT_INCOMPLETE"
    shift.refresh_from_db()
    assert shift.status == Shift.OPEN
    assert not StockCount.objects.filter(shift=shift).exists()
    assert StockMovement.objects.filter(shift=shift).count() == 1


@pytest.mark.django_db
def test_close_rejects_duplicate_counts():
    User = get_user_model()
    user = User.objects.create_user(username="close-duplicates", password="x")
    item = make_item("Duplicate item")
    shift = Shift.objects.create(opened_by=user, status=Shift.OPEN)
    StockMovement.objects.create(
        shift=shift,
        item=item,
        type=StockMovement.OPENING,
        qty_base=10,
        created_by=user,
    )

    client = APIClient()
    client.force_authenticate(user=user)
    response = client.post(
        f"/api/v1/shifts/{shift.id}/close/",
        {
            "counts": [
                {"item_id": item.id, "counted_qty": 10},
                {"item_id": item.id, "counted_qty": 10},
            ],
            "pin": "",
        },
        format="json",
    )

    assert response.status_code == 400
    assert response.data["code"] == "COUNT_INCOMPLETE"
