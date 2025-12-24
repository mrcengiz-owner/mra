from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from accounts.models import SubDealerProfile
from finance.services import TransactionService
from .api_serializers import WithdrawalRequestSerializer
from django.core.exceptions import ValidationError
from .permissions import IsAuthenticatedClient
from accounts.utils import log_action
from finance.utils import send_notification
import logging

logger = logging.getLogger(__name__)

class WithdrawRequestAPIView(APIView):
    """
    Public API for external systems to request withdrawals.
    Transactions are placed in a 'Pool' for Admin assignment.
    """
    authentication_classes = []
    permission_classes = []

    def post(self, request, format=None):
        from finance.models import Transaction
        serializer = WithdrawalRequestSerializer(data=request.data)
        if serializer.is_valid():
            try:
                txn = Transaction.objects.create(
                    sub_dealer=None,
                    transaction_type=Transaction.TransactionType.WITHDRAW,
                    status=Transaction.Status.WAITING_ASSIGNMENT,
                    amount=serializer.validated_data['amount'],
                    external_user_id=serializer.validated_data['external_id'],
                    target_iban=serializer.validated_data['customer_iban'],
                    target_name=serializer.validated_data['customer_name']
                )
                
                # Push Notification (To Admin)
                send_notification('admin-channel', 'new-transaction', {
                    "message": f"Yeni Çekim Talebi (Havuz): {txn.amount} TL",
                    "amount": str(txn.amount),
                    "user": txn.target_name,
                    "type": "WITHDRAW"
                })
                
                return Response({
                    "status": "success",
                    "transaction_id": txn.id,
                    "message": "Talebiniz alındı, işleme hazırlanıyor"
                }, status=status.HTTP_201_CREATED)
            
            except Exception as e:
                logger.error(f"Pool Withdrawal Error: {e}")
                return Response({"error": "Sistemsel bir hata oluştu."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class CreateWithdrawalAPIView(APIView):
    # Deprecated or kept for specific dealer integrations if needed. 
    # For now, I'll keep it but the new 'Pool' one is primary.
    ...

class DepositRequestAPIView(APIView):
    authentication_classes = []
    permission_classes = [IsAuthenticatedClient]

    def post(self, request, format=None):
        from .api_serializers import DepositRequestSerializer
        from finance.models import BankAccount, Transaction
        import random

        serializer = DepositRequestSerializer(data=request.data)
        if serializer.is_valid():
            amount = serializer.validated_data['amount']
            full_name = serializer.validated_data['full_name']
            user_id = serializer.validated_data['user_id']

            # 1. Find eligible accounts
            # Filter by account limits and dealer status
            candidates = BankAccount.objects.filter(
                is_active=True,
                min_deposit_limit__lte=amount,
                max_deposit_limit__gte=amount,
                sub_dealer__is_active_by_system=True
            ).select_related('sub_dealer')
            
            # 2. Check Dealer Balance Limits (Post-DB filter for calculation)
            valid_accounts = []
            for acc in candidates:
                # Check if adding this amount exceeds the dealer's limit
                # Note: current_net_balance is updated only on APPROVED. 
                # But we should consider Pending deposits too to be safe? 
                # For now, simplest check on current balance.
                if acc.sub_dealer.current_net_balance + amount <= acc.sub_dealer.net_balance_limit:
                    valid_accounts.append(acc)
            
            if not valid_accounts:
                return Response(
                    {"error": "Uygun hesap bulunamadı (Limitler dolu veya limit dışı miktar)."}, 
                    status=status.HTTP_404_NOT_FOUND
                )

            # 3. Select one
            selected_account = random.choice(valid_accounts)

            # 4. Create Transaction (INITIATED)
            txn = Transaction.objects.create(
                sub_dealer=selected_account.sub_dealer,
                bank_account=selected_account,
                transaction_type=Transaction.TransactionType.DEPOSIT,
                status=Transaction.Status.PENDING,
                amount=amount,
                external_user_id=user_id,
                sender_full_name=full_name,
                description=f"Depositor: {full_name}"
            )

            # Push Notifications
            payload = {
                "message": f"Yeni Yatırım: {amount} TL - {full_name}",
                "amount": str(amount),
                "user": full_name,
                "type": "DEPOSIT"
            }
            # Notify Admin
            send_notification('admin-channel', 'new-transaction', payload)
            # Notify Dealer
            send_notification(f'dealer-{selected_account.sub_dealer.user.id}', 'new-transaction', payload)

            return Response({
                "status": "success",
                "transaction_token": txn.token,
                "banka_bilgileri": {
                    "banka_adi": selected_account.bank_name,
                    "alici_adi": selected_account.account_holder,
                    "iban": selected_account.iban
                }
            }, status=status.HTTP_201_CREATED)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class DepositConfirmAPIView(APIView):
    authentication_classes = []
    permission_classes = [IsAuthenticatedClient]

    def post(self, request, format=None):
        from .api_serializers import DepositConfirmSerializer
        from finance.models import Transaction

        serializer = DepositConfirmSerializer(data=request.data)
        if serializer.is_valid():
            token = serializer.validated_data['transaction_token']
            
            try:
                txn = Transaction.objects.get(token=token)
            except Transaction.DoesNotExist:
                 return Response({"error": "Geçersiz Token"}, status=status.HTTP_404_NOT_FOUND)
            
            if txn.status == Transaction.Status.PENDING:
                return Response({"status": "confirmed", "message": "İşlem zaten onaya gönderildi veya onaya hazır."}, status=status.HTTP_200_OK)
            elif txn.status == Transaction.Status.APPROVED:
                return Response({"status": "already_processed", "message": "İşlem zaten onaylanmış."}, status=status.HTTP_200_OK)
            else:
                 return Response({"error": "İşlem iptal edilmiş veya geçersiz."}, status=status.HTTP_400_BAD_REQUEST)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
