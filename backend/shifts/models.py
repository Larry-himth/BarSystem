from django.conf import settings
from django.db import models


class Shift(models.Model):
    OPEN = "OPEN"
    SUBMITTED = "SUBMITTED"
    APPROVED = "APPROVED"
    DISPUTED = "DISPUTED"

    STATUS_CHOICES = [
        (OPEN, "Open"),
        (SUBMITTED, "Submitted"),
        (APPROVED, "Approved"),
        (DISPUTED, "Disputed"),
    ]

    opened_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="shifts_opened")
    opened_at = models.DateTimeField(auto_now_add=True)
    closed_at = models.DateTimeField(null=True, blank=True)
    submitted_at = models.DateTimeField(null=True, blank=True)
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="shifts_approved",
        null=True,
        blank=True,
    )
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default=OPEN)
    notes = models.TextField(blank=True)
    declared_cash = models.IntegerField(default=0)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["status"],
                condition=models.Q(status="OPEN"),
                name="only_one_open_shift",
            )
        ]

    def __str__(self):
        return f"Shift {self.id} - {self.status}"


class StockCount(models.Model):
    OPENING = "OPENING"
    CLOSING = "CLOSING"

    KIND_CHOICES = [
        (OPENING, "Opening"),
        (CLOSING, "Closing"),
    ]

    shift = models.ForeignKey(Shift, on_delete=models.PROTECT, related_name="stock_counts")
    item = models.ForeignKey("catalog.Item", on_delete=models.PROTECT, related_name="stock_counts")
    kind = models.CharField(max_length=16, choices=KIND_CHOICES)
    counted_qty = models.IntegerField()
    expected_qty = models.IntegerField()
    counted_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["shift", "item", "kind"],
                name="unique_stock_count_per_shift_item_kind",
            )
        ]
        ordering = ["created_at", "id"]

    def __str__(self):
        return f"{self.kind} {self.item_id} {self.counted_qty}"
