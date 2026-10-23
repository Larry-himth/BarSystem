import uuid

import pytest
from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied

from catalog.models import Item
from shifts.models import Shift
from stock.models import StockMovement


@pytest.mark.django_db
def test_bulk_update_raises():
    User = get_user_model()
    user = User.objects.create_user(username="b1", password="x")
    shift = Shift.objects.create(opened_by=user, status=Shift.OPEN)
    item = Item.objects.create(
        name_en="X",
        name_sw="X",
        category=Item.BEER,
        base_unit=Item.BOTTLE,
        buy_price=1000,
        par_level=1,
        is_active=True,
    )
    StockMovement.objects.create(
        uuid=uuid.uuid4(),
        item=item,
        shift=shift,
        qty_base=1,
        type=StockMovement.OPENING,
        reason="",
        created_by=user,
    )
    with pytest.raises(PermissionDenied):
        StockMovement.objects.filter(item=item).update(qty_base=5)


@pytest.mark.django_db
def test_bulk_delete_raises():
    User = get_user_model()
    user = User.objects.create_user(username="b2", password="x")
    shift = Shift.objects.create(opened_by=user, status=Shift.OPEN)
    item = Item.objects.create(
        name_en="Y",
        name_sw="Y",
        category=Item.BEER,
        base_unit=Item.BOTTLE,
        buy_price=1000,
        par_level=1,
        is_active=True,
    )
    StockMovement.objects.create(
        uuid=uuid.uuid4(),
        item=item,
        shift=shift,
        qty_base=2,
        type=StockMovement.OPENING,
        reason="",
        created_by=user,
    )
    with pytest.raises(PermissionDenied):
        StockMovement.objects.filter(item=item).delete()
