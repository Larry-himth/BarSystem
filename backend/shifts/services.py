from decimal import Decimal

from django.db.models import Sum

from sales.models import Payment, Sale
from stock.models import StockMovement


def get_expected_stock(item, shift):
    total = (
        StockMovement.objects.filter(item=item, shift=shift).aggregate(total=Sum("qty_base"))["total"]
        or 0
    )
    return total


def compute_shift_totals(shift):
    sales = Sale.objects.filter(shift=shift, voided_at__isnull=True)
    expected_cash = 0
    expected_momo = 0
    for sale in sales:
        for p in sale.payments.all():
            if p.method == "CASH":
                expected_cash += p.amount
            elif p.method == "MOMO":
                expected_momo += p.amount
    return {"expected_cash": expected_cash, "expected_momo": expected_momo}
