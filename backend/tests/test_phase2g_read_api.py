import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

from catalog.models import Item, ItemUnit
from shifts.models import Shift
from stock.models import StockMovement
from stock.services import current_stock


def make_user(username, role):
    User = get_user_model()
    return User.objects.create_user(username=username, password="x", role=role)


def make_item(name, category=Item.BEER, buy_price=1000, par_level=10, is_active=True):
    return Item.objects.create(
        name_en=name,
        name_sw=name,
        category=category,
        base_unit=Item.BOTTLE,
        buy_price=buy_price,
        par_level=par_level,
        icon="",
        is_active=is_active,
    )


def make_shift(user):
    return Shift.objects.create(opened_by=user, status=Shift.OPEN)


def add_stock(shift, item, user, movement_type, qty):
    return StockMovement.objects.create(
        shift=shift,
        item=item,
        type=movement_type,
        qty_base=qty,
        created_by=user,
    )


def walk_keys(value):
    if isinstance(value, dict):
        for key, child in value.items():
            yield key
            yield from walk_keys(child)
    elif isinstance(value, list):
        for child in value:
            yield from walk_keys(child)


@pytest.mark.django_db
def test_bartender_items_hide_cost_and_quantity_fields():
    bartender = make_user("items-bartender", "BARTENDER")
    item = make_item("Hidden Cost")
    ItemUnit.objects.create(
        item=item,
        label="Bottle",
        qty_in_base_unit=1,
        sell_price=3000,
        can_sell=True,
    )

    client = APIClient()
    client.force_authenticate(user=bartender)
    response = client.get("/api/v1/items/")

    assert response.status_code == 200
    keys = set(walk_keys(response.data))
    assert "buy_price" not in keys
    assert "par_level" not in keys
    assert "stock_base" not in keys
    assert "quantity" not in keys
    assert "qty" not in keys
    assert response.data[0]["units"][0]["label_en"] == "Bottle"
    assert response.data[0]["units"][0]["label_sw"] == "Bottle"
    assert response.data[0]["units"][0]["qty_in_base_unit"] == 1


@pytest.mark.django_db
def test_manager_items_include_cost_fields():
    manager = make_user("items-manager", "MANAGER")
    make_item("Manager Cost")

    client = APIClient()
    client.force_authenticate(user=manager)
    response = client.get("/api/v1/items/")

    assert response.status_code == 200
    assert response.data[0]["buy_price"] == 1000
    assert response.data[0]["par_level"] == 10


@pytest.mark.django_db
def test_items_exclude_inactive_and_order_by_category_then_name():
    bartender = make_user("items-order", "BARTENDER")
    make_item("Zulu", category=Item.BEER)
    make_item("Alpha", category=Item.BEER)
    make_item("Spirit", category=Item.SPIRIT)
    make_item("Inactive", category=Item.BEER, is_active=False)

    client = APIClient()
    client.force_authenticate(user=bartender)
    response = client.get("/api/v1/items/")

    assert response.status_code == 200
    assert [row["name_en"] for row in response.data] == ["Alpha", "Zulu", "Spirit"]


@pytest.mark.django_db
def test_bartender_cannot_read_stock_list():
    bartender = make_user("stock-bartender", "BARTENDER")

    client = APIClient()
    client.force_authenticate(user=bartender)
    response = client.get("/api/v1/stock/")

    assert response.status_code == 403
    assert response.data["code"] == "FORBIDDEN"


@pytest.mark.django_db
def test_manager_stock_list_marks_low_stock():
    manager = make_user("stock-manager", "MANAGER")
    shift = make_shift(manager)
    low_item = make_item("Low", par_level=10)
    ok_item = make_item("OK", par_level=10)
    add_stock(shift, low_item, manager, StockMovement.OPENING, 7)
    add_stock(shift, ok_item, manager, StockMovement.OPENING, 12)

    client = APIClient()
    client.force_authenticate(user=manager)
    response = client.get("/api/v1/stock/")

    assert response.status_code == 200
    rows = {row["item_id"]: row for row in response.data}
    assert rows[low_item.id]["stock_base"] == 7
    assert rows[low_item.id]["par_level"] == 10
    assert rows[low_item.id]["is_low"] is True
    assert rows[ok_item.id]["stock_base"] == 12
    assert rows[ok_item.id]["is_low"] is False


@pytest.mark.django_db
def test_manager_stock_balance_restored_after_void_reversal():
    manager = make_user("stock-void", "MANAGER")
    shift = make_shift(manager)
    item = make_item("Voided", par_level=10)
    add_stock(shift, item, manager, StockMovement.OPENING, 10)

    sale = add_stock(shift, item, manager, StockMovement.SALE, -3)
    client = APIClient()
    client.force_authenticate(user=manager)
    after_sale = client.get("/api/v1/stock/")
    assert {row["item_id"]: row for row in after_sale.data}[item.id]["stock_base"] == 7

    add_stock(shift, item, manager, StockMovement.VOID_REVERSAL, 3)
    after_void = client.get("/api/v1/stock/")
    assert {row["item_id"]: row for row in after_void.data}[item.id]["stock_base"] == 10
    assert current_stock(item) == 10
    assert sale.type == StockMovement.SALE


@pytest.mark.django_db
def test_me_patch_updates_only_language():
    bartender = make_user("me-language", "BARTENDER")

    client = APIClient()
    client.force_authenticate(user=bartender)
    response = client.patch("/api/v1/auth/me/", {"language": "sw"}, format="json")

    assert response.status_code == 200
    assert response.data == {"id": bartender.id, "username": "me-language", "role": "BARTENDER", "language": "sw"}
    bartender.refresh_from_db()
    assert bartender.language == "sw"
    assert bartender.role == "BARTENDER"
    assert bartender.username == "me-language"

    invalid = client.patch("/api/v1/auth/me/", {"language": "xx"}, format="json")
    assert invalid.status_code == 400
    assert invalid.data["code"] == "INVALID_LANGUAGE"

    role_change = client.patch("/api/v1/auth/me/", {"role": "OWNER"}, format="json")
    assert role_change.status_code == 400
    assert role_change.data["code"] == "INVALID_FIELDS"


@pytest.mark.django_db
def test_me_requires_authentication():
    client = APIClient()
    response = client.patch("/api/v1/auth/me/", {"language": "sw"}, format="json")

    assert response.status_code == 401
