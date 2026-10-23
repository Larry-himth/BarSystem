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
from catalog.models import ItemUnit
from sales.models import Payment, Sale, SaleLine
from shifts.models import Shift
from stock.models import StockMovement
from tabs.models import Tab
from users.utils import verify_pin

from .serializers import (
    SaleCreateSerializer,
    SaleCreatedSerializer,
    VoidResponseSerializer,
    VoidSaleSerializer,
)


class SaleCreateView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(request=SaleCreateSerializer, responses={201: SaleCreatedSerializer})
    @transaction.atomic
    def post(self, request):
        serializer = SaleCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        shift = get_object_or_404(Shift, pk=data["shift_id"])
        if shift.status != Shift.OPEN:
            return Response(
                {"code": "SHIFT_NOT_OPEN", "message": "Shift is not open"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        total = 0
        for line in data["lines"]:
            unit = get_object_or_404(ItemUnit, pk=line["item_unit_id"])
            total += unit.sell_price * line["qty"]

        sale = Sale.objects.create(
            uuid=uuid.uuid4(), shift=shift, total=total, created_by=request.user
        )

        for line in data["lines"]:
            unit = get_object_or_404(ItemUnit, pk=line["item_unit_id"])
            qty = line["qty"]
            SaleLine.objects.create(
                sale=sale,
                item_unit=unit,
                qty=qty,
                unit_price=unit.sell_price,
                line_total=unit.sell_price * qty,
            )
            StockMovement.objects.create(
                uuid=uuid.uuid4(),
                item=unit.item,
                shift=shift,
                qty_base=-(unit.qty_in_base_unit * qty),
                type=StockMovement.SALE,
                reason="",
                created_by=request.user,
            )

        for payment in data["payments"]:
            tab_id = payment.get("tab_id")
            tab = get_object_or_404(Tab, pk=tab_id) if tab_id else None
            Payment.objects.create(
                sale=sale,
                method=payment["method"],
                amount=payment["amount"],
                momo_ref=payment.get("momo_ref", ""),
                tab=tab,
            )

        AuditLog.objects.create(
            user=request.user,
            action="SALE_CREATE",
            entity="Sale",
            entity_id=str(sale.id),
            metadata={"total": total, "shift_id": shift.id},
        )

        return Response({"id": sale.id, "total": total}, status=status.HTTP_201_CREATED)


class SaleVoidView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(request=VoidSaleSerializer, responses={200: VoidResponseSerializer})
    @transaction.atomic
    def post(self, request, pk):
        serializer = VoidSaleSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        sale = get_object_or_404(Sale, pk=pk)

        user = request.user
        if user.role not in ("OWNER", "MANAGER"):
            return Response(
                {"code": "FORBIDDEN", "message": "Manager/Owner required"},
                status=status.HTTP_403_FORBIDDEN,
            )
        if not verify_pin(user, serializer.validated_data["pin"]):
            return Response(
                {"code": "INVALID_PIN", "message": "Manager PIN is incorrect"},
                status=status.HTTP_403_FORBIDDEN,
            )
        if sale.voided_at:
            return Response(
                {"code": "ALREADY_VOIDED", "message": "Sale is already voided"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        sale.voided_by = user
        sale.void_reason = serializer.validated_data["reason"]
        sale.voided_at = timezone.now()
        sale.save()

        for line in sale.lines.all():
            StockMovement.objects.create(
                uuid=uuid.uuid4(),
                item=line.item_unit.item,
                shift=sale.shift,
                qty_base=line.item_unit.qty_in_base_unit * line.qty,
                type=StockMovement.VOID_REVERSAL,
                reason=f"VOID {sale.id}",
                created_by=user,
            )

        AuditLog.objects.create(
            user=user,
            action="VOID",
            entity="Sale",
            entity_id=str(sale.id),
            metadata={"reason": sale.void_reason},
        )

        return Response({"status": "voided"}, status=status.HTTP_200_OK)
