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


def _user_label(user):
    if user is None:
        return ""
    return user.get_full_name() or user.username


def serialize_shift_summary(shift):
    opener = shift.opened_by
    approver = shift.approved_by if shift.approved_by_id else None
    return {
        "id": shift.id,
        "status": shift.status,
        "opened_by": shift.opened_by_id,
        "opened_by_username": opener.username if opener else "",
        "opened_by_name": _user_label(opener),
        "opened_by_user": {
            "id": opener.id,
            "username": opener.username,
            "name": _user_label(opener),
            "role": opener.role,
        }
        if opener
        else None,
        "opened_at": shift.opened_at,
        "closed_at": shift.closed_at,
        "submitted_at": shift.submitted_at,
        "approved_by": shift.approved_by_id,
        "approved_by_username": approver.username if approver else "",
        "notes": shift.notes,
    }


def build_shift_report(shift):
    items_by_id = {}
    user_totals = {}

    movements = (
        StockMovement.objects.filter(shift=shift)
        .select_related("item", "created_by")
        .order_by("created_at", "id")
    )
    for move in movements:
        row = items_by_id.setdefault(
            move.item_id,
            {
                "item": move.item,
                "opening": 0,
                "deliveries": 0,
                "sales": 0,
                "voids": 0,
                "spillage": 0,
                "comps": 0,
                "adjustments": 0,
                "counted": 0,
            },
        )
        if move.type == StockMovement.OPENING:
            row["opening"] += move.qty_base
        elif move.type == StockMovement.DELIVERY:
            row["deliveries"] += move.qty_base
        elif move.type == StockMovement.SALE:
            row["sales"] += -move.qty_base
        elif move.type == StockMovement.VOID_REVERSAL:
            row["voids"] += move.qty_base
        elif move.type == StockMovement.SPILLAGE:
            row["spillage"] += -move.qty_base
        elif move.type == StockMovement.COMP:
            row["comps"] += -move.qty_base
        elif move.type == StockMovement.ADJUSTMENT:
            row["adjustments"] += move.qty_base
        elif move.type == StockMovement.CLOSING_COUNT:
            row["counted"] = move.qty_base

        if move.type in (StockMovement.VOID_REVERSAL, StockMovement.SPILLAGE, StockMovement.COMP):
            actor = move.created_by
            user_row = user_totals.setdefault(
                actor.id,
                {
                    "user_id": actor.id,
                    "username": actor.username,
                    "name": _user_label(actor),
                    "voids": 0,
                    "spillage": 0,
                    "comps": 0,
                    "void_value": 0,
                    "spillage_value": 0,
                    "comp_value": 0,
                },
            )
            buy_price = move.item.buy_price or 0
            if move.type == StockMovement.VOID_REVERSAL:
                user_row["voids"] += move.qty_base
                user_row["void_value"] += move.qty_base * buy_price
            elif move.type == StockMovement.SPILLAGE:
                user_row["spillage"] += -move.qty_base
                user_row["spillage_value"] += -move.qty_base * buy_price
            elif move.type == StockMovement.COMP:
                user_row["comps"] += -move.qty_base
                user_row["comp_value"] += -move.qty_base * buy_price

    item_rows = []
    for item_id, row in items_by_id.items():
        item = row["item"]
        expected = (
            row["opening"]
            + row["deliveries"]
            + row["adjustments"]
            + row["voids"]
            - row["sales"]
            - row["spillage"]
            - row["comps"]
        )
        counted = row["counted"]
        variance = counted - expected
        buy_price = item.buy_price or 0
        variance_ugx = variance * buy_price
        item_rows.append(
            {
                "item_id": item_id,
                "name": item.name_en,
                "name_en": item.name_en,
                "name_sw": item.name_sw,
                "opening": row["opening"],
                "deliveries": row["deliveries"],
                "sales": row["sales"],
                "voids": row["voids"],
                "spillage": row["spillage"],
                "spillages": row["spillage"],
                "comps": row["comps"],
                "comp": row["comps"],
                "adjustments": row["adjustments"],
                "expected": expected,
                "counted": counted,
                "variance": variance,
                "variance_ugx": variance_ugx,
                "variance_value": variance_ugx,
                "expected_qty": expected,
                "counted_qty": counted,
                "variance_qty": variance,
                "buy_price": buy_price,
            }
        )

    expected_cash = 0
    expected_momo = 0
    momo_refs = []
    momo_references = []
    sales = Sale.objects.filter(shift=shift, voided_at__isnull=True).prefetch_related("payments")
    for sale in sales:
        for payment in sale.payments.all():
            if payment.method == Payment.CASH:
                expected_cash += payment.amount
            elif payment.method == Payment.MOMO:
                expected_momo += payment.amount
                if payment.momo_ref:
                    momo_refs.append(payment.momo_ref)
                    momo_references.append(
                        {
                            "sale_id": sale.id,
                            "amount": payment.amount,
                            "momo_ref": payment.momo_ref,
                            "ref": payment.momo_ref,
                        }
                    )

    declared_cash = int(getattr(shift, "declared_cash", 0) or 0)
    grouped_by_user = {row["username"]: row for row in user_totals.values()}
    return {
        "shift": serialize_shift_summary(shift),
        "id": shift.id,
        "status": shift.status,
        "opened_by": shift.opened_by_id,
        "opened_by_username": shift.opened_by.username if shift.opened_by else "",
        "opened_at": shift.opened_at,
        "closed_at": shift.closed_at,
        "submitted_at": shift.submitted_at,
        "expected_cash": expected_cash,
        "declared_cash": declared_cash,
        "cash_variance": declared_cash - expected_cash,
        "expected_momo": expected_momo,
        "momo_refs": momo_refs,
        "momo_references": momo_references,
        "momo_reference_list": momo_refs,
        "items": item_rows,
        "by_user": grouped_by_user,
        "grouped_by_user": grouped_by_user,
        "user_totals": list(user_totals.values()),
        "voids_by_user": {row["username"]: row["voids"] for row in user_totals.values()},
        "spillage_by_user": {row["username"]: row["spillage"] for row in user_totals.values()},
        "comps_by_user": {row["username"]: row["comps"] for row in user_totals.values()},
    }
