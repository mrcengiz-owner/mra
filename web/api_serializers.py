from rest_framework import serializers
from finance.models import Transaction

class WithdrawalRequestSerializer(serializers.Serializer):
    amount = serializers.DecimalField(max_digits=12, decimal_places=2)
    customer_iban = serializers.CharField(max_length=34, required=True)
    customer_name = serializers.CharField(max_length=255, required=True)
    external_id = serializers.CharField(max_length=100, required=True)
    callback_url = serializers.URLField(required=False, allow_blank=True)

    def validate_amount(self, value):
        if value <= 0:
            raise serializers.ValidationError("Amount must be positive.")
        return value

class DepositRequestSerializer(serializers.Serializer):
    full_name = serializers.CharField(max_length=255)
    amount = serializers.DecimalField(max_digits=12, decimal_places=2)
    user_id = serializers.CharField(max_length=100)
    callback_url = serializers.URLField(required=False, allow_blank=True)

    def validate_amount(self, value):
        if value <= 0:
            raise serializers.ValidationError("Miktar pozitif olmalıdır.")
        return value

class DepositConfirmSerializer(serializers.Serializer):
    transaction_token = serializers.UUIDField()
