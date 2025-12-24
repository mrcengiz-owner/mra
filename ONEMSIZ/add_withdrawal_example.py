import os
import django
import random
from decimal import Decimal

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'paygate.settings')
django.setup()

from django.contrib.auth import get_user_model
from accounts.models import SubDealerProfile
from finance.models import Transaction
from web.api_views import CreateWithdrawalAPIView
from rest_framework.test import APIRequestFactory

User = get_user_model()

def run():
    print("--- Creating Sample Withdrawal ---")
    
    # 1. Get User
    username = "api_test_user"
    user, _ = User.objects.get_or_create(username=username, email="api@test.com")
    if not hasattr(user, 'profile'):
        SubDealerProfile.objects.create(user=user)
    
    profile = user.profile
    
    # 2. Ensure Funds
    if profile.current_net_balance < 2000:
        print("Adding Funds...")
        Transaction.objects.create(
            sub_dealer=profile,
            transaction_type=Transaction.TransactionType.DEPOSIT,
            amount=Decimal("5000.00"),
            status=Transaction.Status.APPROVED
        )
        profile.refresh_from_db()
    
    print(f"Current Balance: {profile.current_net_balance}")
    
    # 3. Create Request via API
    factory = APIRequestFactory()
    view = CreateWithdrawalAPIView.as_view()
    
    # Randomize
    amount = random.choice([150.00, 250.50, 750.00, 1200.00])
    names = ["Ahmet Yilmaz", "Mehmet Demir", "Ayse Kaya", "Fatma Celik"]
    name = random.choice(names)
    iban = f"TR1200062000000{random.randint(1000000000, 9999999999)}"
    ext_id = f"ORD-{random.randint(1000, 9999)}"
    
    payload = {
        "amount": amount,
        "customer_iban": iban,
        "customer_name": name,
        "external_id": ext_id
    }
    
    request = factory.post(
        '/api/create-withdrawal/',
        data=payload,
        format='json'
    )
    request.META['HTTP_X_API_KEY'] = str(profile.api_key)

    print(f"Sending Request: {name} - {amount} TL")
    response = view(request)
    
    if response.status_code == 201:
        print(f"SUCCESS! Transaction ID: {response.data['transaction_id']}")
        print("Check the 'Withdrawal Queue' in the Admin Panel.")
    else:
        print(f"FAIL: {response.data}")

if __name__ == '__main__':
    run()
