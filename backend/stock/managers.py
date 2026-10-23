from django.db import models

from .querysets import StockMovementQuerySet


class StockMovementManager(models.Manager.from_queryset(StockMovementQuerySet)):
    pass
