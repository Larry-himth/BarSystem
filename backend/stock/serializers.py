from rest_framework import serializers


class StockMovementCreateSerializer(serializers.Serializer):
    item_id = serializers.IntegerField()
    shift_id = serializers.IntegerField()
    type = serializers.ChoiceField(choices=["DELIVERY", "SPILLAGE", "COMP"])
    qty_base = serializers.IntegerField()
    reason = serializers.CharField(required=False, allow_blank=True)

    def validate(self, attrs):
        if attrs["type"] in ("SPILLAGE", "COMP") and not attrs.get("reason"):
            raise serializers.ValidationError({"reason": "Required for spillage and comp"})
        if attrs["qty_base"] == 0:
            raise serializers.ValidationError({"qty_base": "Quantity cannot be zero"})
        return attrs


class StockMovementCreatedSerializer(serializers.Serializer):
    status = serializers.CharField()
