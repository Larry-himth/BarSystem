from django.db import models


class Item(models.Model):
    BEER = "beer"
    SPIRIT = "spirit"
    SOFT_DRINK = "soft drink"
    WATER = "water"
    SNACK = "snack"
    OTHER = "other"

    CATEGORY_CHOICES = [
        (BEER, "Beer"),
        (SPIRIT, "Spirit"),
        (SOFT_DRINK, "Soft drink"),
        (WATER, "Water"),
        (SNACK, "Snack"),
        (OTHER, "Other"),
    ]

    PIECE = "piece"
    BOTTLE = "bottle"
    CAN = "can"
    ML = "ml"

    BASE_UNIT_CHOICES = [
        (PIECE, "Piece"),
        (BOTTLE, "Bottle"),
        (CAN, "Can"),
        (ML, "Milliliter"),
    ]

    name_en = models.CharField(max_length=255)
    name_sw = models.CharField(max_length=255)
    category = models.CharField(max_length=32, choices=CATEGORY_CHOICES)
    base_unit = models.CharField(max_length=16, choices=BASE_UNIT_CHOICES)
    buy_price = models.IntegerField()
    par_level = models.IntegerField(default=0)
    icon = models.CharField(max_length=255, blank=True)
    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name_en


class ItemUnit(models.Model):
    item = models.ForeignKey(Item, on_delete=models.PROTECT, related_name="units")
    label = models.CharField(max_length=64)
    qty_in_base_unit = models.IntegerField()
    sell_price = models.IntegerField()
    can_sell = models.BooleanField(default=True)
    can_buy = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.item.name_en} - {self.label}"
