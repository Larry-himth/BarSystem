from drf_spectacular.utils import extend_schema
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Item
from .serializers import ItemReadSerializer


class ItemListView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(responses=ItemReadSerializer(many=True))
    def get(self, request):
        items = (
            Item.objects.filter(is_active=True)
            .prefetch_related("units")
            .order_by("category", "name_en", "id")
        )
        data = ItemReadSerializer(items, many=True).data
        if request.user.role not in ("MANAGER", "OWNER"):
            for row in data:
                row.pop("buy_price", None)
                row.pop("par_level", None)
        return Response(data)
