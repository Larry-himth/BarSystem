from django.core.exceptions import PermissionDenied
from django.db import IntegrityError
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Shift


class OpenShiftView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        if Shift.objects.filter(status=Shift.OPEN).exists():
            return Response({"code": "SHIFT_OPEN_EXISTS", "message": "An open shift already exists"}, status=status.HTTP_400_BAD_REQUEST)
        try:
            shift = Shift.objects.create(opened_by=request.user, status=Shift.OPEN)
        except Exception:
            return Response({"code": "SHIFT_OPEN_EXISTS", "message": "An open shift already exists"}, status=status.HTTP_400_BAD_REQUEST)
        return Response({"id": shift.id, "status": shift.status}, status=status.HTTP_201_CREATED)
