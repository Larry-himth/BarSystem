from rest_framework import serializers


class StockMovementCreateSerializer(serializers.Serializer):
    item_id = serializers.IntegerField()
    shift_id = serializers.IntegerField()
    type = serializers.ChoiceField(choices=["DELIVERY", "SPILLAGE", "COMP", "ADJUSTMENT"])
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


class StockItemReadSerializer(serializers.Serializer):
    item_id = serializers.IntegerField(source="id")
    name_en = serializers.CharField()
    name_sw = serializers.CharField()
    base_unit = serializers.CharField()
    stock_base = serializers.SerializerMethodField()
    par_level = serializers.IntegerField()
    is_low = serializers.SerializerMethodField()

    def get_stock_base(self, item) -> int:
        from .services import current_stock

        return current_stock(item)

    def get_is_low(self, item) -> bool:
        from .services import current_stock

        return current_stock(item) < item.par_level
