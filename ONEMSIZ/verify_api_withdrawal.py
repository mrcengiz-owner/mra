import os
import django
import json
from decimal import Decimal

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'paygate.settings')
django.setup()

from django.contrib.auth import get_user_model
from accounts.models import SubDealerProfile
from finance.models import Transaction
from rest_framework.test import APIRequestFactory, force_authenticate
from web.api_views import CreateWithdrawalAPIView

User = get_user_model()

def run_test():
    print("--- Starting Withdrawal API Verification ---")
    
    # 1. Setup User & Profile
    username = "api_test_user"
    user, _ = User.objects.get_or_create(username=username, email="api@test.com")
    if not hasattr(user, 'profile'):
        SubDealerProfile.objects.create(user=user)
    
    profile = user.profile
    
    # Reset State
    Transaction.objects.filter(sub_dealer=profile).delete()
    
    # Deposit Funds (Need funds to withdraw)
    Transaction.objects.create(
        sub_dealer=profile,
        transaction_type=Transaction.TransactionType.DEPOSIT,
        amount=Decimal("2000.00"),
        status=Transaction.Status.APPROVED
    )
    profile.refresh_from_db()
    
    # Get API Key
    api_key = str(profile.api_key)
    print(f"User Balance: {profile.current_net_balance}")
    print(f"API Key: {api_key}")

    # 2. Test API Request
    factory = APIRequestFactory()
    view = CreateWithdrawalAPIView.as_view()
    
    payload = {
        "amount": 1000.00,
        "customer_iban": "TR120006200000012345678901",
        "customer_name": "John Doe",
        "external_id": "EXT-999"
    }
    
    request = factory.post(
        '/api/create-withdrawal/',
        data=payload,
        format='json',
        headers={'X-API-KEY': api_key} # APIRequestFactory might need META handling depending on DRF version
    )
    # DRF RequestFactory handling of headers: HTTP_X_API_KEY
    request.META['HTTP_X_API_KEY'] = api_key 

    response = view(request)
    print(f"\nAPI Response Status: {response.status_code}")
    print(f"API Response Body: {response.data}")
    
    if response.status_code == 201:
        txn_id = response.data['transaction_id']
        tx = Transaction.objects.get(id=txn_id)
        print(f"\n[Verification] Transaction Created: ID {tx.id}")
        print(f" - Amount: {tx.amount}")
        print(f" - Target IBAN: {tx.target_iban}")
        print(f" - Target Name: {tx.target_name}")
        
        if tx.target_iban == payload['customer_iban'] and tx.target_name == payload['customer_name']:
            print("SUCCESS: Data saved correctly.")
        else:
            print("FAIL: Data mismatch.")
            
        print(f" - Status: {tx.status} (Expected: PENDING)")
        
    else:
        print("FAIL: API Request rejected.")

if __name__ == '__main__':
    run_test()
