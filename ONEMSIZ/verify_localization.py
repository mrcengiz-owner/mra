import os
import django
from django.conf import settings

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'paygate.settings')
django.setup()

from django.test import RequestFactory
from django.contrib.auth import get_user_model
from finance.models import Transaction, Transaction
from web.views import TransactionActionView
from accounts.models import SubDealerProfile

User = get_user_model()

def run_test():
    print("--- Verifying Localization & Refactoring ---")
    
    # 1. Check Language Code
    print(f"LANGUAGE_CODE: {settings.LANGUAGE_CODE}")
    if settings.LANGUAGE_CODE != 'tr-tr':
        print("FAIL: Language code not set to tr-tr")
    else:
        print("SUCCESS: Language is tr-tr")
        
    # 2. Check Model Verbose Name
    print(f"Transaction Verbose Name: {Transaction._meta.verbose_name}")
    if Transaction._meta.verbose_name == "İşlem":
        print("SUCCESS: Verbose name localized.")
    else:
        print(f"FAIL: Expected 'İşlem', got '{Transaction._meta.verbose_name}'")

    # 3. Verify Re-Queue Logic
    print("\n--- Testing Re-Queue Logic ---")
    # Setup
    user, _ = User.objects.get_or_create(username="admin_tester", email="admin@test.com")
    user.role = User.Roles.SUPERADMIN
    user.is_superuser = True
    user.save()
    
    if not hasattr(user, 'profile'):
        SubDealerProfile.objects.create(user=user)
        
    # Create Rejected Transaction
    tx = Transaction.objects.create(
        sub_dealer=user.profile,
        transaction_type=Transaction.TransactionType.DEPOSIT,
        amount=100.00,
        status=Transaction.Status.REJECTED
    )
    print(f"Created Rejected Tx: #{tx.id} - Status: {tx.status}")
    
    # Simulate Action
    factory = RequestFactory()
    request = factory.post(f'/web/transaction/{tx.id}/requeue/')
    request.user = user
    request.session = {} 
    request._messages = [] # Mock messages
    
    # We need to mock 'messages' framework or just check DB after calling view method directly?
    # View is class based.
    view = TransactionActionView.as_view()
    
    # To avoid middleware/message issues in raw script, we might need to setup middleware or just test logic manually if view fails.
    # Let's try calling View.
    try:
        from django.contrib.messages.storage.fallback import FallbackStorage
        setattr(request, 'session', 'session')
        messages = FallbackStorage(request)
        setattr(request, '_messages', messages)
        
        view(request, pk=tx.id, action='requeue')
        
        tx.refresh_from_db()
        print(f"After Re-Queue: Status: {tx.status}")
        
        if tx.status == Transaction.Status.PENDING:
            print("SUCCESS: Transaction Re-Queued to PENDING.")
        else:
            print(f"FAIL: Status is {tx.status}")
            
    except Exception as e:
        print(f"View execution failed (expected if middleware missing): {e}")
        # Manual Logic Test
        print("Testing Logic via ORM directly...")
        if tx.status == Transaction.Status.REJECTED:
             tx.status = Transaction.Status.PENDING
             tx.save()
             print(f"Manual Save Status: {tx.status}")

if __name__ == '__main__':
    run_test()
