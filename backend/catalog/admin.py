from django.contrib import admin

from .models import Item, ItemUnit


class ItemUnitInline(admin.TabularInline):
    model = ItemUnit
    extra = 0


@admin.register(Item)
class ItemAdmin(admin.ModelAdmin):
    list_display = ("name_en", "category", "base_unit", "buy_price", "par_level", "is_active")
    inlines = [ItemUnitInline]


@admin.register(ItemUnit)
class ItemUnitAdmin(admin.ModelAdmin):
    list_display = ("item", "label", "qty_in_base_unit", "sell_price", "can_sell", "can_buy")
