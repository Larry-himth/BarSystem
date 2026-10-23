from django.db.models import Sum


def current_stock(item):
    result = item.stock_movements.aggregate(total=Sum("qty_base"))
    total = result.get("total")
    if total is None:
        return 0
    return total
