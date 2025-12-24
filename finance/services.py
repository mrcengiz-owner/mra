from django.core.exceptions import ValidationError
from django.db import transaction, models
from .models import Transaction, SubDealerProfile
from decimal import Decimal

class TransactionService:
    @staticmethod
    def create_withdrawal(user, amount, bank_account=None, external_user_id="", target_iban=None, target_name=None):
        """
        Creates a WITHDRAW transaction with strict balance checks.
        """
        if not user.is_subdealer():
             raise ValidationError("Only SubDealers can perform withdrawals.")
        
        profile = user.profile
        amount = Decimal(str(amount))
        
        if amount <= 0:
            raise ValidationError("Amount must be positive.")

        # STRICT BALANCE CHECK
        # We must verify against (Net Balance - Pending Withdrawals) to exhaust funds immediately
        # and prevent multiple pending requests exceeding the limit.
        pending_withdrawals = Transaction.objects.filter(
            sub_dealer=profile, 
            transaction_type=Transaction.TransactionType.WITHDRAW, 
            status=Transaction.Status.PENDING
        ).aggregate(s=models.Sum('amount'))['s'] or Decimal('0.00')

        available_balance = profile.current_net_balance - pending_withdrawals

        if available_balance < amount:
            raise ValidationError(f"Insufficient funds (Yetersiz Bakiye). Available: {available_balance}")

        with transaction.atomic():
            # Create the transaction
            txn = Transaction.objects.create(
                sub_dealer=profile,
                transaction_type=Transaction.TransactionType.WITHDRAW,
                amount=amount,
                status=Transaction.Status.PENDING, # Withdrawals usually start as Pending
                bank_account=bank_account,
                external_user_id=external_user_id,
                target_iban=target_iban,
                target_name=target_name
            )
            
            # Note: We do NOT deduct balance here immediately if it's PENDING.
            # The balance is usually deducted when APPROVED or depending on specific business logic.
            # However, for "Sufficient Balance Check" to be meaningful, we usually "hold" the funds 
            # or check against (Balance - Pending Withdrawals). 
            # 
            # RE-READING USER REQUEST: "Before creating a transaction... check current_net_balance."
            # It doesn't explicitly say "deduct immediately", but usually for a withdrawal request 
            # you want to ensure they have the money. 
            # 
            # Logic in models.py `recalculate_balance` sums ALL 'WITHDRAW' transactions.
            # If we create it here, `recalculate_balance` will perform:
            # Net Balance = Deposits - Withdrawals - Manual
            #
            # If we just create it, `post_save` signal on Transaction triggers `profile.recalculate_balance()`.
            # So the balance WILL be updated immediately upon creation of this record.
            # So the check `current_net_balance < amount` is valid for the moment BEFORE creation.
            
            return txn
