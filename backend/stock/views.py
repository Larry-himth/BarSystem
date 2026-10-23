import uuid

from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from catalog.models import Item
from shifts.models import Shift
from stock.models import StockMovement


class StockMovementCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        data = request.data
        item = Item.objects.get(id=data["item_id"])
        shift = Shift.objects.get(id=data["shift_id"])
        mtype = data["type"]
        if mtype not in ("DELIVERY", "SPILLAGE", "COMP"):
            return Response({"code": "INVALID_TYPE", "message": "Invalid type"}, status=status.HTTP_400_BAD_REQUEST)
        if mtype in ("SPILLAGE", "COMP") and not data.get("reason"):
            return Response({"code": "REASON_REQUIRED", "message": "Reason required"}, status=status.HTTP_400_BAD_REQUEST)
        qty_base = int(data["qty_base"])
        if mtype in ("SPILLAGE", "COMP") and qty_base >= 0:
            qty_base = -abs(qty_base)
        StockMovement.objects.create(
            uuid=uuid.uuid4(),
            item=item,
            shift=shift,
            qty_base=qty_base,
            type=mtype,
            reason=data.get("reason", ""),
            created_by=request.user,
        )
        return Response({"status": "created"}, status=status.HTTP_201_CREATED)
