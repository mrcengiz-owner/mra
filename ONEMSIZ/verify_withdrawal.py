import os
import django
from decimal import Decimal

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'paygate.settings')
django.setup()

from django.contrib.auth import get_user_model
from accounts.models import SubDealerProfile
from finance.services import TransactionService
from finance.models import Transaction, BankAccount
from django.core.exceptions import ValidationError

User = get_user_model()

def run_test():
    print("--- Starting Withdrawal Verification ---")
    
    # 1. Setup Test User
    username = "test_subdealer_withdraw"
    email = "withdraw@test.com"
    password = "password123"
    
    user, created = User.objects.get_or_create(username=username, email=email)
    if created:
        user.set_password(password)
        user.role = User.Roles.SUBDEALER
        user.save()
        print(f"Created user: {username}")
    else:
        print(f"Using existing user: {username}")

    # Ensure profile exists (signal should have created it, but just in case)
    if not hasattr(user, 'profile'):
        SubDealerProfile.objects.create(user=user)
    
    profile = user.profile
    
    # Reset state: Delete all transactions for this user
    Transaction.objects.filter(sub_dealer=profile).delete()
    
    # Create Initial Deposit of 1000
    Transaction.objects.create(
        sub_dealer=profile,
        transaction_type=Transaction.TransactionType.DEPOSIT,
        amount=Decimal("1000.00"),
        status=Transaction.Status.APPROVED
    )
    
    # Refresh profile to get calculated balance
    profile.refresh_from_db()
    print(f"Initial Balance (after Deposit): {profile.current_net_balance}")

    # 2. Test Insufficient Funds
    print("\n[TEST 1] Attempting withdrawal of 5000.00 (Should Fail)")
    try:
        TransactionService.create_withdrawal(user, Decimal("5000.00"))
        print("FAIL: Withdrawal succeeded unexpectedly.")
    except ValidationError as e:
        print(f"SUCCESS: Caught expected error: {e}")

    # 3. Test Sufficient Funds
    print("\n[TEST 2] Attempting withdrawal of 500.00 (Should Succeed)")
    try:
        txn = TransactionService.create_withdrawal(user, Decimal("500.00"))
        print(f"SUCCESS: Withdrawal created. ID: {txn.id}, Amount: {txn.amount}")
        
        # Verify balance is NOT deducted yet (it is pending) OR logic says check balance.
        # Wait, if `recalculate_balance` runs, it sums all withdrawals including PENDING?
        # Let's check `recalculate_balance` in accounts/models.py
        profile.refresh_from_db()
        print(f"Post-Withdrawal Balance: {profile.current_net_balance}")
        
    except ValidationError as e:
        print(f"FAIL: Withdrawal failed unexpectedly: {e}")

    # cleanup
    # user.delete() 

if __name__ == '__main__':
    run_test()
