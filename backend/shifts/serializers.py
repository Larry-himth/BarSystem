from rest_framework import serializers


class OpenShiftSerializer(serializers.Serializer):
    notes = serializers.CharField(required=False, allow_blank=True)


class ShiftOpenedSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    status = serializers.CharField()
    code = serializers.CharField(required=False)


class CountLineSerializer(serializers.Serializer):
    item_id = serializers.IntegerField()
    counted_qty = serializers.IntegerField(min_value=0)


class ShiftCountSerializer(serializers.Serializer):
    type = serializers.ChoiceField(choices=["OPENING", "CLOSING"])
    counts = CountLineSerializer(many=True, allow_empty=False)


class ShiftCloseSerializer(serializers.Serializer):
    counts = CountLineSerializer(many=True, allow_empty=True)
    pin = serializers.CharField(required=False, allow_blank=True)


class ShiftCountResponseSerializer(serializers.Serializer):
    status = serializers.CharField()
    variances = serializers.ListField(child=serializers.DictField(), required=False)


class ShiftCloseResponseSerializer(serializers.Serializer):
    status = serializers.CharField()
    code = serializers.CharField(required=False)
    items = serializers.ListField(child=serializers.DictField())


class ShiftSubmitResponseSerializer(serializers.Serializer):
    status = serializers.CharField()
    code = serializers.CharField(required=False)


class ShiftApproveResponseSerializer(serializers.Serializer):
    status = serializers.CharField()
    code = serializers.CharField(required=False)


class ShiftDisputeSerializer(serializers.Serializer):
    note = serializers.CharField()


class ShiftDisputeResponseSerializer(serializers.Serializer):
    status = serializers.CharField()
    code = serializers.CharField(required=False)


class MomoConfirmSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=["PENDING", "CONFIRMED", "DISPUTED"])
    note = serializers.CharField(required=False, allow_blank=True)


class MomoConfirmResponseSerializer(serializers.Serializer):
    status = serializers.CharField()
    code = serializers.CharField(required=False)
