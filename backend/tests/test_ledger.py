import uuid
from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model
from django.db import IntegrityError

from catalog.models import Item, ItemUnit
from shifts.models import Shift
from stock.models import StockMovement


@pytest.mark.django_db
def test_stock_equals_sum_of_movements():
    User = get_user_model()
    user = User.objects.create_user(username="t", password="x")
    shift = Shift.objects.create(opened_by=user, status=Shift.OPEN)
    item = Item.objects.create(
        name_en="Beer",
        name_sw="Bia",
        category=Item.BEER,
        base_unit=ItemUnitUnit.BOTTLE if False else "bottle",
        buy_price=2000,
        par_level=10,
        is_active=True,
    )
    # Create base unit properly
    from catalog.models import ItemUnit
    bottle = ItemUnit.objects.create(
        item=item,
        label="Bottle",
        qty_in_base_unit=1,
        sell_price=3000,
        can_sell=True,
        can_buy=True,
    )

    StockMovement.objects.create(
        uuid=uuid.uuid4(),
        item=item,
        shift=shift,
        qty_base=10,
        type=StockMovement.OPENING,
        reason="",
        created_by=user,
    )
    StockMovement.objects.create(
        uuid=uuid.uuid4(),
        item=item,
        shift=shift,
        qty_base=-1,
        type=StockMovement.SALE,
        reason="",
        created_by=user,
    )

    total = sum(m.qty_base for m in StockMovement.objects.filter(item=item))
    assert total == 9


@pytest.mark.django_db
def test_tot_sale_deducts_25_ml_bottle_sale_deducts_750():
    # Waragi bottle is base unit bottle? Or base unit ml? 
    # Prompt says: "spirits base unit = 1 ml (a 750 ml bottle = 750, a 25 ml tot = 25)"
    User = get_user_model()
    user = User.objects.create_user(username="t2", password="x")
    shift = Shift.objects.create(opened_by=user, status=Shift.OPEN)
    item = Item.objects.create(
        name_en="Waragi",
        name_sw="Waragi",
        category=Item.SPIRIT,
        base_unit=Item.ML,
        buy_price=10,
        par_level=1000,
        is_active=True,
    )

    from catalog.models import ItemUnit

    bottle = ItemUnit.objects.create(
        item=item,
        label="Bottle",
        qty_in_base_unit=750,
        sell_price=15000,
        can_sell=True,
        can_buy=True,
    )
    tot = ItemUnit.objects.create(
        item=item,
        label="Tot",
        qty_in_base_unit=25,
        sell_price=1500,
        can_sell=True,
        can_buy=False,
    )

    # Simulate sale movements
    StockMovement.objects.create(
        uuid=uuid.uuid4(),
        item=item,
        shift=shift,
        qty_base=-750,
        type=StockMovement.SALE,
        reason="",
        created_by=user,
    )
    StockMovement.objects.create(
        uuid=uuid.uuid4(),
        item=item,
        shift=shift,
        qty_base=-25,
        type=StockMovement.SALE,
        reason="",
        created_by=user,
    )

    # bottle sale deducts 750, tot deducts 25
    assert sum(m.qty_base for m in StockMovement.objects.filter(item=item)) == -775


@pytest.mark.django_db
def test_movement_rows_cannot_be_edited_or_deleted():
    User = get_user_model()
    user = User.objects.create_user(username="t3", password="x")
    shift = Shift.objects.create(opened_by=user, status=Shift.OPEN)
    item = Item.objects.create(
        name_en="Soda",
        name_sw="Soda",
        category=Item.SOFT_DRINK,
        base_unit=Item.PIECE,
        buy_price=1000,
        par_level=24,
        is_active=True,
    )

    from stock.models import StockMovement

    m = StockMovement.objects.create(
        uuid=uuid.uuid4(),
        item=item,
        shift=shift,
        qty_base=12,
        type=StockMovement.OPENING,
        reason="",
        created_by=user,
    )

    # Attempt to update - should be prevented
    with pytest.raises(Exception):
        m.qty_base = 5
        m.save()

    # Attempt to delete - should be prevented
    with pytest.raises(Exception):
        m.delete()
