import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework.test import APIClient

from catalog.models import Item
from sales.models import Payment, Sale
from shifts.models import Shift
from stock.models import StockMovement


def make_item(suffix="D", buy_price=1000):
    return Item.objects.create(
        name_en=f"Item {suffix}",
        name_sw=f"Item {suffix}",
        category=Item.BEER,
        base_unit=Item.BOTTLE,
        buy_price=buy_price,
        par_level=1,
    )


@pytest.mark.django_db
def test_bartender_cannot_read_shift_list_or_report():
    User = get_user_model()
    bartender = User.objects.create_user(username="read-bartender", password="x", role=User.BARTENDER)
    shift = Shift.objects.create(opened_by=bartender, status=Shift.OPEN)
    client = APIClient()
    client.force_authenticate(user=bartender)

    list_response = client.get("/api/v1/shifts/")
    assert list_response.status_code == 403
    assert list_response.data["code"] == "FORBIDDEN"

    report_response = client.get(f"/api/v1/shifts/{shift.id}/report/")
    assert report_response.status_code == 403
    assert report_response.data["code"] == "FORBIDDEN"


@pytest.mark.django_db
def test_report_item_totals_and_variance():
    User = get_user_model()
    manager = User.objects.create_user(username="read-manager", password="x", role=User.MANAGER)
    bartender = User.objects.create_user(username="read-owner-bartender", password="x", role=User.BARTENDER)
    item = make_item("V", buy_price=1000)
    shift = Shift.objects.create(opened_by=bartender, status=Shift.OPEN)
    StockMovement.objects.create(shift=shift, item=item, type=StockMovement.OPENING, qty_base=10, created_by=bartender)
    StockMovement.objects.create(shift=shift, item=item, type=StockMovement.DELIVERY, qty_base=5, created_by=bartender)
    StockMovement.objects.create(shift=shift, item=item, type=StockMovement.SALE, qty_base=-3, created_by=bartender)
    StockMovement.objects.create(shift=shift, item=item, type=StockMovement.CLOSING_COUNT, qty_base=11, created_by=bartender)

    client = APIClient()
    client.force_authenticate(user=manager)
    response = client.get(f"/api/v1/shifts/{shift.id}/report/")

    assert response.status_code == 200
    row = response.data["items"][0]
    assert row["opening"] == 10
    assert row["deliveries"] == 5
    assert row["sales"] == 3
    assert row["expected"] == 12
    assert row["counted"] == 11
    assert row["variance"] == -1
    assert row["variance_ugx"] == -1000


@pytest.mark.django_db
def test_report_excludes_voided_sales_from_cash_and_momo():
    User = get_user_model()
    manager = User.objects.create_user(username="read-manager-cash", password="x", role=User.MANAGER)
    bartender = User.objects.create_user(username="read-bartender-cash", password="x", role=User.BARTENDER)
    shift = Shift.objects.create(opened_by=bartender, status=Shift.OPEN)

    active_cash = Sale.objects.create(shift=shift, total=2000, created_by=bartender)
    Payment.objects.create(sale=active_cash, method=Payment.CASH, amount=2000)

    active_momo = Sale.objects.create(shift=shift, total=1000, created_by=bartender)
    Payment.objects.create(sale=active_momo, method=Payment.MOMO, amount=1000, momo_ref="OK123")

    voided_cash = Sale.objects.create(shift=shift, total=4000, created_by=bartender, voided_at=timezone.now())
    Payment.objects.create(sale=voided_cash, method=Payment.CASH, amount=4000)

    voided_momo = Sale.objects.create(shift=shift, total=500, created_by=bartender, voided_at=timezone.now())
    Payment.objects.create(sale=voided_momo, method=Payment.MOMO, amount=500, momo_ref="VOIDREF")

    client = APIClient()
    client.force_authenticate(user=manager)
    response = client.get(f"/api/v1/shifts/{shift.id}/report/")

    assert response.status_code == 200
    assert response.data["expected_cash"] == 2000
    assert response.data["expected_momo"] == 1000
    assert response.data["momo_refs"] == ["OK123"]


@pytest.mark.django_db
def test_shift_list_newest_first_with_status_and_opener():
    User = get_user_model()
    manager = User.objects.create_user(username="read-list-manager", password="x", role=User.MANAGER)
    bartender = User.objects.create_user(username="read-list-bartender", password="x", role=User.BARTENDER)
    older = Shift.objects.create(opened_by=bartender, status=Shift.APPROVED)
    newer = Shift.objects.create(opened_by=manager, status=Shift.SUBMITTED)

    client = APIClient()
    client.force_authenticate(user=manager)
    response = client.get("/api/v1/shifts/")

    assert response.status_code == 200
    assert [row["id"] for row in response.data] == [newer.id, older.id]
    assert response.data[0]["status"] == Shift.SUBMITTED
    assert response.data[0]["opened_by_username"] == "read-list-manager"
    assert response.data[1]["opened_by_username"] == "read-list-bartender"
