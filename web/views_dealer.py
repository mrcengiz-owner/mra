from django.views.generic import ListView, UpdateView, CreateView, TemplateView, View
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.shortcuts import get_object_or_404, redirect
from django.contrib import messages
from django.urls import reverse_lazy
from django.db.models import Sum, F, DecimalField, Case, When, Q
from django.utils import timezone
from finance.models import Transaction, BankAccount
from accounts.models import SubDealerProfile
from accounts.utils import log_action
import logging

logger = logging.getLogger(__name__)

class DealerMixin(LoginRequiredMixin, UserPassesTestMixin):
    def test_func(self):
        return self.request.user.is_authenticated and self.request.user.is_subdealer()

    def get_profile(self):
        return self.request.user.profile

class FilteredTransactionListView(DealerMixin, ListView):
    def get_queryset_base(self, tx_type):
        profile = self.get_profile()
        qs = Transaction.objects.filter(sub_dealer=profile, transaction_type=tx_type)
        
        # Filter Parameters
        status_filter = self.request.GET.get('status')
        date_start = self.request.GET.get('date_start')
        date_end = self.request.GET.get('date_end')
        search_query = self.request.GET.get('search')

        # 1. Default Behavior: Only PENDING if no filters are provided
        # We check if any of the key filter params exist in GET
        is_filtered = any([status_filter, date_start, date_end, search_query])
        
        if not is_filtered:
            qs = qs.filter(status=Transaction.Status.PENDING)
        else:
            # Apply Status Filter
            if status_filter and status_filter != 'ALL':
                qs = qs.filter(status=status_filter)
            
            # Apply Date Range
            if date_start:
                qs = qs.filter(created_at__date__gte=date_start)
            if date_end:
                qs = qs.filter(created_at__date__lte=date_end)
            
            # Apply Search (ID or Amount)
            if search_query:
                # Try search by ID or amount (Note: exact match for ID, contains for notes/external)
                search_q = Q(external_user_id__icontains=search_query) | Q(description__icontains=search_query)
                if search_query.isdigit():
                    search_q |= Q(id=search_query) | Q(amount=search_query)
                qs = qs.filter(search_q)

        return qs.order_by('-created_at')

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['is_filtered'] = any([self.request.GET.get(f) for f in ['status', 'date_start', 'date_end', 'search']])
        return ctx

class DealerDepositListView(FilteredTransactionListView):
    template_name = 'web/dealer_deposits.html'
    context_object_name = 'transactions'

    def get_queryset(self):
        return self.get_queryset_base(Transaction.TransactionType.DEPOSIT)

class DealerWithdrawalListView(FilteredTransactionListView):
    template_name = 'web/dealer_withdrawals.html'
    context_object_name = 'transactions'

    def get_queryset(self):
        return self.get_queryset_base(Transaction.TransactionType.WITHDRAW)

class DealerTransactionUpdateView(DealerMixin, UpdateView):
    model = Transaction
    fields = ['amount']
    template_name = 'web/dealer_transaction_form.html'
    success_url = reverse_lazy('dealer-deposits') # Default, can be dynamic based on type

    def get_queryset(self):
        # Security: Only allow editing own PENDING transactions
        return Transaction.objects.filter(
            sub_dealer=self.get_profile(),
            status=Transaction.Status.PENDING
        )

    def form_valid(self, form):
        # Log the change (Implementation Note: Ideally we'd have an audit log model)
        # For now, we update and message
        old_amount = self.get_object().amount
        new_amount = form.cleaned_data['amount']
        
        # Append to description or log
        tx = form.save(commit=False)
        tx.description = f"{tx.description or ''} | Amount updated from {old_amount} to {new_amount} by Dealer."
        tx.save()
        log_action(self.request, self.request.user, 'DEALER_UPDATE_AMOUNT', tx, details={
            'old_amount': float(old_amount),
            'new_amount': float(new_amount),
            'reason': 'Dealer correction'
        })
        
        messages.success(self.request, 'İşlem miktarı güncellendi.')
        
        if tx.transaction_type == Transaction.TransactionType.WITHDRAW:
            return redirect('dealer-withdrawals')
        return redirect('dealer-deposits')

class DealerBankAccountListView(DealerMixin, ListView):
    template_name = 'web/dealer_banks.html'
    context_object_name = 'bank_accounts'

    def get_queryset(self):
        return BankAccount.objects.filter(sub_dealer=self.get_profile())

class DealerBankAccountCreateView(DealerMixin, CreateView):
    model = BankAccount
    fields = ['bank_name', 'iban', 'account_holder', 'daily_limit', 'is_active']
    template_name = 'web/dealer_bank_form.html'
    success_url = reverse_lazy('dealer-banks')

    def form_valid(self, form):
        form.instance.sub_dealer = self.get_profile()
        messages.success(self.request, 'Banka hesabı eklendi.')
        return super().form_valid(form)

class DealerBankAccountUpdateView(DealerMixin, UpdateView):
    model = BankAccount
    fields = ['bank_name', 'iban', 'account_holder', 'daily_limit', 'is_active']
    template_name = 'web/dealer_bank_form.html'
    success_url = reverse_lazy('dealer-banks')

    def get_queryset(self):
        return BankAccount.objects.filter(sub_dealer=self.get_profile())

    def form_valid(self, form):
        messages.success(self.request, 'Banka hesabı güncellendi.')
        return super().form_valid(form)


class DealerReportView(DealerMixin, TemplateView):
    template_name = 'web/dealer_reports.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        profile = self.get_profile()
        
        # Base Querysets
        qs = Transaction.objects.filter(sub_dealer=profile)
        
        # Filter Parameters
        date_start = self.request.GET.get('date_start')
        date_end = self.request.GET.get('date_end')
        tx_type = self.request.GET.get('type')
        status = self.request.GET.get('status')

        # Apply Filters
        if date_start:
            qs = qs.filter(created_at__date__gte=date_start)
        if date_end:
            qs = qs.filter(created_at__date__lte=date_end)
        if tx_type and tx_type != 'ALL':
            qs = qs.filter(transaction_type=tx_type)
        if status and status != 'ALL':
            qs = qs.filter(status=status)
        else:
            # Default for reports is usually APPROVED for stats, but we list all below
            pass

        # Calculate Statistics (Only for APPROVED transactions within filter)
        stats_qs = qs.filter(status=Transaction.Status.APPROVED)
        
        totals = stats_qs.aggregate(
            gross_dep=Sum(Case(
                When(transaction_type__in=['DEPOSIT', 'MANUAL_CREDIT'], then=F('amount')),
                default=0, output_field=DecimalField()
            )),
            comm=Sum('commission_amount'),
            wd=Sum(Case(
                When(transaction_type__in=['WITHDRAW', 'MANUAL_DEBIT'], then=F('amount')),
                default=0, output_field=DecimalField()
            ))
        )

        total_in_gross = totals['gross_dep'] or 0
        total_comm = totals['comm'] or 0
        total_out = totals['wd'] or 0

        # Card metrics for the filtered period
        ctx['total_deposits_gross'] = total_in_gross
        ctx['total_withdrawals'] = total_out
        ctx['total_commission'] = total_comm
        
        # Consistent with user request: Gross In - Out - Commission
        ctx['period_net_balance'] = total_in_gross - total_out - total_comm
        
        # Keep global balance for info but main card should probably show period net
        ctx['global_net_balance'] = profile.current_net_balance

        
        # Transaction List (Filtered)
        ctx['transactions'] = qs.order_by('-created_at')[:100]
        ctx['is_filtered'] = any([date_start, date_end, tx_type, status])
        
        return ctx

from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.contrib.auth.decorators import login_required

class DealerTransactionActionView(DealerMixin, View):
    def post(self, request, pk, action):
        tx = get_object_or_404(Transaction, pk=pk, sub_dealer=self.get_profile())
        
        # Action Logic
        if action == 'approve':
            # Deposits: Dealer explicitly approves receiving money
            if tx.transaction_type == Transaction.TransactionType.DEPOSIT and tx.status == Transaction.Status.PENDING:
                tx.status = Transaction.Status.APPROVED
                tx.processed_at = timezone.now()
                tx.processed_by = request.user
                tx.save()
                log_action(request, request.user, 'DEALER_APPROVE_DEPOSIT', tx, details={'amount': float(tx.amount)})
                messages.success(request, f'Yatırım #{tx.id} onaylandı.')
            else:
                messages.error(request, 'Bu işlem onaylanamaz.')

        elif action == 'reject':
            # Both Deposits and Withdrawals can be rejected
            if tx.status == Transaction.Status.PENDING:
                tx.status = Transaction.Status.REJECTED
                tx.processed_at = timezone.now()
                tx.processed_by = request.user
                tx.rejection_reason = request.POST.get('reason', 'Bayi tarafından reddedildi.')
                tx.save()
                log_action(request, request.user, 'DEALER_REJECT_TRANSACTION', tx, details={
                    'amount': float(tx.amount),
                    'reason': tx.rejection_reason
                })
                
                if request.headers.get('x-requested-with') == 'XMLHttpRequest' or request.META.get('HTTP_ACCEPT') == 'application/json':
                    return JsonResponse({'status': 'success', 'message': f'İşlem #{tx.id} reddedildi.'})
                
                messages.warning(request, f'İşlem #{tx.id} reddedildi.')
            else:
                if request.headers.get('x-requested-with') == 'XMLHttpRequest' or request.META.get('HTTP_ACCEPT') == 'application/json':
                    return JsonResponse({'status': 'error', 'message': 'Bu işlem reddedilemez.'}, status=400)
                messages.error(request, 'Bu işlem reddedilemez.')

        elif action == 'paid':
            # Withdrawals: Dealer confirms they paid the user
            if tx.transaction_type == Transaction.TransactionType.WITHDRAW and tx.status == Transaction.Status.PENDING:
                tx.status = Transaction.Status.APPROVED # Using APPROVED as 'Completed/Paid'
                tx.processed_at = timezone.now()
                tx.processed_by = request.user
                tx.save()
                log_action(request, request.user, 'DEALER_MARK_PAID_WITHDRAW', tx, details={'amount': float(tx.amount)})
                messages.success(request, f'Çekim #{tx.id} ödendi olarak işaretlendi.')
            else:
                messages.error(request, 'Bu işlem tamamlanamaz.')
        
        # Redirect back
        if tx.transaction_type == Transaction.TransactionType.WITHDRAW:
            return redirect('dealer-withdrawals')
        return redirect('dealer-deposits')

@login_required
@require_POST
def toggle_bank_status(request):
    if not request.user.is_subdealer():
         return JsonResponse({'error': 'Unauthorized'}, status=403)
         
    bank_id = request.POST.get('bank_id')
    if not bank_id:
        return JsonResponse({'error': 'Missing bank_id'}, status=400)

    account = get_object_or_404(BankAccount, pk=bank_id, sub_dealer=request.user.profile)
    account.is_active = not account.is_active
    account.save()
    
    return JsonResponse({
        'status': 'success', 
        'new_state': account.is_active,
        'message': 'Durum güncellendi'
    })
