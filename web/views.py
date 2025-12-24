from django.contrib.auth.views import LoginView
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.shortcuts import redirect
from django.views.generic import TemplateView, ListView
from django.db.models import Sum, F, DecimalField, Case, When, Q
from decimal import Decimal
from django.shortcuts import get_object_or_404
from django.urls import reverse_lazy
from django.views.generic import FormView, ListView, View
from django.contrib import messages
from django.utils import timezone
from .forms import SystemConfigForm, ManualAdjustmentForm
from finance.utils import send_transaction_webhook
from finance.models import SystemConfig
from .filters import TransactionFilter
from django_filters.views import FilterView
from django.core.serializers.json import DjangoJSONEncoder
import json
from accounts.utils import log_action
import csv
from django.http import HttpResponse, JsonResponse

from accounts.models import SubDealerProfile, CustomUser, AuditLog
from finance.models import Transaction, BankAccount

class CustomLoginView(LoginView):
    redirect_authenticated_user = True
    def get_success_url(self):
        user = self.request.user
        if user.is_superadmin():
            return '/web/admin-dashboard/'
        elif user.is_subdealer():
            return '/web/dealer-dashboard/'
        return '/admin/' # Fallback

class DashboardRedirectView(LoginRequiredMixin, TemplateView):
    def get(self, request, *args, **kwargs):
        if request.user.is_superadmin():
            return redirect('admin-dashboard')
        elif request.user.is_subdealer():
            return redirect('dealer-dashboard')
        return redirect('login')

class SuperAdminDashboardView(UserPassesTestMixin, TemplateView):
    template_name = 'web/admin_dashboard.html'

    def test_func(self):
        return self.request.user.is_authenticated and self.request.user.is_superadmin()

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        
        # Stats Aggregation (SuperAdmin Dashboard)
        approved_txs = Transaction.objects.filter(status=Transaction.Status.APPROVED)
        
        # A. Toplam Yatırım: (API Yatırımları + Manuel Ekleme "Net Tutarı")
        # Formula: Sum(amount) - Sum(commission_amount) for incoming transactions
        in_txs = approved_txs.filter(
            transaction_type__in=[
                Transaction.TransactionType.DEPOSIT, 
                Transaction.TransactionType.MANUAL_CREDIT, 
                Transaction.TransactionType.MANUAL
            ]
        ).aggregate(
            gross=Sum('amount'),
            comm=Sum('commission_amount')
        )
        total_in_gross = in_txs['gross'] or Decimal('0.00')
        total_in_comm = in_txs['comm'] or Decimal('0.00')
        total_in_net = total_in_gross - total_in_comm
        
        # B. Toplam Çekim: (API Çekimleri + Manuel Kesintiler)
        total_out = approved_txs.filter(
            transaction_type__in=[
                Transaction.TransactionType.WITHDRAW, 
                Transaction.TransactionType.MANUAL_DEBIT
            ]
        ).aggregate(s=Sum('amount'))['s'] or Decimal('0.00')
        
        # D. Toplam Komisyon: (API İşlem Komisyonları + Manuel İşlem Komisyonları)
        total_commission = approved_txs.aggregate(s=Sum('commission_amount'))['s'] or Decimal('0.00')
            
        # C. Net Kasa: (Toplam Yatırım Brüt - Toplam Çekim - Komisyon)
        net_balance = total_in_gross - total_out - total_in_comm
        
        ctx['total_volume_in'] = total_in_gross
        ctx['total_volume_out'] = total_out
        ctx['total_commission'] = total_in_comm
        ctx['net_balance'] = net_balance
        
        # Active Dealer Count
        ctx['active_dealer_count'] = SubDealerProfile.objects.filter(is_active_by_system=True).count()
        
        # Dealers List
        ctx['dealers'] = SubDealerProfile.objects.all().select_related('user')
        
        return ctx

class SubDealerDashboardView(UserPassesTestMixin, TemplateView):
    template_name = 'web/dealer_dashboard.html'
    
    def test_func(self):
        return self.request.user.is_authenticated and self.request.user.is_subdealer()

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        profile = self.request.user.profile
        
        ctx['profile'] = profile
        ctx['percent_used'] = (profile.current_net_balance / profile.net_balance_limit * 100) if profile.net_balance_limit > 0 else 0
        ctx['my_accounts'] = BankAccount.objects.filter(sub_dealer=profile)
        ctx['recent_transactions'] = Transaction.objects.filter(sub_dealer=profile).order_by('-created_at')[:20]
        
        # Stats for Cards
        approved_txs = Transaction.objects.filter(sub_dealer=profile, status=Transaction.Status.APPROVED)
        
        in_stats = approved_txs.filter(
            transaction_type__in=[Transaction.TransactionType.DEPOSIT, Transaction.TransactionType.MANUAL_CREDIT]
        ).aggregate(g=Sum('amount'), c=Sum('commission_amount'))
        
        gross_deposit = in_stats['g'] or Decimal('0.00')
        total_commission = in_stats['c'] or Decimal('0.00')
        total_withdraw = approved_txs.filter(
            transaction_type__in=[Transaction.TransactionType.WITHDRAW, Transaction.TransactionType.MANUAL_DEBIT]
        ).aggregate(s=Sum('amount'))['s'] or Decimal('0.00')

        ctx['total_deposit'] = gross_deposit
        ctx['total_withdraw'] = total_withdraw
        ctx['total_commission'] = total_commission
        
        # User formula: Gross In - Out - Commission
        ctx['period_net'] = gross_deposit - total_withdraw - total_commission

        return ctx

class ReportsPageView(UserPassesTestMixin, FilterView):
    template_name = 'web/reports.html'
    filterset_class = TransactionFilter
    context_object_name = 'transactions'
    
    def test_func(self):
        # Allow both SuperAdmin and SubDealer (with restricted data)
        return self.request.user.is_authenticated and (self.request.user.is_superadmin() or self.request.user.is_subdealer())

    def get_queryset(self):
        qs = Transaction.objects.all().order_by('-created_at')
        # Security: SubDealers only see own
        if self.request.user.is_subdealer():
            if hasattr(self.request.user, 'profile'):
                qs = qs.filter(sub_dealer=self.request.user.profile)
            else:
                # Fallback: If SubDealer has no profile, show nothing for security
                return Transaction.objects.none()
        return qs

    def get_filterset_kwargs(self, filterset_class):
        kwargs = super().get_filterset_kwargs(filterset_class)
        kwargs['user'] = self.request.user # Pass user to FilterSet for widget customization
        return kwargs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        qs = self.object_list # This is the filtered queryset from FilterView
        
        # Aggregation Logic
        approved_qs = qs.filter(status=Transaction.Status.APPROVED)
        
        # A. Toplam Yatırım: (API Yatırımları + Manuel Ekleme "Net Tutarı")
        in_stats = approved_qs.filter(
            transaction_type__in=[Transaction.TransactionType.DEPOSIT, Transaction.TransactionType.MANUAL_CREDIT, Transaction.TransactionType.MANUAL]
        ).aggregate(g=Sum('amount'), c=Sum('commission_amount'))
        
        total_in_net = (in_stats['g'] or Decimal('0.00')) - (in_stats['c'] or Decimal('0.00'))
        
        # B. Toplam Çekim: (API Çekimleri + Manuel Kesintiler)
        total_out = approved_qs.filter(
            transaction_type__in=[Transaction.TransactionType.WITHDRAW, Transaction.TransactionType.MANUAL_DEBIT]
        ).aggregate(s=Sum('amount'))['s'] or Decimal('0.00')
        
        # D. Toplam Komisyon
        total_commission = approved_qs.aggregate(s=Sum('commission_amount'))['s'] or Decimal('0.00')

        ctx['total_deposit'] = total_in_net
        ctx['total_withdraw'] = total_out
        ctx['total_commission'] = total_commission
        ctx['net_flow'] = total_in_net - total_out
        
        # Note: manual_sum placeholder for UI compatibility if needed
        ctx['total_manual'] = approved_qs.filter(transaction_type__in=['MANUAL_CREDIT', 'MANUAL_DEBIT']).aggregate(s=Sum('amount'))['s'] or Decimal('0.00')

        # Chart Logic: Daily Volumes (Last 30 days of filtered range)
        # We aggregate by Date
        from django.db.models.functions import TruncDate
        
        chart_data = approved_qs.annotate(date=TruncDate('created_at')).values('date').annotate(
            dep=Sum(Case(When(transaction_type='DEPOSIT', then=F('amount')), default=0, output_field=DecimalField())),
            wd=Sum(Case(When(transaction_type='WITHDRAW', then=F('amount')), default=0, output_field=DecimalField()))
        ).order_by('date')
        
        dates = [d['date'].strftime('%Y-%m-%d') for d in chart_data]
        deposits = [float(d['dep']) for d in chart_data]
        withdraws = [float(d['wd']) for d in chart_data]
        
        ctx['chart_labels'] = json.dumps(dates)
        ctx['chart_deposits'] = json.dumps(deposits)
        ctx['chart_withdraws'] = json.dumps(withdraws)
        
        # Preserve query params for Export Link
        ctx['current_params'] = self.request.GET.urlencode()
        
        return ctx

def export_reports_csv(request):
    # Re-apply filters
    f = TransactionFilter(request.GET, queryset=Transaction.objects.all())
    qs = f.qs
    
    # Security Check
    if request.user.is_subdealer():
        qs = qs.filter(sub_dealer=request.user.profile)
    elif not request.user.is_superadmin():
        return HttpResponse("Unauthorized", status=403)
        
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="paygate_report_{timezone.now().strftime("%Y%m%d")}.csv"'
    
    writer = csv.writer(response)
    writer.writerow(['ID', 'Date', 'Dealer', 'Type', 'Status', 'Amount', 'Currency'])
    
    for tx in qs:
        writer.writerow([
            tx.id,
            tx.created_at.strftime('%Y-%m-%d %H:%M'),
            tx.sub_dealer.user.username,
            tx.get_transaction_type_display(),
            tx.get_status_display(),
            tx.amount,
            'TRY'
        ])
        
    return response

class DepositsListView(UserPassesTestMixin, ListView):
    template_name = 'web/deposits.html'
    context_object_name = 'transactions'
    
    def test_func(self):
        return self.request.user.is_authenticated and self.request.user.is_superadmin()
    
    def get_queryset(self):
        qs = Transaction.objects.filter(transaction_type=Transaction.TransactionType.DEPOSIT)
        
        # Filtering
        dealer_id = self.request.GET.get('dealer')
        status = self.request.GET.get('status')
        search = self.request.GET.get('search')
        
        if dealer_id:
            qs = qs.filter(sub_dealer_id=dealer_id)
        if status and status != 'ALL':
            qs = qs.filter(status=status)
        elif not any([dealer_id, status, search]):
            # Default to PENDING if no specific filters
            qs = qs.filter(status=Transaction.Status.PENDING)
            
        if search:
            qs = qs.filter(
                Q(sender_full_name__icontains=search) | 
                Q(external_user_id__icontains=search) |
                Q(id__icontains=search.replace('#', ''))
            )
            
        return qs.select_related('sub_dealer', 'sub_dealer__user', 'bank_account', 'processed_by').order_by('-created_at')

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['sub_dealers'] = SubDealerProfile.objects.select_related('user').all()
        ctx['statuses'] = Transaction.Status.choices
        return ctx

class TransactionActionView(UserPassesTestMixin, View):
    def test_func(self):
        return self.request.user.is_authenticated and self.request.user.is_superadmin()

    def post(self, request, pk, action):
        tx = get_object_or_404(Transaction, pk=pk)
        
        # Action: Approve
        if action == 'approve':
            if tx.status != Transaction.Status.PENDING:
                messages.error(request, 'İşlem zaten sonuçlanmış.')
                return self._redirect_back(tx)
                
            tx.status = Transaction.Status.APPROVED
            tx.processed_at = timezone.now()
            tx.processed_by = request.user
            tx.save() # Signal handles balance update
            send_transaction_webhook(tx)
            log_action(request, request.user, 'APPROVE_DEPOSIT', tx, details={'amount': float(tx.amount)})
            messages.success(request, f'İşlem #{tx.id} onaylandı.')

        # Action: Reject
        elif action == 'reject':
            if tx.status != Transaction.Status.PENDING:
                messages.error(request, 'İşlem zaten sonuçlanmış.')
                return self._redirect_back(tx)

            tx.status = Transaction.Status.REJECTED
            tx.processed_at = timezone.now()
            tx.processed_by = request.user
            tx.rejection_reason = request.POST.get('reason', 'Neden belirtilmedi.')
            tx.save()
            send_transaction_webhook(tx)
            log_action(request, request.user, 'REJECT_DEPOSIT', tx, details={
                'amount': float(tx.amount),
                'reason': tx.rejection_reason
            })
            
            if request.headers.get('x-requested-with') == 'XMLHttpRequest' or request.META.get('HTTP_ACCEPT') == 'application/json':
                return JsonResponse({'status': 'success', 'message': f'İşlem #{tx.id} reddedildi.'})
            
            messages.warning(request, f'İşlem #{tx.id} reddedildi.')

        # Action: Re-Queue (Hata Telafisi)
        elif action == 'requeue':
            if tx.status != Transaction.Status.REJECTED:
                messages.error(request, 'Sadece reddedilen işlemler tekrar işleme alınabilir.')
                return self._redirect_back(tx)

            tx.status = Transaction.Status.PENDING
            tx.processed_at = None
            tx.processed_by = None
            tx.save()
            log_action(request, request.user, 'REQUEUE_TRANSACTION', tx)
            messages.info(request, f'İşlem #{tx.id} tekrar beklemeye alındı.')
            
        return self._redirect_back(tx)

    def _redirect_back(self, tx):
        referer = self.request.META.get('HTTP_REFERER')
        if referer:
            return redirect(referer)
        if tx.transaction_type == Transaction.TransactionType.WITHDRAW:
            return redirect('withdrawal-queue')
        return redirect('deposits-list')

class WithdrawalsListView(UserPassesTestMixin, ListView):
    template_name = 'web/withdrawals.html'
    context_object_name = 'transactions'
    
    def test_func(self):
        return self.request.user.is_authenticated and self.request.user.is_superadmin()
    
    def get_queryset(self):
        qs = Transaction.objects.filter(transaction_type=Transaction.TransactionType.WITHDRAW)
        
        # Filtering
        dealer_id = self.request.GET.get('dealer')
        status = self.request.GET.get('status')
        search = self.request.GET.get('search')
        
        if dealer_id:
            qs = qs.filter(sub_dealer_id=dealer_id)
        if status and status != 'ALL':
            qs = qs.filter(status=status)
        elif not any([dealer_id, status, search]):
            # Default to PENDING if no specific filters
            qs = qs.filter(status=Transaction.Status.PENDING)
            
        if search:
            qs = qs.filter(
                Q(target_name__icontains=search) | 
                Q(target_iban__icontains=search) | 
                Q(external_user_id__icontains=search) |
                Q(id__icontains=search.replace('#', ''))
            )
            
        return qs.select_related('sub_dealer', 'sub_dealer__user', 'processed_by').order_by('-created_at')

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['sub_dealers'] = SubDealerProfile.objects.select_related('user').all()
        ctx['statuses'] = Transaction.Status.choices
        return ctx

class ManualAdjustmentView(UserPassesTestMixin, FormView):
    template_name = 'web/manual_adjustment.html'
    form_class = ManualAdjustmentForm
    success_url = reverse_lazy('manual-adjustment')

    def test_func(self):
        return self.request.user.is_authenticated and self.request.user.is_superadmin()

    def form_valid(self, form):
        dealer = form.cleaned_data['dealer']
        amount = form.cleaned_data['amount']
        tx_type = form.cleaned_data['transaction_type']
        desc = form.cleaned_data['description']
        comm_rate = form.cleaned_data.get('commission_rate', Decimal('0.00'))
        
        commission_amount = amount * (comm_rate / Decimal('100.00'))
        
        txn = Transaction.objects.create(
            sub_dealer=dealer,
            transaction_type=tx_type,
            status=Transaction.Status.APPROVED,
            amount=amount, 
            commission_amount=commission_amount,
            external_user_id=f"ADMIN: {self.request.user.username}",
            description=desc
        )
        log_action(self.request, self.request.user, 'MANUAL_BALANCE_ADJUST', txn, details={
            'amount': float(amount),
            'type': tx_type,
            'dealer': dealer.user.username
        })
        
        messages.success(self.request, f'Adjustment applied successfully. Commission: {commission_amount} TL')
        return super().form_valid(form)

class GlobalSettingsView(UserPassesTestMixin, FormView):
    template_name = 'web/global_settings.html'
    form_class = SystemConfigForm
    success_url = reverse_lazy('global-settings')

    def test_func(self):
        return self.request.user.is_authenticated and self.request.user.is_superadmin()

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['instance'] = SystemConfig.get_solo()
        return kwargs

    def form_valid(self, form):
        form.save()
        log_action(self.request, self.request.user, 'UPDATE_GLOBAL_SETTINGS', details=form.cleaned_data)
        messages.success(self.request, 'System configuration updated.')
        return super().form_valid(form)

class DealerReportView(UserPassesTestMixin, TemplateView):
    template_name = 'web/reports_dealer.html'

    def test_func(self):
        return self.request.user.is_authenticated and self.request.user.is_superadmin()

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        
        # Determine Date Range
        from datetime import  timedelta
        today = timezone.now().date()
        start_date = today - timedelta(days=30) # Default last 30 days
        
        # Aggregation
        dealers = SubDealerProfile.objects.all().select_related('user')
        dealer_stats = []
        
        for dealer in dealers:
            # Filter transactions for this dealer
            txs = Transaction.objects.filter(sub_dealer=dealer, status=Transaction.Status.APPROVED)
            
            deposit = txs.filter(transaction_type='DEPOSIT').aggregate(s=Sum('amount'))['s'] or Decimal('0.00')
            withdraw = txs.filter(transaction_type='WITHDRAW').aggregate(s=Sum('amount'))['s'] or Decimal('0.00')
            
            # Estimate Commission
            commission = deposit * (dealer.commission_rate / Decimal('100.00'))
            
            # Net Balance (Calculated)
            net_balance = deposit - withdraw - commission
            
            dealer_stats.append({
                'username': dealer.user.username,
                'rate': dealer.commission_rate,
                'deposit': deposit,
                'withdraw': withdraw,
                'commission': commission,
                'net_balance': net_balance,
                'current_balance': dealer.current_net_balance, # Compare with stored
                'is_active': dealer.is_active_by_system
            })
            
        ctx['dealer_stats'] = dealer_stats
        return ctx

class CommissionReportView(UserPassesTestMixin, TemplateView):
    template_name = 'web/reports_commission.html'

    def test_func(self):
        return self.request.user.is_authenticated and self.request.user.is_superadmin()

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        
        dealer_id = self.request.GET.get('dealer')
        date_start = self.request.GET.get('date_start')
        date_end = self.request.GET.get('date_end')
        
        qs = Transaction.objects.filter(
            status=Transaction.Status.APPROVED, 
            transaction_type='DEPOSIT'
        ).select_related('sub_dealer')
        
        if dealer_id:
            qs = qs.filter(sub_dealer_id=dealer_id)
        if date_start:
            qs = qs.filter(created_at__date__gte=date_start)
        if date_end:
            qs = qs.filter(created_at__date__lte=date_end)
        
        daily_stats = {} 
        
        for tx in qs:
            # We must use local time for the date string to match user perspective
            local_date = timezone.localtime(tx.created_at).date()
            date_str = local_date.strftime('%Y-%m-%d')
            
            if date_str not in daily_stats:
                daily_stats[date_str] = {'date': date_str, 'volume': Decimal('0.00'), 'commission': Decimal('0.00'), 'count': 0}
            
            comm = tx.amount * (tx.sub_dealer.commission_rate / Decimal('100.00'))
            
            daily_stats[date_str]['volume'] += tx.amount
            daily_stats[date_str]['commission'] += comm
            daily_stats[date_str]['count'] += 1
            
        # Convert to list and sort
        report_data = sorted(daily_stats.values(), key=lambda x: x['date'], reverse=True)
        
        ctx['report_data'] = report_data
        ctx['total_earnings'] = sum(d['commission'] for d in report_data)
        ctx['total_volume'] = sum(d['volume'] for d in report_data)
        ctx['sub_dealers'] = SubDealerProfile.objects.select_related('user').all()
        
        return ctx

class AdminWithdrawalPoolView(UserPassesTestMixin, ListView):
    model = Transaction
    template_name = 'web/admin_withdrawal_pool.html'
    context_object_name = 'transactions'

    def test_func(self):
        return self.request.user.is_authenticated and self.request.user.is_superadmin()

    def get_queryset(self):
        return Transaction.objects.filter(status=Transaction.Status.WAITING_ASSIGNMENT).order_by('created_at')

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        # We need dealers with their live current_net_balance
        ctx['dealers'] = SubDealerProfile.objects.filter(user__is_active=True).select_related('user')
        return ctx

class AssignWithdrawalView(UserPassesTestMixin, View):
    def test_func(self):
        return self.request.user.is_authenticated and self.request.user.is_superadmin()

    def post(self, request, pk):
        dealer_id = request.POST.get('dealer_id')
        txn = get_object_or_404(Transaction, pk=pk, status=Transaction.Status.WAITING_ASSIGNMENT)
        dealer = get_object_or_404(SubDealerProfile, pk=dealer_id)

        # Check balance again just in case (though UI should handle it)
        if dealer.current_net_balance < txn.amount:
            messages.error(request, f"Bakiye yetersiz! {dealer.user.username} bakiyesi: {dealer.current_net_balance} ₺")
            return redirect('admin-withdrawal-pool')

        txn.sub_dealer = dealer
        txn.status = Transaction.Status.PENDING
        txn.save()

        messages.success(request, f"İşlem {dealer.user.username} bayisine atandı.")
        return redirect('admin-withdrawal-pool')

class ReturnToPoolView(UserPassesTestMixin, View):
    def test_func(self):
        return self.request.user.is_authenticated and self.request.user.is_superadmin()

    def post(self, request, pk):
        txn = get_object_or_404(Transaction, pk=pk, transaction_type=Transaction.TransactionType.WITHDRAW)
        
        if txn.status != Transaction.Status.PENDING:
            messages.error(request, "Sadece 'Bekliyor' durumundaki işlemler havuza geri gönderilebilir.")
            return redirect('withdrawal-queue')

        # Critical: Capture the dealer before removing assignment to update their balance
        old_dealer = txn.sub_dealer
        
        txn.sub_dealer = None
        txn.status = Transaction.Status.WAITING_ASSIGNMENT
        txn.save()

        # Update the former dealer's balance since the transaction is no longer their responsibility
        if old_dealer:
            old_dealer.recalculate_balance()

        messages.success(request, f"#{txn.id} nolu işlem başarıyla havuza geri alındı.")
        return redirect('withdrawal-queue')

class AuditLogListView(UserPassesTestMixin, ListView):
    model = AuditLog
    template_name = 'web/admin_audit.html'
    context_object_name = 'logs'
    paginate_by = 50

    def test_func(self):
        return self.request.user.is_authenticated and self.request.user.is_superadmin()

    def get_queryset(self):
        return AuditLog.objects.select_related('user').all().order_by('-created_at')

