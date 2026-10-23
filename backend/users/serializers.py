from rest_framework import serializers

from .models import User


class LoginSerializer(serializers.Serializer):
    username = serializers.CharField(help_text="Worker username")
    pin = serializers.CharField(help_text="Worker PIN", style={"input_type": "password"})
