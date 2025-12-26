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
    throttle_scope = 'withdraw'

    def post(self, request, format=None):
        from finance.models import Transaction, Blacklist
        from .utils import is_blacklisted, get_client_ip
        # from .models import Blacklist # DEPRECATED

        # Blacklist Checks
        client_ip = get_client_ip(request)
        if is_blacklisted(client_ip, Blacklist.BlacklistType.IP):
             return Response({"error": "Erişim engellendi (IP)."}, status=status.HTTP_403_FORBIDDEN)
        
        # Note: We can check External User ID only after validating data or peeking data
        external_id = request.data.get('external_id')
        if external_id and is_blacklisted(external_id, Blacklist.BlacklistType.USER_ID):
             return Response({"error": "Hesabınız kısıtlanmıştır."}, status=status.HTTP_403_FORBIDDEN)
        
        target_iban = request.data.get('customer_iban')
        if target_iban and is_blacklisted(target_iban, Blacklist.BlacklistType.IBAN):
             return Response({"error": "Bu IBAN engellenmiştir."}, status=status.HTTP_403_FORBIDDEN)

        serializer = WithdrawalRequestSerializer(data=request.data)
        if serializer.is_valid():
            external_id_val = serializer.validated_data['external_id']
            try:
                from django.db import transaction
                from django.db.models import Q

                # Atomic block to prevent race conditions
                with transaction.atomic():
                    # Check for existing PENDING transactions for this user
                    # Note: We cannot check IP on Transaction model as it doesn't exist there.
                    # We rely on external_user_id for concurrency check for now.
                    if Transaction.objects.select_for_update().filter(
                        external_user_id=external_id_val, 
                        status__in=[Transaction.Status.PENDING, Transaction.Status.WAITING_ASSIGNMENT]
                    ).exists():
                         return Response(
                             {"error": "Zaten bekleyen bir işleminiz var. Lütfen sonuçlanmasını bekleyin."}, 
                             status=status.HTTP_409_CONFLICT
                         )

                    txn = Transaction.objects.create(
                        sub_dealer=None,
                        transaction_type=Transaction.TransactionType.WITHDRAW,
                        status=Transaction.Status.WAITING_ASSIGNMENT,
                        amount=serializer.validated_data['amount'],
                        external_user_id=external_id_val,
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

from api.authentication import ApiKeyAuthentication
from rest_framework.authentication import BasicAuthentication

from rest_framework.permissions import AllowAny

class DepositRequestAPIView(APIView):
    authentication_classes = [ApiKeyAuthentication]
    permission_classes = [AllowAny]
    throttle_scope = 'deposit'

    def post(self, request, format=None):
        from .api_serializers import DepositRequestSerializer
        from finance.models import BankAccount, Transaction, Blacklist
        from .utils import is_blacklisted, get_client_ip
        # from .models import Blacklist # DEPRECATED
        import random

        # Blacklist Checks
        client_ip = get_client_ip(request)
        if is_blacklisted(client_ip, Blacklist.BlacklistType.IP):
             return Response({"error": "Erişim engellendi (IP)."}, status=status.HTTP_403_FORBIDDEN)
        
        user_id = request.data.get('user_id')
        if user_id and is_blacklisted(user_id, Blacklist.BlacklistType.USER_ID):
             return Response({"error": "Hesabınız kısıtlanmıştır."}, status=status.HTTP_403_FORBIDDEN)

        serializer = DepositRequestSerializer(data=request.data)
        if serializer.is_valid():
            amount = serializer.validated_data['amount']
            full_name = serializer.validated_data['full_name']
            user_id_val = serializer.validated_data['user_id']

            from django.db import transaction
            
            # Atomic block start
            with transaction.atomic():
                # Check concurrency
                # Lock rows to be safe
                if Transaction.objects.select_for_update().filter(
                    external_user_id=user_id_val, 
                    status=Transaction.Status.PENDING,
                    transaction_type=Transaction.TransactionType.DEPOSIT
                ).exists():
                     return Response(
                         {"error": "Zaten bekleyen bir yatırım işleminiz var."}, 
                         status=status.HTTP_409_CONFLICT
                     )

                # 1. Find eligible accounts
                # Filter by account limits and dealer status
                candidates = BankAccount.objects.filter(
                    is_active=True,
                    min_deposit_limit__lte=amount,
                    max_deposit_limit__gte=amount,
                    sub_dealer__is_active_by_system=True,
                    sub_dealer__user__is_active=True  # Ensure User is globally active
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
                    external_user_id=user_id_val,
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
