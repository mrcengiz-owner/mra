import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'paygate.settings')
django.setup()

from finance.models import Transaction

def check_tx(tx_id):
    try:
        tx = Transaction.objects.get(id=tx_id)
        print(f"ID: {tx.id}")
        print(f"Type: {tx.transaction_type}")
        print(f"Status: {tx.status}")
        print(f"Dealer: {tx.sub_dealer}")
    except Transaction.DoesNotExist:
        print("Not Found")

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        check_tx(sys.argv[1])
    else:
        print("Provide ID")
