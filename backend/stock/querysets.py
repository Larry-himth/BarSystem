from django.core.exceptions import PermissionDenied
from django.db import models


class StockMovementQuerySet(models.QuerySet):
    def update(self, *args, **kwargs):
        raise PermissionDenied("StockMovement is append-only and cannot be bulk updated")

    def delete(self):
        raise PermissionDenied("StockMovement is append-only and cannot be bulk deleted")
