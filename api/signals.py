from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from finance.models import Transaction
import requests
import logging

logger = logging.getLogger(__name__)

@receiver(pre_save, sender=Transaction)
def store_previous_status(sender, instance, **kwargs):
    if instance.pk:
        try:
            old_instance = Transaction.objects.get(pk=instance.pk)
            instance._old_status = old_instance.status
        except Transaction.DoesNotExist:
            instance._old_status = None
    else:
        instance._old_status = None

@receiver(post_save, sender=Transaction)
def send_transaction_callback(sender, instance, created, **kwargs):
    # Check if status changed
    old_status = getattr(instance, '_old_status', None)
    new_status = instance.status

    if old_status == new_status:
        return

    # User requested: Trigger when status changes (e.g. to APPROVED or REJECTED)
    # We primarily care about final states, but strict change detection is good.
    if new_status not in [Transaction.Status.APPROVED, Transaction.Status.REJECTED]:
        return

    if not instance.callback_url:
        return

    payload = {
        'transaction_id': instance.external_user_id or str(instance.id),
        'internal_id': instance.id,
        'status': new_status,
        'amount': float(instance.amount),
        'currency': 'TRY',
        'message': instance.rejection_reason if new_status == Transaction.Status.REJECTED else "Success"
    }

    try:
        # Timeout 5 seconds as requested
        response = requests.post(instance.callback_url, json=payload, timeout=5)
        logger.info(f"Callback sent for Tx #{instance.id} to {instance.callback_url}. Status: {response.status_code}")
    except Exception as e:
        logger.error(f"Callback failed for Tx #{instance.id}: {e}")
