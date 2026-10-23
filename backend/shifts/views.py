from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Shift
from .serializers import OpenShiftSerializer, ShiftOpenedSerializer


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
        return Response({"id": shift.id, "status": shift.status}, status=status.HTTP_201_CREATED)
