import uuid

from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from audit.models import AuditLog
from catalog.models import Item
from shifts.models import Shift
from stock.models import StockMovement

from .serializers import StockMovementCreatedSerializer, StockMovementCreateSerializer


class StockMovementCreateView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        request=StockMovementCreateSerializer,
        responses={201: StockMovementCreatedSerializer},
    )
    def post(self, request):
        serializer = StockMovementCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        if request.user.role == "BARTENDER" and data["type"] == "ADJUSTMENT":
            return Response(
                {"code": "FORBIDDEN", "message": "Not allowed"},
                status=status.HTTP_403_FORBIDDEN,
            )

        item = get_object_or_404(Item, pk=data["item_id"])
        shift = get_object_or_404(Shift, pk=data["shift_id"])
        if shift.status != Shift.OPEN:
            return Response({"code": "SHIFT_NOT_OPEN", "message": "Shift not open"}, status=status.HTTP_400_BAD_REQUEST)

        qty_base = data["qty_base"]
        if data["type"] in ("SPILLAGE", "COMP"):
            qty_base = -abs(qty_base)

        movement = StockMovement.objects.create(
            uuid=uuid.uuid4(),
            item=item,
            shift=shift,
            qty_base=qty_base,
            type=data["type"],
            reason=data.get("reason", ""),
            created_by=request.user,
        )

        AuditLog.objects.create(
            user=request.user,
            action=f"STOCK_{data['type']}",
            entity="StockMovement",
            entity_id=str(movement.uuid),
            metadata={"item_id": item.id, "shift_id": shift.id, "qty_base": qty_base},
        )

        return Response({"status": "created"}, status=status.HTTP_201_CREATED)
