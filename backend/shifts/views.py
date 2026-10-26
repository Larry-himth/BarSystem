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

from .models import Shift
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
    ShiftOpenedSerializer,
    ShiftSubmitResponseSerializer,
)
from .services import compute_shift_totals, get_expected_stock


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
        serializer = ShiftCountSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        shift = get_object_or_404(Shift, pk=pk)

        variances = []
        for line in data["counts"]:
            item = get_object_or_404(Item, pk=line["item_id"])
            counted_qty = int(line["counted_qty"])
            expected_qty = get_expected_stock(item, shift)
            if request.user.role == "BARTENDER" and data["type"] == "CLOSING":
                variances = []  # blind count - do not leak expected to bartender
            else:
                variances.append({"item_id": item.id, "expected_qty": expected_qty, "counted_qty": counted_qty, "variance_qty": counted_qty - expected_qty})
            StockMovement.objects.create(
                uuid=uuid.uuid4(),
                item=item,
                shift=shift,
                qty_base=counted_qty,
                type=StockMovement.CLOSING_COUNT if data["type"] == "CLOSING" else StockMovement.OPENING,
                reason="",
                created_by=request.user,
            )

        AuditLog.objects.create(
            user=request.user,
            action=f"SHIFT_{data['type']}_COUNT",
            entity="Shift",
            entity_id=str(shift.id),
            metadata={"counted_items": len(data["counts"])},
        )

        resp = {"status": "recorded"}
        if variances and not (request.user.role == "BARTENDER" and data["type"] == "CLOSING"):
            resp["variances"] = variances
        return Response(resp, status=status.HTTP_201_CREATED)


class ShiftSubmitView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(responses={200: ShiftSubmitResponseSerializer})
    @transaction.atomic
    def post(self, request, pk):
        shift = get_object_or_404(Shift, pk=pk)
        if shift.status != Shift.OPEN:
            return Response({"code": "SHIFT_NOT_OPEN", "message": "Shift not open"}, status=status.HTTP_400_BAD_REQUEST)
        shift.status = Shift.SUBMITTED
        shift.submitted_at = timezone.now()
        shift.closed_at = timezone.now()
        shift.save()
        AuditLog.objects.create(
            user=request.user,
            action="SHIFT_SUBMIT",
            entity="Shift",
            entity_id=str(shift.id),
            metadata=compute_shift_totals(shift),
        )
        return Response({"status": "submitted", "code": "SHIFT_SUBMITTED"}, status=status.HTTP_200_OK)


class ShiftCloseView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(request=ShiftCloseSerializer, responses={200: ShiftCloseResponseSerializer})
    @transaction.atomic
    def post(self, request, pk):
        serializer = ShiftCloseSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        shift = get_object_or_404(Shift, pk=pk)
        if shift.status != Shift.OPEN:
            return Response({"code": "SHIFT_NOT_OPEN", "message": "Shift not open"}, status=status.HTTP_400_BAD_REQUEST)

        counts_map = {int(c["item_id"]): int(c["counted_qty"]) for c in data["counts"]}
        active_items = []
        for move in StockMovement.objects.filter(shift=shift):
            if move.item_id not in active_items:
                active_items.append(move.item_id)
        if len(active_items) == 0:
            return Response({"code": "BAD_REQUEST", "message": "No active items"}, status=status.HTTP_400_BAD_REQUEST)
        for item_id in active_items:
            if item_id not in counts_map:
                return Response({"code": "MISSING_COUNT", "message": "Missing count"}, status=status.HTTP_400_BAD_REQUEST)

        items_resp = []
        for item_id in active_items:
            item = get_object_or_404(Item, pk=item_id)
            counted_qty = counts_map[item_id]
            expected_qty = get_expected_stock(item, shift)
            variance_qty = counted_qty - expected_qty
            variance_value = variance_qty * (item.buy_price or 0)
            StockMovement.objects.create(
                uuid=uuid.uuid4(),
                item=item,
                shift=shift,
                qty_base=counted_qty,
                type=StockMovement.CLOSING_COUNT,
                reason="",
                created_by=request.user,
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
        shift.save()
        AuditLog.objects.create(
            user=request.user,
            action="SHIFT_CLOSE",
            entity="Shift",
            entity_id=str(shift.id),
            metadata={"items": len(items_resp)},
        )
        return Response({"status": "submitted", "code": "SHIFT_CLOSED", "items": items_resp}, status=status.HTTP_200_OK)


class ShiftApproveView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(responses={200: ShiftApproveResponseSerializer})
    @transaction.atomic
    def post(self, request, pk):
        if request.user.role not in ("OWNER", "MANAGER"):
            return Response({"code": "FORBIDDEN", "message": "Manager/Owner required"}, status=status.HTTP_403_FORBIDDEN)
        shift = get_object_or_404(Shift, pk=pk)
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
