from rest_framework import serializers
from .models import Transaction, BankAccount, SubDealerProfile

class TransactionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Transaction
        fields = '__all__'
        read_only_fields = ('created_at', 'processed_at')

    def validate(self, data):
        """
        Check for insufficient funds if creating a WITHDRAW transaction.
        """
        user = self.context['request'].user
        
        # Ensure we are dealing with a SubDealer
        if not hasattr(user, 'profile'):
             # If for some reason a non-subdealer tries this (admin?), skip or enforce policy?
             # For now, let's assume this API is for SubDealers.
             pass

        if data.get('transaction_type') == Transaction.TransactionType.WITHDRAW:
            amount = data.get('amount')
            if amount is not None and user.is_subdealer():
                profile = user.profile
                
                # Check Available Balance (Net - Pending Withdrawals)
                from django.db.models import Sum
                from decimal import Decimal
                
                pending_withdrawals = Transaction.objects.filter(
                    sub_dealer=profile, 
                    transaction_type=Transaction.TransactionType.WITHDRAW, 
                    status=Transaction.Status.PENDING
                ).aggregate(s=Sum('amount'))['s'] or Decimal('0.00')

                available = profile.current_net_balance - pending_withdrawals

                if available < amount:
                    raise serializers.ValidationError({"amount": f"Insufficient funds. Available: {available}"})
        
        return data
