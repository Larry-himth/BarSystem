from rest_framework import serializers


class SaleLineInputSerializer(serializers.Serializer):
    item_unit_id = serializers.IntegerField()
    qty = serializers.IntegerField(min_value=1)


class PaymentInputSerializer(serializers.Serializer):
    method = serializers.ChoiceField(choices=["CASH", "MOMO", "TAB"])
    amount = serializers.IntegerField(min_value=1)
    momo_ref = serializers.CharField(required=False, allow_blank=True)
    tab_id = serializers.IntegerField(required=False, allow_null=True)

    def validate(self, attrs):
        if attrs["method"] == "MOMO" and not attrs.get("momo_ref"):
            raise serializers.ValidationError({"momo_ref": "Required for mobile money payments"})
        if attrs["method"] == "TAB" and not attrs.get("tab_id"):
            raise serializers.ValidationError({"tab_id": "Required for tab payments"})
        return attrs


class SaleCreateSerializer(serializers.Serializer):
    shift_id = serializers.IntegerField()
    lines = SaleLineInputSerializer(many=True, allow_empty=False)
    payments = PaymentInputSerializer(many=True, allow_empty=False)


class SaleCreatedSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    total = serializers.IntegerField()


class VoidSaleSerializer(serializers.Serializer):
    pin = serializers.CharField(help_text="Manager/owner PIN", style={"input_type": "password"})
    reason = serializers.CharField()


class VoidResponseSerializer(serializers.Serializer):
    status = serializers.CharField()
