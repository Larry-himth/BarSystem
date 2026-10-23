import uuid

import pytest
from django.contrib.auth import get_user_model
from django.db.models.deletion import ProtectedError

from catalog.models import Item
from shifts.models import Shift
from stock.models import StockMovement


@pytest.mark.django_db
def test_deleting_item_with_movements_raises_protected_error():
    User = get_user_model()
    user = User.objects.create_user(username="p1", password="x")
    shift = Shift.objects.create(opened_by=user, status=Shift.OPEN)
    item = Item.objects.create(
        name_en="Test",
        name_sw="Test",
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
        qty_base=5,
        type=StockMovement.OPENING,
        reason="",
        created_by=user,
    )
    with pytest.raises(ProtectedError):
        item.delete()
