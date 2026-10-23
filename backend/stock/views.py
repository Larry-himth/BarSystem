import uuid

from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

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

        item = get_object_or_404(Item, pk=data["item_id"])
        shift = get_object_or_404(Shift, pk=data["shift_id"])

        qty_base = data["qty_base"]
        if data["type"] in ("SPILLAGE", "COMP"):
            qty_base = -abs(qty_base)

        StockMovement.objects.create(
            uuid=uuid.uuid4(),
            item=item,
            shift=shift,
            qty_base=qty_base,
            type=data["type"],
            reason=data.get("reason", ""),
            created_by=request.user,
        )
        return Response({"status": "created"}, status=status.HTTP_201_CREATED)
