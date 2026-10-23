from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken

from .models import User
from .serializers import LoginSerializer, MeSerializer
from .utils import verify_pin


class PinLoginView(APIView):
    # Login must never be blocked by a stale/invalid Authorization header.
    authentication_classes = []
    permission_classes = [AllowAny]

    @extend_schema(request=LoginSerializer, responses={200: dict})
    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        username = serializer.validated_data["username"]
        pin = serializer.validated_data["pin"]
        try:
            user = User.objects.get(username=username, is_active=True)
        except User.DoesNotExist:
            return Response(
                {"code": "AUTH_FAILED", "message": "Invalid credentials"},
                status=status.HTTP_401_UNAUTHORIZED,
            )
        if not verify_pin(user, pin):
            return Response(
                {"code": "AUTH_FAILED", "message": "Invalid credentials"},
                status=status.HTTP_401_UNAUTHORIZED,
            )
        refresh = RefreshToken.for_user(user)
        return Response({"access": str(refresh.access_token), "refresh": str(refresh)})


# Backward compatible name
LoginView = PinLoginView


class MeView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(responses=MeSerializer)
    def get(self, request):
        u = request.user
        return Response({"id": u.id, "username": u.username, "name": u.name, "role": u.role})
