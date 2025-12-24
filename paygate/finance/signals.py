from django.db.models.signals import post_save
from django.dispatch import receiver
from django.db.models import Sum, F, Case, When, DecimalField
from decimal import Decimal
from .models import Transaction
import logging

logger = logging.getLogger(__name__)

@receiver(post_save, sender=Transaction)
def update_net_balance(sender, instance, created, **kwargs):
    """
    Recalculate the Net Balance for the SubDealer whenever a transaction changes.
    Logic: Net Balance = (Total Approved Deposits) - (Total Approved Withdrawals) - (Total Commission)
    Asumming Commission is applied on DEPOSITS.
    """
    sub_dealer = instance.sub_dealer
    
    # Filter approved transactions
    approved_txs = Transaction.objects.filter(
        sub_dealer=sub_dealer, 
        status=Transaction.Status.APPROVED
    )

    # Calculate Totals
    totals = approved_txs.aggregate(
        total_deposits=Sum(
            Case(
                When(transaction_type=Transaction.TransactionType.DEPOSIT, then=F('amount')),
                default=0,
                output_field=DecimalField()
            )
        ),
        total_withdrawals=Sum(
            Case(
                When(transaction_type=Transaction.TransactionType.WITHDRAW, then=F('amount')),
                default=0,
                output_field=DecimalField()
            )
        )
    )

    total_deposits = totals['total_deposits'] or Decimal('0.00')
    total_withdrawals = totals['total_withdrawals'] or Decimal('0.00')

    # Calculate Commission (only on deposits)
    # Commission = Total Deposits * (Rate / 100)
    commission_rate = sub_dealer.commission_rate
    total_commission = total_deposits * (commission_rate / Decimal('100.00'))

    # Net Balance
    new_balance = total_deposits - total_withdrawals - total_commission

    # Update SubDealer Profile
    sub_dealer.current_net_balance = new_balance
    
    # Check Limit
    if new_balance >= sub_dealer.net_balance_limit:
        if sub_dealer.is_active_by_system:
            sub_dealer.is_active_by_system = False
            logger.warning(f"SubDealer {sub_dealer.user.username} REACHED LIMIT ({new_balance} >= {sub_dealer.net_balance_limit}). System Auto-Passive.")
    elif not sub_dealer.is_active_by_system and new_balance < sub_dealer.net_balance_limit:
        # İsteğe bağlı: Bakiye düştüğünde otomatik olarak yeniden etkinleştirilsin mi? 
        # Gereksinim, otomatik olarak yeniden etkinleştirmeyi açıkça belirtmiyor, sadece otomatik olarak pasif hale getirmeyi belirtiyor.
        # Ancak genellikle manuel olarak yeniden etkinleştirme veya en azından güvenlik istersiniz. 
        # Talep edilmedikçe, otomatik yeniden etkinleştirme mantığını yorum satırında bırakacağım veya basit bir günlük kaydedeceğim. 
        # "Set SubDealerProfile.is_active_by_system = False ... Hesaplara hizmet vermeyi durdur" 
        # Güvenlik için yalnızca otomatik devre dışı bırakma seçeneğini kullanacağım.
        pass

    sub_dealer.save()
