import os
import django
import random
import uuid
from decimal import Decimal

# Set up Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'paygate.settings')
django.setup()

from finance.models import Transaction

def create_pool_withdrawals(count=10):
    names = [
        "Ahmet Yılmaz", "Mehmet Demir", "Ayşe Kaya", "Fatma Çelik", 
        "Mustafa Öztürk", "Emine Şahin", "Ali Arslan", "Zeynep Doğan",
        "Hüseyin Kılıç", "Can Özkan", "Buse Aydın", "Murat Yıldız"
    ]
    
    banks = ["TR980006200000000012345678", "TR120001500158000012345678", "TR560004610000000012345678"]
    
    created_count = 0
    for i in range(count):
        amount = Decimal(random.randint(500, 15000))
        name = random.choice(names)
        iban = random.choice(banks)
        user_id = str(random.randint(100000, 999999))
        
        Transaction.objects.create(
            sub_dealer=None,
            transaction_type=Transaction.TransactionType.WITHDRAW,
            status=Transaction.Status.WAITING_ASSIGNMENT,
            amount=amount,
            external_user_id=user_id,
            target_iban=iban,
            target_name=name,
            token=uuid.uuid4()
        )
        created_count += 1
        print(f"Created pool withdrawal: {name} - {amount} ₺")
    
    print(f"\nSuccessfully created {created_count} pool withdrawals.")

if __name__ == "__main__":
    create_pool_withdrawals(10)
