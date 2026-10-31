import uuid

from django.db import IntegrityError, transaction
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
from stock.services import current_stock
from tabs.models import Tab
from users.models import User
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

        client_uuid = data.get("client_uuid")

        if client_uuid:
            existing = Sale.objects.filter(client_uuid=client_uuid).first()
            if existing:
                return Response(
                    {"id": existing.id, "total": existing.total, "negative_stock_flag": existing.negative_stock_flag},
                    status=status.HTTP_201_CREATED,
                )

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

        payments_total = 0
        for payment in data.get("payments", []):
            payments_total += int(payment.get("amount", 0))
        if payments_total != total:
            return Response(
                {"code": "PAYMENT_MISMATCH", "message": "Payments must sum to total"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        negative_stock_flag = False
        for line in data["lines"]:
            unit = get_object_or_404(ItemUnit, pk=line["item_unit_id"])
            qty = line["qty"]
            current = current_stock(unit.item)
            projected = current - (unit.qty_in_base_unit * qty)
            if projected < 0:
                negative_stock_flag = True

        try:
            with transaction.atomic():
                sale = Sale.objects.create(
                    uuid=uuid.uuid4(),
                    client_uuid=client_uuid,
                    shift=shift,
                    total=total,
                    created_by=request.user,
                    negative_stock_flag=negative_stock_flag,
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

                if negative_stock_flag:
                    AuditLog.objects.create(
                        user=request.user,
                        action="NEGATIVE_STOCK_SALE",
                        entity="Sale",
                        entity_id=str(sale.id),
                        metadata={"shift_id": shift.id, "total": total},
                    )

                AuditLog.objects.create(
                    user=request.user,
                    action="SALE_CREATE",
                    entity="Sale",
                    entity_id=str(sale.id),
                    metadata={"total": total, "shift_id": shift.id},
                )
        except IntegrityError:
            if client_uuid:
                existing = Sale.objects.filter(client_uuid=client_uuid).first()
                if existing:
                    return Response(
                        {"id": existing.id, "total": existing.total, "negative_stock_flag": existing.negative_stock_flag},
                        status=status.HTTP_201_CREATED,
                    )
            raise

        return Response(
            {"id": sale.id, "total": total, "negative_stock_flag": negative_stock_flag},
            status=status.HTTP_201_CREATED,
        )


class SaleVoidView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(request=VoidSaleSerializer, responses={200: VoidResponseSerializer})
    @transaction.atomic
    def post(self, request, pk):
        serializer = VoidSaleSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        sale = get_object_or_404(Sale, pk=pk)

        caller = request.user
        approver = None
        override = False

        if data.get("approver_username") and data.get("approver_pin") is not None:
            try:
                approver = User.objects.get(username=data["approver_username"], is_active=True)
            except User.DoesNotExist:
                return Response({"code": "APPROVER_INVALID", "message": "Approver not found"}, status=status.HTTP_403_FORBIDDEN)
            if approver == caller:
                return Response({"code": "APPROVER_SAME_AS_CALLER", "message": "Approver must be different"}, status=status.HTTP_403_FORBIDDEN)
            if approver.role not in ("OWNER", "MANAGER"):
                return Response({"code": "APPROVER_NOT_AUTHORIZED", "message": "Approver must be manager/owner"}, status=status.HTTP_403_FORBIDDEN)
            try:
                if not verify_pin(approver, data["approver_pin"]):
                    return Response({"code": "INVALID_PIN", "message": "Approver PIN incorrect"}, status=status.HTTP_403_FORBIDDEN)
            except PermissionError:
                return Response({"code": "PIN_LOCKED", "message": "PIN is temporarily locked"}, status=status.HTTP_403_FORBIDDEN)
            override = True
        else:
            if caller.role not in ("OWNER", "MANAGER"):
                return Response({"code": "FORBIDDEN", "message": "Manager/Owner required"}, status=status.HTTP_403_FORBIDDEN)
            try:
                if not verify_pin(caller, data.get("pin") or ""):
                    return Response({"code": "INVALID_PIN", "message": "Manager PIN is incorrect"}, status=status.HTTP_403_FORBIDDEN)
            except PermissionError:
                return Response({"code": "PIN_LOCKED", "message": "PIN is temporarily locked"}, status=status.HTTP_403_FORBIDDEN)

        if sale.voided_at:
            return Response({"code": "ALREADY_VOIDED", "message": "Sale is already voided"}, status=status.HTTP_400_BAD_REQUEST)

        sale.voided_by = caller
        sale.void_reason = data.get("reason", "")
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
                created_by=caller,
            )

        AuditLog.objects.create(
            user=caller,
            action="VOID_OVERRIDE" if override else "VOID",
            entity="Sale",
            entity_id=str(sale.id),
            metadata={"reason": sale.void_reason, "approver_id": approver.id if approver else None},
        )

        return Response({"status": "voided", "override": override}, status=status.HTTP_200_OK)
