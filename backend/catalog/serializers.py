from rest_framework import serializers


class ItemUnitReadSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    label_en = serializers.CharField(source="label")
    label_sw = serializers.CharField(source="label")
    qty_in_base_unit = serializers.IntegerField()
    sell_price = serializers.IntegerField()
    can_sell = serializers.BooleanField()


class ItemReadSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    name_en = serializers.CharField()
    name_sw = serializers.CharField()
    category = serializers.CharField()
    icon = serializers.CharField()
    buy_price = serializers.IntegerField(required=False)
    par_level = serializers.IntegerField(required=False)
    units = ItemUnitReadSerializer(many=True)
