
import os
import django
import random

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'paygate.settings')
django.setup()

from finance.models import Transaction

def fill_sender_names():
    names = ["Ahmet Yılmaz", "Mehmet Demir", "Ayşe Kaya", "Fatma Çelik", "Mustafa Öztürk", "Emine Can", "Ali Yıldız", "Hüseyin Aydın"]
    
    txs = Transaction.objects.filter(transaction_type='DEPOSIT', sender_full_name__isnull=True)
    count = txs.count()
    print(f"Found {count} transactions to update...")
    
    for tx in txs:
        # If description contains 'Depositor: Name', try extracting
        if tx.description and "Depositor:" in tx.description:
            try:
                tx.sender_full_name = tx.description.replace("Depositor: ", "").strip()
            except:
                tx.sender_full_name = random.choice(names)
        else:
            tx.sender_full_name = random.choice(names)
        tx.save()
    
    print(f"Update completed. {count} records updated.")

if __name__ == "__main__":
    fill_sender_names()
