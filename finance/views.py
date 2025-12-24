from rest_framework import viewsets, status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.decorators import action
from django.db.models import Q
import random
from .models import BankAccount, Transaction, SubDealerProfile
from .serializers import TransactionSerializer # We need to create this

class AccountSelectionView(APIView):
    """
    API to get a deposit account based on Amount and Bank Name.
    Logic:
    1. Filter Active SubDealers (System Active).
    2. Filter Active BankAccounts of those dealers matching Bank Name.
    3. Select one (Random/Round-Robin).
    """
    def post(self, request):
        amount = request.data.get('amount')
        bank_name = request.data.get('bank_name')

        if not amount or not bank_name:
            return Response({"error": "amount and bank_name are required"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            amount = float(amount)
        except ValueError:
            return Response({"error": "Invalid amount"}, status=status.HTTP_400_BAD_REQUEST)

        # 1. Filter Active SubDealers
        active_dealers = SubDealerProfile.objects.filter(is_active_by_system=True)
        
        # 2. Filter Bank Accounts
        # checking daily limit could be complex (sum of today's txs), simple check for now: just active.
        eligible_accounts = BankAccount.objects.filter(
            sub_dealer__in=active_dealers,
            bank_name__iexact=bank_name,
            is_active=True
        )

        if not eligible_accounts.exists():
            return Response({"error": "No available accounts found for this bank"}, status=status.HTTP_404_NOT_FOUND)

        # 3. Selection (Random for load balancing)
        selected_account = random.choice(list(eligible_accounts))

        return Response({
            "bank_name": selected_account.bank_name,
            "iban": selected_account.iban,
            "account_holder": selected_account.account_holder,
            "sub_dealer_id": selected_account.sub_dealer.id # simplified for internal ref
        })

class TransactionViewSet(viewsets.ModelViewSet):
    queryset = Transaction.objects.all()
    serializer_class = TransactionSerializer
    # Permission classes should be added for security (IsAuthenticated)

    def create(self, request, *args, **kwargs):
        # Custom logic if needed, else default is fine.
        # Required triggers signals on save.
        return super().create(request, *args, **kwargs)
