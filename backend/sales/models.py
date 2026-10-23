import uuid

from django.conf import settings
from django.db import models


class Sale(models.Model):
    uuid = models.UUIDField(unique=True, default=uuid.uuid4)
    shift = models.ForeignKey("shifts.Shift", on_delete=models.PROTECT, related_name="sales")
    total = models.IntegerField()
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)
    voided_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="sales_voided",
    )
    void_reason = models.TextField(blank=True)
    voided_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"Sale {self.id} {self.total}"


class SaleLine(models.Model):
    sale = models.ForeignKey(Sale, on_delete=models.PROTECT, related_name="lines")
    item_unit = models.ForeignKey("catalog.ItemUnit", on_delete=models.PROTECT)
    qty = models.IntegerField()
    unit_price = models.IntegerField()
    line_total = models.IntegerField()

    created_at = models.DateTimeField(auto_now_add=True)


class Payment(models.Model):
    CASH = "CASH"
    MOMO = "MOMO"
    TAB = "TAB"

    METHOD_CHOICES = [(CASH, "Cash"), (MOMO, "Mobile Money"), (TAB, "Tab")]

    sale = models.ForeignKey(Sale, on_delete=models.PROTECT, related_name="payments")
    method = models.CharField(max_length=16, choices=METHOD_CHOICES)
    amount = models.IntegerField()
    momo_ref = models.CharField(max_length=255, blank=True)
    tab = models.ForeignKey("tabs.Tab", on_delete=models.PROTECT, null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
