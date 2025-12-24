# verify_logic.py
import os
import django
from decimal import Decimal

# Setup Django Environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'paygate.settings')
django.setup()

from accounts.models import CustomUser, SubDealerProfile
from finance.models import Transaction, BankAccount

def run_test():
    print("--- Starting Auto-Passive Logic Test ---")
    
    # 1. Create Test User & SubDealer
    username = "test_money_man"
    if CustomUser.objects.filter(username=username).exists():
        CustomUser.objects.filter(username=username).delete()
        print(f"Cleaned up existing user: {username}")

    user = CustomUser.objects.create_user(username=username, password="password")
    
    # Create Profile with Limit = 1000.00
    profile = SubDealerProfile.objects.create(
        user=user,
        commission_rate=Decimal('2.00'), # 2% Commission
        net_balance_limit=Decimal('1000.00'),
        is_active_by_system=True
    )
    print(f"Created SubDealer: {username} | Limit: {profile.net_balance_limit} | Rate: {profile.commission_rate}%")

    # 2. Add a Bank Account
    bank = BankAccount.objects.create(
        sub_dealer=profile,
        bank_name="TestBank",
        iban="TR99",
        account_holder="Test Holder",
        daily_limit=Decimal('50000')
    )
    print("Created BankAccount.")

    # 3. Process a Transaction BELOW Limit
    # Deposit 500. Commission = 500 * 0.02 = 10. Net = 490.
    # Balance = 490. Limit = 1000. Should stay Active.
    t1 = Transaction.objects.create(
        sub_dealer=profile,
        bank_account=bank,
        transaction_type=Transaction.TransactionType.DEPOSIT,
        status=Transaction.Status.APPROVED,
        amount=Decimal('500.00'),
        external_user_id="user1"
    )
    
    profile.refresh_from_db()
    print(f"\nTx 1 (500 Deposit). New Balance: {profile.current_net_balance}")
    print(f"Active Status: {profile.is_active_by_system}")
    
    if profile.is_active_by_system:
        print(">> PASS: Remains Active (490 < 1000)")
    else:
        print(">> FAIL: Unexpectedly Disabled")

    # 4. Process a Transaction EXCEEDING Limit
    # Need > 510 Net to cross 1000.
    # Let's deposit 600. Commission = 12. Net = 588.
    # Total Balance = 490 + 588 = 1078. Limit = 1000. Should DISABLE.
    t2 = Transaction.objects.create(
        sub_dealer=profile,
        bank_account=bank,
        transaction_type=Transaction.TransactionType.DEPOSIT,
        status=Transaction.Status.APPROVED,
        amount=Decimal('600.00'),
        external_user_id="user2"
    )

    profile.refresh_from_db()
    print(f"\nTx 2 (600 Deposit). New Balance: {profile.current_net_balance}")
    print(f"Active Status: {profile.is_active_by_system}")

    if not profile.is_active_by_system:
        print(">> PASS: System Successfully set to PASSIVE (1078 >= 1000)")
    else:
        print(">> FAIL: Did not disable!")

if __name__ == "__main__":
    run_test()
