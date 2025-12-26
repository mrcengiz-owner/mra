from rest_framework import viewsets, status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.decorators import action
from django.db.models import Q, Count, Sum
import random
from .models import BankAccount, Transaction, SubDealerProfile, Blacklist
from .serializers import TransactionSerializer # We need to create this

from django.views.generic import ListView, View
from django.contrib.auth.mixins import UserPassesTestMixin
from django.shortcuts import redirect, get_object_or_404
from django.http import JsonResponse
from django.contrib import messages

from datetime import timedelta
from django.utils import timezone
from decimal import Decimal
from accounts.models import CustomUser

class BlacklistManagerView(UserPassesTestMixin, ListView):
    model = Blacklist
    template_name = 'finance/blacklist_manager.html'
    context_object_name = 'blacklist_items'
    ordering = ['-created_at']

    def test_func(self):
        return self.request.user.is_superuser or self.request.user.role == CustomUser.Roles.ADMIN

    def post(self, request, *args, **kwargs):
        action = request.POST.get('action')
        
        if action == 'add':
            type_val = request.POST.get('type')
            value_val = request.POST.get('value')
            reason_val = request.POST.get('reason')
            
            if type_val and value_val:
                Blacklist.objects.create(type=type_val, value=value_val, reason=reason_val)
                messages.success(request, 'Kayıt eklendi.')
            else:
                messages.error(request, 'Eksik bilgi.')
            return redirect(request.path)

        elif action == 'toggle':
            item_id = request.POST.get('item_id')
            item = get_object_or_404(Blacklist, id=item_id)
            item.is_active = not item.is_active
            item.save()
            return JsonResponse({'status': 'success', 'new_state': item.is_active})

        elif action == 'delete':
            item_id = request.POST.get('item_id')
            item = get_object_or_404(Blacklist, id=item_id)
            item.delete()
            return JsonResponse({'status': 'success'})
            
        return redirect(request.path)

from .api.authentication import CsrfExemptSessionAuthentication
from rest_framework.authentication import BasicAuthentication

class AccountSelectionView(APIView):
    authentication_classes = (CsrfExemptSessionAuthentication, BasicAuthentication)
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


class AllDealersListView(UserPassesTestMixin, ListView):
    model = SubDealerProfile
    template_name = 'web/admin_all_dealers.html'
    context_object_name = 'dealers'

    def test_func(self):
        return self.request.user.is_superuser or self.request.user.role == CustomUser.Roles.ADMIN

    def get_queryset(self):
        # Calculate active bank count using related_name 'bank_accounts'
        # distinct=True is CRITICAL here to avoid multiplication by transaction count (Cartesian Product)
        return SubDealerProfile.objects.select_related('user').annotate(
            active_bank_count=Count('bank_accounts', filter=Q(bank_accounts__is_active=True), distinct=True),
            total_deposit=Sum('transactions__amount', filter=Q(transactions__status='APPROVED', transactions__transaction_type='DEPOSIT'))
        ).order_by('user__username')

class UpdateDealerPermissionsView(UserPassesTestMixin, View):
    def test_func(self):
        return self.request.user.is_superuser or self.request.user.role == CustomUser.Roles.ADMIN

    def post(self, request):
        user_id = request.POST.get('user_id')
        field_name = request.POST.get('field_name')
        
        # We assume user_id is the CustomUser id, since profile is related 1-1
        # But we need to update SubDealerProfile or User depending on field.
        
        # Profile fields
        if field_name == 'can_edit_amounts':
            profile = get_object_or_404(SubDealerProfile, user_id=user_id)
            profile.can_edit_amounts = not profile.can_edit_amounts
            profile.save()
            new_state = profile.can_edit_amounts
            
        # User fields
        elif field_name == 'is_active':
            # This toggle refers to User login status
            from accounts.models import CustomUser
            user = get_object_or_404(CustomUser, pk=user_id)
            user.is_active = not user.is_active
            user.save()
            new_state = user.is_active
            
        else:
             return JsonResponse({'status': 'error', 'message': 'Unknown field'}, status=400)
             
        return JsonResponse({'status': 'success', 'new_state': new_state})


def get_dashboard_stats(request):
    if not request.user.is_authenticated:
        return JsonResponse({'status': 'error', 'message': 'Unauthorized'}, status=403)

    period = request.GET.get('period', 'all')
    now = timezone.now()
    
    # Base QuerySet
    qs = Transaction.objects.filter(status=Transaction.Status.APPROVED)
    
    # User Filter
    if request.user.is_subdealer() and not request.user.is_superuser:
        qs = qs.filter(sub_dealer=request.user.profile)
    # else: superuser sees all by default

    # Date Filter
    if period == 'daily':
        start_date = now.replace(hour=0, minute=0, second=0, microsecond=0)
        qs = qs.filter(created_at__gte=start_date)
    elif period == 'weekly':
        start_date = now - timedelta(days=7)
        qs = qs.filter(created_at__gte=start_date)
    elif period == 'monthly':
        start_date = now - timedelta(days=30)
        qs = qs.filter(created_at__gte=start_date)
    
    # Aggregation
    totals = qs.aggregate(
        total_deposit=Sum(Case(
            When(transaction_type__in=['DEPOSIT', 'MANUAL_CREDIT', 'MANUAL'], then=F('amount')),
            default=0, output_field=DecimalField()
        )),
        total_withdraw=Sum(Case(
            When(transaction_type__in=['WITHDRAW', 'MANUAL_DEBIT'], then=F('amount')),
            default=0, output_field=DecimalField()
        )),
        total_commission=Sum('commission_amount')
    )
    
    dep = totals['total_deposit'] or Decimal('0.00')
    wd = totals['total_withdraw'] or Decimal('0.00')
    comm = totals['total_commission'] or Decimal('0.00')
    net = dep - wd - comm
    
    return JsonResponse({
        'status': 'success',
        'total_deposit': dep,
        'total_withdraw': wd,
        'total_commission': comm,
        'net_balance': net
    }, encoder=DjangoJSONEncoder)

from django.core.serializers.json import DjangoJSONEncoder
from django.db.models import Case, When, F, DecimalField
