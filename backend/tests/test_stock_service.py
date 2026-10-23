import uuid

import pytest
from django.contrib.auth import get_user_model

from catalog.models import Item
from shifts.models import Shift
from stock.models import StockMovement
from stock.services import current_stock


@pytest.mark.django_db
def test_current_stock_sums_movements():
    User = get_user_model()
    user = User.objects.create_user(username="s1", password="x")
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
    StockMovement.objects.create(
        uuid=uuid.uuid4(),
        item=item,
        shift=shift,
        qty_base=24,
        type=StockMovement.OPENING,
        reason="",
        created_by=user,
    )
    StockMovement.objects.create(
        uuid=uuid.uuid4(),
        item=item,
        shift=shift,
        qty_base=-2,
        type=StockMovement.SALE,
        reason="",
        created_by=user,
    )
    assert current_stock(item) == 22
