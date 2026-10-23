from django.conf import settings
from django.db import models


class Tab(models.Model):
    customer_name = models.CharField(max_length=255)
    phone = models.CharField(max_length=32, blank=True)
    balance = models.IntegerField(default=0)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.customer_name


class TabPayment(models.Model):
    tab = models.ForeignKey(Tab, on_delete=models.PROTECT, related_name="payments")
    amount = models.IntegerField()
    method = models.CharField(max_length=16)
    received_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    shift = models.ForeignKey("shifts.Shift", on_delete=models.PROTECT)

    created_at = models.DateTimeField(auto_now_add=True)
