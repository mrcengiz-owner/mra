from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import Transaction
import logging

logger = logging.getLogger(__name__)

@receiver(post_save, sender=Transaction)
def update_net_balance(sender, instance, created, **kwargs):
    """
    Recalculate the Net Balance for the SubDealer whenever a transaction changes.
    Delegates logic to SubDealerProfile model.
    """
    sub_dealer = instance.sub_dealer
    if sub_dealer:
        sub_dealer.recalculate_balance()
