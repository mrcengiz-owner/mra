import os
import django
from decimal import Decimal
import json

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'paygate.settings')
django.setup()

from django.test import Client
from django.contrib.auth import get_user_model
from finance.models import Transaction, BankAccount
from accounts.models import APIClient, SubDealerProfile

User = get_user_model()

def run_test():
    print("--- Verifying Public Deposit API ---")
    
    # 1. Setup
    dealer_user, _ = User.objects.get_or_create(username="api_dealer", email="api@test.com")
    dealer_user.role = User.Roles.SUBDEALER
    dealer_user.save()
    profile, _ = SubDealerProfile.objects.get_or_create(user=dealer_user)
    profile.net_balance_limit = 2000.00
    profile.current_net_balance = 0.00
    profile.is_active_by_system = True
    profile.save()
    
    # Create API Client
    api_client, _ = APIClient.objects.get_or_create(name="Test Client")
    api_client.allowed_ips = "127.0.0.1"
    api_client.save()
    
    BankAccount.objects.filter(sub_dealer=profile).delete()
    bank = BankAccount.objects.create(
        sub_dealer=profile,
        bank_name="Test Bank",
        iban="TR_TEST_IBAN",
        account_holder="Test Holder",
        daily_limit=50000,
        min_deposit_limit=50,
        max_deposit_limit=1000,
        is_active=True
    )
    
    client = Client()
    headers = {'HTTP_X_API_KEY': api_client.api_key}

    # 2. Test Step A: Deposit Request (Success)
    print("\nTesting Step A: Request (Valid)...")
    payload = {
        "full_name": "John Doe",
        "amount": 500.00,
        "user_id": "USER_001"
    }
    resp = client.post('/web/api/public/deposit-request/', 
                       data=json.dumps(payload), 
                       content_type='application/json',
                       **headers)
    
    if resp.status_code != 201:
        print(f"FAIL: {resp.status_code} - {resp.content}")
    else:
        print("SUCCESS: Deposit Requested.")
        data = resp.json()
        print(f"Token: {data['transaction_token']}")
        print(f"Bank: {data['banka_bilgileri']['iban']}")
        
        token = data['transaction_token']
        
        # Verify DB
        txn = Transaction.objects.get(token=token)
        print(f"DB Status: {txn.status}")
        if txn.status == Transaction.Status.PENDING:
             print("Status OK (PENDING)")
        else:
             print("Status FAIL")

        # 3. Test Step B: Confirm
        print("\nTesting Step B: Confirm...")
        confirm_payload = {"transaction_token": token}
        resp_conf = client.post('/web/api/public/deposit-confirm/', 
                                data=json.dumps(confirm_payload), 
                                content_type='application/json',
                                **headers)
        
        if resp_conf.status_code == 200:
             print("SUCCESS: Confirmed.")
             txn.refresh_from_db()
             if txn.status == Transaction.Status.PENDING:
                 print("DB Status OK (STILL PENDING)")
             else:
                 print(f"DB Status FAIL: {txn.status}")
        else:
             print(f"FAIL: {resp_conf.status_code} - {resp_conf.content}")

    # 4. Test Step A: Limit Fail
    print("\nTesting Step A: Limit Fail (Too High)...")
    payload_high = {
        "full_name": "Rich Guy",
        "amount": 1500.00, # > 1000 limit
        "user_id": "USER_002"
    }
    resp_fail = client.post('/web/api/public/deposit-request/', 
                            data=json.dumps(payload_high), 
                            content_type='application/json',
                            **headers)
    if resp_fail.status_code == 404:
        print("SUCCESS: 404 Not Found (Correct).")
    else:
        print(f"FAIL: Expected 404, got {resp_fail.status_code}")

if __name__ == '__main__':
    run_test()
