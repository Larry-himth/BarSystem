from django.contrib.auth import get_user_model
from django.contrib.auth.hashers import make_password
from django.core.management.base import BaseCommand

from catalog.models import Item, ItemUnit
from shifts.models import Shift
from stock.models import StockMovement


class Command(BaseCommand):
    help = "Seed demo data for Bar POS (Uganda)"

    def handle(self, *args, **options):
        User = get_user_model()
        owner, _ = User.objects.get_or_create(
            username="owner",
            defaults={
                "name": "Bar Owner",
                "role": User.OWNER,
                "language": User.EN,
                "is_active": True,
            },
        )
        owner.set_password("owner123")
        owner.pin_hash = make_password("1234")
        owner.save()

        manager, _ = User.objects.get_or_create(
            username="manager",
            defaults={"name": "Manager", "role": User.MANAGER, "language": User.EN, "is_active": True},
        )
        manager.set_password("manager123")
        manager.pin_hash = make_password("2222")
        manager.save()

        User = get_user_model()
        for uname, name, pin in [("b1", "Bartender 1", "1111"), ("b2", "Bartender 2", "3333")]:
            u, _ = User.objects.get_or_create(
                username=uname,
                defaults={"name": name, "role": User.BARTENDER, "language": User.EN, "is_active": True},
            )
            u.set_password(pin)
            u.pin_hash = make_password(pin)
            u.save()

        items_data = [
            ("Nile Special", "Nile Special", Item.BEER, Item.BOTTLE, 2000, 3000, 24),
            ("Club Pilsner", "Club Pilsner", Item.BEER, Item.BOTTLE, 2000, 3000, 24),
            ("Bell Lager", "Bell Lager", Item.BEER, Item.BOTTLE, 2000, 2800, 24),
            ("Tusker Lager", "Tusker Lager", Item.BEER, Item.BOTTLE, 2000, 3000, 24),
            ("Uganda Waragi", "Uganda Waragi", Item.SPIRIT, Item.BOTTLE, 15000, 25000, 6),
            ("Johnnie Walker Red Label", "Johnnie Walker Red Label", Item.SPIRIT, Item.BOTTLE, 40000, 65000, 3),
            ("Coca-Cola", "Coca-Cola", Item.SOFT_DRINK, Item.BOTTLE, 1000, 1500, 24),
            ("Fanta Orange", "Fanta Orange", Item.SOFT_DRINK, Item.BOTTLE, 1000, 1500, 24),
            ("Mineral Water", "Maji ya Chupa", Item.WATER, Item.BOTTLE, 500, 1000, 24),
            ("Soda", "Soda", Item.SOFT_DRINK, Item.BOTTLE, 1000, 1500, 24),
        ]

        created_items = []
        for name_en, name_sw, cat, base, buy, sell_bottle, par in items_data:
            item, created = Item.objects.get_or_create(
                name_en=name_en,
                defaults={
                    "name_sw": name_sw,
                    "category": cat,
                    "base_unit": base,
                    "buy_price": buy,
                    "par_level": par,
                    "is_active": True,
                },
            )
            if created and base == Item.BOTTLE:
                ItemUnit.objects.get_or_create(
                    item=item,
                    label="Bottle",
                    defaults={"qty_in_base_unit": 1, "sell_price": sell_bottle, "can_sell": True, "can_buy": True},
                )
                if cat == Item.SPIRIT:
                    ItemUnit.objects.get_or_create(
                        item=item,
                        label="Tot",
                        defaults={"qty_in_base_unit": 25, "sell_price": 1500, "can_sell": True, "can_buy": False},
                    )
            created_items.append(item)

        try:
            for s in Shift.objects.filter(status=Shift.OPEN):
                s.status = Shift.APPROVED
                s.save()
        except Exception:
            pass

        from django.utils import timezone
        shift = Shift.objects.filter(status=Shift.APPROVED).first()
        if not shift:
            try:
                shift = Shift.objects.create(opened_by=owner, status=Shift.APPROVED, closed_at=timezone.now())
            except Exception:
                Shift.objects.all().update(status=Shift.SUBMITTED)
                shift = Shift.objects.create(opened_by=owner, status=Shift.APPROVED, closed_at=timezone.now())
        if shift.opened_by_id is None:
            shift.opened_by = owner
        if shift.status != Shift.APPROVED:
            try:
                shift.status = Shift.APPROVED
            except Exception:
                Shift.objects.filter(pk=shift.pk).update(status=Shift.APPROVED)
                shift.refresh_from_db()
        if not getattr(shift, "closed_at", None):
            shift.closed_at = timezone.now()
        try:
            shift.save()
        except Exception:
            Shift.objects.filter(pk=shift.pk).update(status=Shift.APPROVED, closed_at=timezone.now())
            shift.refresh_from_db()

        for item in created_items:
            if not StockMovement.objects.filter(shift=shift, item=item, type=StockMovement.OPENING).exists():
                qty = item.par_level if item.par_level else 24
                StockMovement.objects.create(
                    item=item,
                    shift=shift,
                    qty_base=qty,
                    type=StockMovement.OPENING,
                    reason="seed",
                    created_by=owner,
                )

        self.stdout.write(self.style.SUCCESS("Seeded demo data (owner/manager/b1/b2 with PINs 1234/2222/1111/3333)"))
