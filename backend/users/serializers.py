from rest_framework import serializers


class LoginSerializer(serializers.Serializer):
    username = serializers.CharField(help_text="Worker username")
    pin = serializers.CharField(help_text="Worker PIN", style={"input_type": "password"})


class MeSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    username = serializers.CharField()
    name = serializers.CharField()
    role = serializers.CharField()
