from rest_framework import serializers


class TabCreateSerializer(serializers.Serializer):
    customer_name = serializers.CharField()
    phone = serializers.CharField(required=False, allow_blank=True)


class TabCreatedSerializer(serializers.Serializer):
    id = serializers.IntegerField()


class TabPaymentSerializer(serializers.Serializer):
    amount = serializers.IntegerField(min_value=1)
    method = serializers.ChoiceField(choices=["CASH", "MOMO"])


class TabPaymentResponseSerializer(serializers.Serializer):
    status = serializers.CharField()
