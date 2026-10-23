import uuid

from django.conf import settings
from django.core.exceptions import PermissionDenied
from django.db import models

from .managers import StockMovementManager


class StockMovement(models.Model):
    OPENING = "OPENING"
    SALE = "SALE"
    DELIVERY = "DELIVERY"
    SPILLAGE = "SPILLAGE"
    COMP = "COMP"
    ADJUSTMENT = "ADJUSTMENT"
    CLOSING_COUNT = "CLOSING_COUNT"

    TYPE_CHOICES = [
        (OPENING, "Opening"),
        (SALE, "Sale"),
        (DELIVERY, "Delivery"),
        (SPILLAGE, "Spillage"),
        (COMP, "Comp"),
        (ADJUSTMENT, "Adjustment"),
        (CLOSING_COUNT, "Closing Count"),
    ]

    uuid = models.UUIDField(unique=True, default=uuid.uuid4, editable=False)
    item = models.ForeignKey("catalog.Item", on_delete=models.PROTECT, related_name="stock_movements")
    shift = models.ForeignKey("shifts.Shift", on_delete=models.PROTECT, related_name="stock_movements")
    qty_base = models.IntegerField()
    type = models.CharField(max_length=16, choices=TYPE_CHOICES)
    reason = models.TextField(blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)

    created_at = models.DateTimeField(auto_now_add=True)

    objects = StockMovementManager()

    class Meta:
        ordering = ["created_at", "id"]

    def save(self, *args, **kwargs):
        if self.pk is not None:
            raise PermissionDenied("StockMovement is append-only and cannot be edited")
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise PermissionDenied("StockMovement is append-only and cannot be deleted")

    def __str__(self):
        return f"{self.type} {self.item_id} {self.qty_base}"
