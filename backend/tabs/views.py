from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from audit.models import AuditLog
from shifts.models import Shift

from .models import Tab, TabPayment
from .serializers import TabCreateSerializer, TabCreatedSerializer, TabPaymentResponseSerializer, TabPaymentSerializer


class TabCreateView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(request=TabCreateSerializer, responses={201: TabCreatedSerializer})
    def post(self, request):
        serializer = TabCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        tab = Tab.objects.create(
            customer_name=serializer.validated_data["customer_name"],
            phone=serializer.validated_data.get("phone", ""),
        )
        AuditLog.objects.create(
            user=request.user,
            action="TAB_CREATE",
            entity="Tab",
            entity_id=str(tab.id),
            metadata={},
        )
        return Response({"id": tab.id}, status=status.HTTP_201_CREATED)


class TabRepayView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(request=TabPaymentSerializer, responses={200: TabPaymentResponseSerializer})
    def post(self, request, pk):
        serializer = TabPaymentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        tab = get_object_or_404(Tab, pk=pk)
        shift = Shift.objects.filter(status=Shift.OPEN).first()
        if not shift:
            shift = Shift.objects.filter(opened_by=request.user).order_by("-id").first()
        if not shift:
            shift = Shift.objects.order_by("-id").first()
        if not shift:
            return Response({"code": "NO_SHIFT", "message": "No shift found"}, status=status.HTTP_400_BAD_REQUEST)
        TabPayment.objects.create(
            tab=tab,
            amount=serializer.validated_data["amount"],
            method=serializer.validated_data["method"],
            received_by=request.user,
            shift=shift,
        )
        tab.balance = max(0, (getattr(tab, "balance", 0) or 0) - serializer.validated_data["amount"])
        tab.save()
        AuditLog.objects.create(
            user=request.user,
            action="TAB_REPAY",
            entity="Tab",
            entity_id=str(tab.id),
            metadata={"amount": serializer.validated_data["amount"]},
        )
        return Response({"status": "recorded"}, status=status.HTTP_200_OK)
