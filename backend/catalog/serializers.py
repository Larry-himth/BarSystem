from rest_framework import serializers


class ItemUnitReadSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    label_en = serializers.CharField(source="label")
    label_sw = serializers.SerializerMethodField()
    qty_in_base_unit = serializers.IntegerField()
    sell_price = serializers.IntegerField()
    can_sell = serializers.BooleanField()
    can_buy = serializers.BooleanField()

    def get_label_sw(self, unit) -> str:
        return unit.label_sw or unit.label


class BartenderItemReadSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    name_en = serializers.CharField()
    name_sw = serializers.CharField()
    category = serializers.CharField()
    icon = serializers.CharField()
    units = ItemUnitReadSerializer(many=True)


class ManagerItemReadSerializer(BartenderItemReadSerializer):
    buy_price = serializers.IntegerField()
    par_level = serializers.IntegerField()
