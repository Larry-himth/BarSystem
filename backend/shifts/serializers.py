from rest_framework import serializers


class OpenShiftSerializer(serializers.Serializer):
    notes = serializers.CharField(required=False, allow_blank=True)


class ShiftOpenedSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    status = serializers.CharField()
