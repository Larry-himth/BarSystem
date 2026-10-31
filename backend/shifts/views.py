import uuid

from django.db import transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from audit.models import AuditLog
from catalog.models import Item
from sales.models import Payment, Sale
from stock.models import StockMovement
from stock.services import current_stock

from .models import Shift, StockCount
from .serializers import (
    MomoConfirmResponseSerializer,
    MomoConfirmSerializer,
    OpenShiftSerializer,
    ShiftApproveResponseSerializer,
    ShiftCloseResponseSerializer,
    ShiftCloseSerializer,
    ShiftCountResponseSerializer,
    ShiftCountSerializer,
    ShiftDisputeResponseSerializer,
    ShiftDisputeSerializer,
    ShiftListItemSerializer,
    ShiftOpenedSerializer,
    ShiftReportResponseSerializer,
)
from .services import (
    build_shift_report,
    expected_stock_for_item,
    ledger_balance_at,
    serialize_shift_summary,
)


class ShiftListView(APIView):
    permission_classes = [IsAuthenticated]
    serializer_class = ShiftListItemSerializer

    @extend_schema(responses={200: ShiftListItemSerializer(many=True)})
    def get(self, request):
        if request.user.role not in ("OWNER", "MANAGER"):
            return Response(
                {"code": "FORBIDDEN", "message": "Manager/Owner required"},
                status=status.HTTP_403_FORBIDDEN,
            )
        shifts = Shift.objects.select_related("opened_by", "approved_by").order_by("-opened_at", "-id")
        status_filter = request.query_params.get("status")
        if status_filter:
            shifts = shifts.filter(status=status_filter.upper())
        date_filter = request.query_params.get("date")
        if date_filter:
            shifts = shifts.filter(opened_at__date=date_filter)
        start_date = request.query_params.get("start_date")
        if start_date:
            shifts = shifts.filter(opened_at__date__gte=start_date)
        end_date = request.query_params.get("end_date")
        if end_date:
            shifts = shifts.filter(opened_at__date__lte=end_date)
        return Response([serialize_shift_summary(shift) for shift in shifts])


class ShiftReportView(APIView):
    permission_classes = [IsAuthenticated]
    serializer_class = ShiftReportResponseSerializer

    @extend_schema(responses={200: ShiftReportResponseSerializer})
    def get(self, request, pk):
        if request.user.role not in ("OWNER", "MANAGER"):
            return Response(
                {"code": "FORBIDDEN", "message": "Manager/Owner required"},
                status=status.HTTP_403_FORBIDDEN,
            )
        shift = get_object_or_404(
            Shift.objects.select_related("opened_by", "approved_by"),
            pk=pk,
        )
        return Response(build_shift_report(shift))


class OpenShiftView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(request=OpenShiftSerializer, responses={201: ShiftOpenedSerializer})
    def post(self, request):
        serializer = OpenShiftSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        if Shift.objects.filter(status=Shift.OPEN).exists():
            return Response(
                {"code": "SHIFT_OPEN_EXISTS", "message": "An open shift already exists"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        shift = Shift.objects.create(
            opened_by=request.user,
            status=Shift.OPEN,
            notes=serializer.validated_data.get("notes", ""),
        )
        AuditLog.objects.create(
            user=request.user,
            action="SHIFT_OPEN",
            entity="Shift",
            entity_id=str(shift.id),
            metadata={},
        )
        return Response({"id": shift.id, "status": shift.status, "code": "SHIFT_OPENED"}, status=status.HTTP_201_CREATED)


class ShiftCountView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(request=ShiftCountSerializer, responses={200: ShiftCountResponseSerializer, 201: ShiftCountResponseSerializer})
    @transaction.atomic
    def post(self, request, pk):
        shift = get_object_or_404(Shift, pk=pk)
        if shift.status != Shift.OPEN:
            return Response({"code": "SHIFT_NOT_OPEN", "message": "Shift not open"}, status=status.HTTP_400_BAD_REQUEST)

        serializer = ShiftCountSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        is_bartender = request.user.role == "BARTENDER"
        variances = []
        for line in data["counts"]:
            item = get_object_or_404(Item, pk=line["item_id"])
            counted_qty = int(line["counted_qty"])
            expected_qty = current_stock(item)
            StockCount.objects.update_or_create(
                shift=shift,
                item=item,
                kind=data["type"],
                defaults={
                    "counted_qty": counted_qty,
                    "expected_qty": expected_qty,
                    "counted_by": request.user,
                },
            )
            if not is_bartender:
                variances.append(
                    {
                        "item_id": item.id,
                        "expected_qty": expected_qty,
                        "counted_qty": counted_qty,
                        "variance_qty": counted_qty - expected_qty,
                    }
                )

        AuditLog.objects.create(
            user=request.user,
            action=f"SHIFT_{data['type']}_COUNT",
            entity="Shift",
            entity_id=str(shift.id),
            metadata={"counted_items": len(data["counts"])},
        )

        resp = {"status": "recorded"}
        if variances:
            resp["variances"] = variances
        return Response(resp, status=status.HTTP_201_CREATED)


def _complete_shift(request, shift, data, audit_action, response_code):
    counts = data.get("counts") or []
    count_item_ids = [int(c["item_id"]) for c in counts]
    active_item_ids = list(
        Item.objects.filter(is_active=True).order_by("id").values_list("id", flat=True)
    )
    if len(count_item_ids) != len(set(count_item_ids)) or set(count_item_ids) != set(active_item_ids):
        return Response(
            {"code": "COUNT_INCOMPLETE", "message": "Count every active item exactly once"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    counts_map = {int(c["item_id"]): int(c["counted_qty"]) for c in counts}
    items_resp = []
    for item_id in active_item_ids:
        item = get_object_or_404(Item, pk=item_id)
        counted_qty = counts_map[item_id]
        expected_qty = expected_stock_for_item(item, shift)
        variance_qty = counted_qty - expected_qty
        variance_value = variance_qty * (item.buy_price or 0)
        StockCount.objects.update_or_create(
            shift=shift,
            item=item,
            kind=StockCount.CLOSING,
            defaults={
                "counted_qty": counted_qty,
                "expected_qty": current_stock(item),
                "counted_by": request.user,
            },
        )
        items_resp.append(
            {
                "item_id": item_id,
                "expected_qty": expected_qty,
                "counted_qty": counted_qty,
                "variance_qty": variance_qty,
                "variance_value": variance_value,
            }
        )

    shift.status = Shift.SUBMITTED
    shift.submitted_at = timezone.now()
    shift.closed_at = timezone.now()
    if "declared_cash" in data:
        shift.declared_cash = data["declared_cash"]
    shift.save()
    AuditLog.objects.create(
        user=request.user,
        action=audit_action,
        entity="Shift",
        entity_id=str(shift.id),
        metadata={"items": len(items_resp)},
    )
    return Response(
        {"status": "submitted", "code": response_code, "items": items_resp},
        status=status.HTTP_200_OK,
    )


class ShiftSubmitView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(request=ShiftCloseSerializer, responses={200: ShiftCloseResponseSerializer})
    @transaction.atomic
    def post(self, request, pk):
        serializer = ShiftCloseSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        shift = get_object_or_404(Shift, pk=pk)
        if shift.status != Shift.OPEN:
            return Response({"code": "SHIFT_NOT_OPEN", "message": "Shift not open"}, status=status.HTTP_400_BAD_REQUEST)
        return _complete_shift(request, shift, serializer.validated_data, "SHIFT_SUBMIT", "SHIFT_SUBMITTED")


class ShiftCloseView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(request=ShiftCloseSerializer, responses={200: ShiftCloseResponseSerializer})
    @transaction.atomic
    def post(self, request, pk):
        serializer = ShiftCloseSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        shift = get_object_or_404(Shift, pk=pk)
        if shift.status != Shift.OPEN:
            return Response({"code": "SHIFT_NOT_OPEN", "message": "Shift not open"}, status=status.HTTP_400_BAD_REQUEST)
        return _complete_shift(request, shift, serializer.validated_data, "SHIFT_CLOSE", "SHIFT_CLOSED")


class ShiftApproveView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(responses={200: ShiftApproveResponseSerializer})
    @transaction.atomic
    def post(self, request, pk):
        if request.user.role not in ("OWNER", "MANAGER"):
            return Response({"code": "FORBIDDEN", "message": "Manager/Owner required"}, status=status.HTTP_403_FORBIDDEN)
        shift = get_object_or_404(Shift, pk=pk)
        if shift.status == Shift.APPROVED:
            return Response(
                {"code": "SHIFT_ALREADY_APPROVED", "message": "Shift already approved"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        reconciliation_reason = f"count reconciliation shift {shift.id}"
        if StockMovement.objects.filter(
            shift=shift,
            type=StockMovement.ADJUSTMENT,
            reason=reconciliation_reason,
        ).exists():
            return Response(
                {"code": "SHIFT_ALREADY_APPROVED", "message": "Shift already approved"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        reconciled_at = shift.closed_at or shift.submitted_at or timezone.now()
        closing_counts = StockCount.objects.filter(
            shift=shift,
            kind=StockCount.CLOSING,
        ).select_related("item")
        for count in closing_counts:
            delta = count.counted_qty - ledger_balance_at(count.item, reconciled_at)
            if delta == 0:
                continue
            StockMovement.objects.create(
                uuid=uuid.uuid4(),
                item=count.item,
                shift=shift,
                qty_base=delta,
                type=StockMovement.ADJUSTMENT,
                reason=reconciliation_reason,
                created_by=request.user,
            )
        shift.status = Shift.APPROVED
        shift.approved_by = request.user
        shift.save()
        AuditLog.objects.create(
            user=request.user,
            action="SHIFT_APPROVE",
            entity="Shift",
            entity_id=str(shift.id),
            metadata={},
        )
        return Response({"status": "approved", "code": "SHIFT_APPROVED"}, status=status.HTTP_200_OK)


class ShiftDisputeView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(request=ShiftDisputeSerializer, responses={200: ShiftDisputeResponseSerializer})
    @transaction.atomic
    def post(self, request, pk):
        if request.user.role not in ("OWNER", "MANAGER"):
            return Response({"code": "FORBIDDEN", "message": "Manager/Owner required"}, status=status.HTTP_403_FORBIDDEN)
        serializer = ShiftDisputeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        shift = get_object_or_404(Shift, pk=pk)
        shift.status = Shift.DISPUTED
        shift.notes = serializer.validated_data.get("note", "")
        shift.save()
        AuditLog.objects.create(
            user=request.user,
            action="SHIFT_DISPUTE",
            entity="Shift",
            entity_id=str(shift.id),
            metadata={"note": shift.notes},
        )
        return Response({"status": "disputed", "code": "SHIFT_DISPUTED"}, status=status.HTTP_200_OK)


class ShiftMomoConfirmView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(request=MomoConfirmSerializer, responses={200: MomoConfirmResponseSerializer})
    @transaction.atomic
    def post(self, request, pk):
        if request.user.role not in ("OWNER", "MANAGER"):
            return Response({"code": "FORBIDDEN", "message": "Manager/Owner required"}, status=status.HTTP_403_FORBIDDEN)
        serializer = MomoConfirmSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        shift = get_object_or_404(Shift, pk=pk)
        AuditLog.objects.create(
            user=request.user,
            action="MOMO_CONFIRM",
            entity="Shift",
            entity_id=str(shift.id),
            metadata={"status": serializer.validated_data["status"], "note": serializer.validated_data.get("note", "")},
        )
        return Response({"status": "confirmed", "code": "MOMO_CONFIRMED"}, status=status.HTTP_200_OK)
