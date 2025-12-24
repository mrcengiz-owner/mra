import os
import django
from decimal import Decimal

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'paygate.settings')
django.setup()

from django.contrib.auth import get_user_model
from accounts.models import SubDealerProfile
from finance.services import TransactionService
from finance.models import Transaction
from django.core.exceptions import ValidationError

User = get_user_model()

def run_test():
    print("--- Starting Double Spend Verification ---")
    
    # Setup
    username = "test_subdealer_double_spend"
    user, _ = User.objects.get_or_create(username=username, email="ds@test.com")
    if not hasattr(user, 'profile'):
        SubDealerProfile.objects.create(user=user)
    
    profile = user.profile
    Transaction.objects.filter(sub_dealer=profile).delete() # Reset
    
    # 1. Deposit 1000
    Transaction.objects.create(
        sub_dealer=profile,
        transaction_type=Transaction.TransactionType.DEPOSIT,
        amount=Decimal("1000.00"),
        status=Transaction.Status.APPROVED
    )
    profile.refresh_from_db()
    print(f"Initial Balance: {profile.current_net_balance}") # 1000

    # 2. Withdraw 500 (Pending)
    print("\n[STEP 2] Withdraw 500...")
    TransactionService.create_withdrawal(user, Decimal("500.00"))
    print("Success.")

    # 3. Withdraw 400 (Pending) - Should Succeed (1000 - 500 = 500 > 400)
    print("\n[STEP 3] Withdraw 400...")
    try:
        TransactionService.create_withdrawal(user, Decimal("400.00"))
        print("Success.")
    except ValidationError as e:
        print(f"FAIL: Unexpected Error: {e}")

    # 4. Withdraw 200 (Pending) - Should FAIL (1000 - 900 = 100 < 200)
    print("\n[STEP 4] Withdraw 200... (Should Fail)")
    try:
        TransactionService.create_withdrawal(user, Decimal("200.00"))
        print("FAIL: Withdrawal succeeded unexpectedly! logic allows double spend!")
    except ValidationError as e:
        print(f"SUCCESS: Caught expected error: {e}")

if __name__ == '__main__':
    run_test()
