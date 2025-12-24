
import os
import django
import random
from decimal import Decimal
from django.utils import timezone

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'paygate.settings')
django.setup()

from finance.models import Transaction, BankAccount
from accounts.models import SubDealerProfile, CustomUser

def create_fake_data():
    print("--- Starting Fake Data Generation (50 Total) ---")

    # 1. Get or Create SubDealerProfile
    profile = SubDealerProfile.objects.first()
    
    if not profile:
        print("No SubDealerProfile found. Searching for a User...")
        user = CustomUser.objects.filter(role=CustomUser.Roles.SUBDEALER).first()
        
        if not user:
            print("No SubDealer user found. Creating new user 'demo_dealer'...")
            user = CustomUser.objects.create_user(username='demo_dealer', password='password123', role=CustomUser.Roles.SUBDEALER)
        
        print(f"Creating profile for user: {user.username}")
        try:
            profile = user.profile
        except SubDealerProfile.DoesNotExist:
            profile = SubDealerProfile.objects.create(user=user, commission_rate=5.00, net_balance_limit=1000000)

    print(f"Using SubDealer: {profile.user.username}")

    # 2. Get Bank Account (for Deposits)
    bank_account = BankAccount.objects.first()
    if not bank_account:
        print("No BankAccount found. Creating one...")
        bank_account = BankAccount.objects.create(
            sub_dealer=profile,
            bank_name="Test Bank",
            iban="TR0000000000000000000000",
            account_holder="Test Holder",
            daily_limit=100000.00
        )
    print(f"Using BankAccount: {bank_account.bank_name}")

    # 3. Create 25 Deposits
    print("Creating 25 FAKE DEPOSITS...")
    for i in range(25):
        amount = Decimal(random.randint(100, 10000))
        # Mix of Pending and others
        status = random.choice([Transaction.Status.PENDING, Transaction.Status.PENDING, Transaction.Status.APPROVED, Transaction.Status.REJECTED])
        
        Transaction.objects.create(
            sub_dealer=profile,
            transaction_type=Transaction.TransactionType.DEPOSIT,
            amount=amount,
            status=status,
            bank_account=bank_account,
            external_user_id=f"ext_{random.randint(100000, 999999)}",
            description=f"Generated Deposit #{i+1}",
            created_at=timezone.now() - timezone.timedelta(minutes=random.randint(1, 5000))
        )
    print("25 Deposits created.")

    # 4. Create 25 Withdrawals
    print("Creating 25 FAKE WITHDRAWALS...")
    for i in range(25):
        amount = Decimal(random.randint(500, 15000))
        status = random.choice([Transaction.Status.PENDING, Transaction.Status.PENDING, Transaction.Status.APPROVED, Transaction.Status.REJECTED])
        
        Transaction.objects.create(
            sub_dealer=profile,
            transaction_type=Transaction.TransactionType.WITHDRAW,
            amount=amount,
            status=status,
            target_iban=f"TR{random.randint(1000, 9999)} 0000 {random.randint(1000, 9999)} {random.randint(1000, 9999)} {random.randint(10, 99)}",
            target_name=f"Customer Name {random.randint(1, 500)}",
            external_user_id=f"ext_wd_{random.randint(100000, 999999)}",
            description=f"Generated Withdrawal #{i+1}",
            created_at=timezone.now() - timezone.timedelta(minutes=random.randint(1, 5000))
        )
    print("25 Withdrawals created.")
    
    # Recalculate balance
    profile.recalculate_balance()
    print("Balance recalculated. Dealer current balance: ", profile.current_net_balance)
    print("--- Done ---")

if __name__ == "__main__":
    create_fake_data()
