from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken

from audit.models import AuditLog
from .models import User
from .serializers import LoginSerializer, MeSerializer, MeUpdateSerializer
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
        AuditLog.objects.create(
            user=user,
            action="LOGIN",
            entity="User",
            entity_id=str(user.id),
            metadata={"method": "pin"},
        )
        refresh = RefreshToken.for_user(user)
        return Response({"access": str(refresh.access_token), "refresh": str(refresh)})


# Backward compatible name
LoginView = PinLoginView


class MeView(APIView):
    permission_classes = [IsAuthenticated]

    def _serialize(self, user):
        return {"id": user.id, "username": user.username, "role": user.role, "language": user.language}

    @extend_schema(responses=MeSerializer)
    def get(self, request):
        return Response(self._serialize(request.user))

    @extend_schema(request=MeUpdateSerializer, responses=MeSerializer)
    def patch(self, request):
        if set(request.data.keys()) != {"language"}:
            return Response(
                {"code": "INVALID_FIELDS", "message": "Only language may be updated"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        serializer = MeUpdateSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                {"code": "INVALID_LANGUAGE", "message": "Language must be en or sw"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        user = request.user
        user.language = serializer.validated_data["language"]
        user.save(update_fields=["language"])
        return Response(self._serialize(user))
