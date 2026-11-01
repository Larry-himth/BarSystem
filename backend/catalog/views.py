from drf_spectacular.utils import extend_schema
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Item
from .serializers import BartenderItemReadSerializer, ManagerItemReadSerializer


class ItemListView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(responses=ManagerItemReadSerializer(many=True))
    def get(self, request):
        items = (
            Item.objects.filter(is_active=True)
            .prefetch_related("units")
            .order_by("category", "name_en", "id")
        )
        serializer_class = (
            ManagerItemReadSerializer
            if request.user.role in ("MANAGER", "OWNER")
            else BartenderItemReadSerializer
        )
        return Response(serializer_class(items, many=True).data)
