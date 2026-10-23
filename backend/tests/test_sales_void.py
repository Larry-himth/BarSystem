import uuid

import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

from catalog.models import Item, ItemUnit
from shifts.models import Shift
from stock.models import StockMovement


def make_sale(owner_pin="9999"):
    User = get_user_model()
    owner = User.objects.create_user(
        username="void-owner", password="x", role=User.OWNER, pin_hash=owner_pin
    )
    bartender = User.objects.create_user(username="void-bartender", password="x", role=User.BARTENDER)
    item = Item.objects.create(
        name_en="Void Beer",
        name_sw="Void Beer",
        category=Item.BEER,
        base_unit=Item.BOTTLE,
        buy_price=2000,
        par_level=24,
    )
    unit = ItemUnit.objects.create(
        item=item, label="Bottle", qty_in_base_unit=1, sell_price=3000, can_sell=True
    )
    shift = Shift.objects.create(opened_by=bartender, status=Shift.OPEN)
    client = APIClient()
    client.force_authenticate(user=bartender)
    response = client.post(
        "/api/v1/sales/",
        {
            "shift_id": shift.id,
            "lines": [{"item_unit_id": unit.id, "qty": 1}],
            "payments": [{"method": "CASH", "amount": 3000}],
        },
        format="json",
    )
    assert response.status_code == 201
    return owner, response.data["id"], shift, item


@pytest.mark.django_db
def test_void_with_wrong_pin_is_rejected():
    owner, sale_id, _, _ = make_sale(owner_pin="9999")
    from sales.models import Sale

    client = APIClient()
    client.force_authenticate(user=owner)
    response = client.post(
        f"/api/v1/sales/{sale_id}/void/",
        {"pin": "0000", "reason": "wrong pin"},
        format="json",
    )

    assert response.status_code == 403
    sale = Sale.objects.get(pk=sale_id)
    assert sale.voided_at is None
    assert not StockMovement.objects.filter(
        type=StockMovement.ADJUSTMENT, reason=f"VOID {sale_id}"
    ).exists()


@pytest.mark.django_db
def test_voiding_already_voided_sale_is_rejected():
    owner, sale_id, _, _ = make_sale(owner_pin="9999")
    client = APIClient()
    client.force_authenticate(user=owner)

    first = client.post(
        f"/api/v1/sales/{sale_id}/void/",
        {"pin": "9999", "reason": "mistake"},
        format="json",
    )
    assert first.status_code == 200

    second = client.post(
        f"/api/v1/sales/{sale_id}/void/",
        {"pin": "9999", "reason": "again"},
        format="json",
    )

    assert second.status_code == 400
    assert second.data["code"] == "ALREADY_VOIDED"


@pytest.mark.django_db
def test_void_non_existent_sale_returns_404():
    User = get_user_model()
    owner = User.objects.create_user(
        username="void-owner-404", password="x", role=User.OWNER, pin_hash="9999"
    )
    client = APIClient()
    client.force_authenticate(user=owner)

    response = client.post(
        "/api/v1/sales/999999/void/",
        {"pin": "9999", "reason": "missing"},
        format="json",
    )

    assert response.status_code == 404
