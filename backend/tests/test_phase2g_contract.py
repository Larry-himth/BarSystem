import uuid

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework.fields import DateTimeField
from rest_framework.test import APIClient

from catalog.models import Item, ItemUnit
from sales.models import Payment, Sale, SaleLine
from shifts.models import Shift


def make_user(username, role):
    User = get_user_model()
    return User.objects.create_user(username=username, password="x", role=role)


def make_item(name):
    return Item.objects.create(
        name_en=name,
        name_sw=name,
        category=Item.BEER,
        base_unit=Item.BOTTLE,
        buy_price=1000,
        par_level=10,
        icon="",
    )


def make_shift(user, status=Shift.OPEN):
    return Shift.objects.create(opened_by=user, status=status)


def make_sale(shift, user, unit, total=3000, voided=False):
    sale = Sale.objects.create(
        uuid=uuid.uuid4(),
        shift=shift,
        total=total,
        created_by=user,
        voided_at=timezone.now() if voided else None,
    )
    SaleLine.objects.create(
        sale=sale,
        item_unit=unit,
        qty=1,
        unit_price=total,
        line_total=total,
    )
    Payment.objects.create(sale=sale, method=Payment.CASH, amount=total, momo_ref="")
    sale.refresh_from_db()
    return sale


def dt(value):
    return DateTimeField().to_representation(value)


@pytest.mark.django_db
def test_current_shift_returns_null_when_none_open():
    bartender = make_user("current-none", "BARTENDER")
    make_shift(bartender, status=Shift.APPROVED)

    client = APIClient()
    client.force_authenticate(user=bartender)
    response = client.get("/api/v1/shifts/current/")

    assert response.status_code == 200
    assert response.data == {"shift": None}


@pytest.mark.django_db
def test_current_shift_returns_open_shift_for_any_role():
    manager = make_user("current-manager", "MANAGER")
    shift = make_shift(manager)

    client = APIClient()
    client.force_authenticate(user=manager)
    response = client.get("/api/v1/shifts/current/")

    assert response.status_code == 200
    assert response.data == {
        "id": shift.id,
        "status": "OPEN",
        "opened_by_username": "current-manager",
        "opened_at": dt(shift.opened_at),
    }


@pytest.mark.django_db
def test_bartender_lists_only_open_shift_sales_with_exact_shape():
    bartender = make_user("sales-bartender-open", "BARTENDER")
    shift = make_shift(bartender)
    item = make_item("Contract Beer")
    unit = ItemUnit.objects.create(
        item=item,
        label="Bottle",
        label_sw="Chupa",
        qty_in_base_unit=1,
        sell_price=3000,
        can_sell=True,
    )
    older_sale = make_sale(shift, bartender, unit)
    voided_sale = make_sale(shift, bartender, unit, voided=True)

    client = APIClient()
    client.force_authenticate(user=bartender)
    response = client.get(f"/api/v1/sales/?shift_id={shift.id}")

    assert response.status_code == 200
    assert response.data == [
        {
            "id": voided_sale.id,
            "total": 3000,
            "created_at": dt(voided_sale.created_at),
            "created_by_username": "sales-bartender-open",
            "is_voided": True,
            "lines": [
                {
                    "label_en": "Bottle",
                    "label_sw": "Chupa",
                    "qty": 1,
                    "unit_price": 3000,
                }
            ],
            "payments": [{"method": "CASH", "amount": 3000, "momo_ref": ""}],
        },
        {
            "id": older_sale.id,
            "total": 3000,
            "created_at": dt(older_sale.created_at),
            "created_by_username": "sales-bartender-open",
            "is_voided": False,
            "lines": [
                {
                    "label_en": "Bottle",
                    "label_sw": "Chupa",
                    "qty": 1,
                    "unit_price": 3000,
                }
            ],
            "payments": [{"method": "CASH", "amount": 3000, "momo_ref": ""}],
        },
    ]


@pytest.mark.django_db
def test_manager_lists_closed_shift_sales_but_bartender_gets_forbidden():
    manager = make_user("sales-manager-closed", "MANAGER")
    bartender = make_user("sales-bartender-closed", "BARTENDER")
    shift = make_shift(manager, status=Shift.APPROVED)
    item = make_item("Closed Shift Beer")
    unit = ItemUnit.objects.create(
        item=item,
        label="Bottle",
        qty_in_base_unit=1,
        sell_price=2500,
        can_sell=True,
    )
    sale = make_sale(shift, manager, unit, total=2500)

    manager_client = APIClient()
    manager_client.force_authenticate(user=manager)
    manager_response = manager_client.get(f"/api/v1/sales/?shift_id={shift.id}")

    assert manager_response.status_code == 200
    assert [row["id"] for row in manager_response.data] == [sale.id]
    assert manager_response.data[0]["is_voided"] is False

    bartender_client = APIClient()
    bartender_client.force_authenticate(user=bartender)
    bartender_response = bartender_client.get(f"/api/v1/sales/?shift_id={shift.id}")

    assert bartender_response.status_code == 403
    assert bartender_response.data == {
        "code": "FORBIDDEN",
        "message": "Bartenders may only list the open shift's sales",
    }


@pytest.mark.django_db
@pytest.mark.parametrize("query", ["", "?shift_id=not-an-integer"])
def test_sales_list_rejects_missing_or_invalid_shift_id_with_stable_code(query):
    bartender = make_user("sales-bartender-invalid-query", "BARTENDER")
    client = APIClient()
    client.force_authenticate(user=bartender)

    response = client.get(f"/api/v1/sales/{query}")

    assert response.status_code == 400
    assert response.data == {
        "code": "INVALID_SHIFT_ID",
        "message": "shift_id query parameter is required and must be an integer",
    }
