from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from finance.models import Transaction
import requests
import logging
import hmac
import hashlib
import json

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
    old_status = getattr(instance, '_old_status', None)
    new_status = instance.status

    if old_status == new_status:
        return

    if new_status not in [Transaction.Status.APPROVED, Transaction.Status.REJECTED]:
        return

    if not instance.callback_url:
        return

    payload = {
        'transaction_id': instance.id,
        'external_id': instance.external_user_id,
        'status': new_status,
        'amount': float(instance.amount),
        'type': instance.transaction_type,
        'processed_at': str(instance.processed_at) if instance.processed_at else None,
        'message': instance.rejection_reason if new_status == Transaction.Status.REJECTED else "Success"
    }

    headers = {'Content-Type': 'application/json'}
    # Sort keys for deterministic signature
    body = json.dumps(payload, sort_keys=True)

    # Security: Sign Request
    if instance.api_client and instance.api_client.webhook_secret:
        secret = instance.api_client.webhook_secret.encode('utf-8')
        signature = hmac.new(secret, body.encode('utf-8'), hashlib.sha256).hexdigest()
        headers['X-NexKasa-Signature'] = signature

    try:
        response = requests.post(instance.callback_url, data=body, headers=headers, timeout=5)
        logger.info(f"Callback sent for Tx #{instance.id} to {instance.callback_url}. Status: {response.status_code}")
    except Exception as e:
        logger.error(f"Callback failed for Tx #{instance.id}: {e}")
