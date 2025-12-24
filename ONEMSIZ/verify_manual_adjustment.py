import os
import django
from decimal import Decimal

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'paygate.settings')
django.setup()

from django.contrib.auth import get_user_model
from accounts.models import SubDealerProfile
from finance.models import Transaction

User = get_user_model()

def run_test():
    print("--- Verifying Manual Balance Adjustments ---")
    
    # 1. Setup User
    username = "manual_adj_test"
    user, _ = User.objects.get_or_create(username=username, email="adj@test.com")
    if not hasattr(user, 'profile'):
        SubDealerProfile.objects.create(user=user)
    
    profile = user.profile
    # Reset
    Transaction.objects.filter(sub_dealer=profile).delete()
    
    # Initial Deposit: 1000
    Transaction.objects.create(
        sub_dealer=profile,
        transaction_type=Transaction.TransactionType.DEPOSIT,
        amount=Decimal("1000.00"),
        status=Transaction.Status.APPROVED
    )
    profile.refresh_from_db()
    print(f"Start Balance: {profile.current_net_balance}") # 1000

    # 2. Add Credit (MANUAL_CREDIT) +500
    print("\n[Action] Adding 500 (Manual Credit)...")
    Transaction.objects.create(
        sub_dealer=profile,
        transaction_type=Transaction.TransactionType.MANUAL_CREDIT,
        amount=Decimal("500.00"),
        status=Transaction.Status.APPROVED,
        description="Bonus"
    )
    profile.refresh_from_db()
    
    # Expected: 1500
    print(f"New Balance: {profile.current_net_balance}")
    if profile.current_net_balance == Decimal("1500.00"):
        print("SUCCESS: Credit applied.")
    else:
        print(f"FAIL: Expected 1500.00, got {profile.current_net_balance}")

    # 3. Deduct Funds (MANUAL_DEBIT) -200
    print("\n[Action] Deducting 200 (Manual Debit)...")
    Transaction.objects.create(
        sub_dealer=profile,
        transaction_type=Transaction.TransactionType.MANUAL_DEBIT,
        amount=Decimal("200.00"),
        status=Transaction.Status.APPROVED,
        description="Penalty"
    )
    profile.refresh_from_db()
    
    # Expected: 1300
    print(f"New Balance: {profile.current_net_balance}")
    if profile.current_net_balance == Decimal("1300.00"):
        print("SUCCESS: Debit applied.")
    else:
        print(f"FAIL: Expected 1300.00, got {profile.current_net_balance}")

if __name__ == '__main__':
    run_test()
