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
from .forms import SystemConfigForm, ManualAdjustmentForm, WithdrawalApprovalForm
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
        if user.is_superadmin() or user.role == CustomUser.Roles.ADMIN:
            return '/web/admin-dashboard/'
        elif user.is_subdealer():
            return '/web/dealer-dashboard/'
        return '/admin/' # Fallback

class DashboardRedirectView(LoginRequiredMixin, TemplateView):
    def get(self, request, *args, **kwargs):
        if request.user.is_superadmin() or request.user.role == CustomUser.Roles.ADMIN:
            return redirect('admin-dashboard')
        elif request.user.is_subdealer():
            return redirect('dealer-dashboard')
        return redirect('login')

class SuperAdminDashboardView(UserPassesTestMixin, TemplateView):
    template_name = 'web/admin_dashboard.html'

    def test_func(self):
        u = self.request.user
        return u.is_authenticated and (u.is_superadmin() or u.role == CustomUser.Roles.ADMIN)

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
            
        # C. Net Kasa: Sum of active dealers' wallet balances
        # This includes Manual Adjustments automatically since they affect the balance field.
        total_dealer_balance = SubDealerProfile.objects.filter(user__is_active=True).aggregate(
            total=Sum('current_net_balance')
        )['total'] or Decimal('0.00')
        
        ctx['total_volume_in'] = total_in_gross
        ctx['total_volume_out'] = total_out
        ctx['total_commission'] = total_in_comm
        ctx['net_balance'] = total_dealer_balance
        
        # Active Dealer Count
        ctx['active_dealer_count'] = SubDealerProfile.objects.filter(is_active_by_system=True).count()
        
        # Dealers List
        ctx['dealers'] = SubDealerProfile.objects.all().select_related('user')
        
        return ctx

class SubDealerDashboardView(UserPassesTestMixin, TemplateView):
    template_name = 'web/dealer_dashboard.html'
    
    def test_func(self):
        return self.request.user.is_authenticated and self.request.user.is_subdealer()

    def dispatch(self, request, *args, **kwargs):
        if not hasattr(request.user, 'profile'):
             messages.error(request, "Hesap profili bulunamadı. Lütfen yönetici ile iletişime geçin.")
             return redirect('logout')
        return super().dispatch(request, *args, **kwargs)

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


class BaseAdminReportView(LoginRequiredMixin, UserPassesTestMixin):
    """
    Base view for Admin Reports.
    Allows access to Superusers, Staff, and users with ADMIN/SUPERADMIN roles.
    """
    def test_func(self):
        user = self.request.user
        if not user.is_authenticated:
            return False
            
        # Check for multiple permission levels
        return (
            user.is_superuser or 
            user.is_staff or 
            getattr(user, 'role', '') in ['SUPERADMIN', 'ADMIN']
        )

class ReportsPageView(UserPassesTestMixin, FilterView):
    template_name = 'web/reports.html'
    filterset_class = TransactionFilter
    context_object_name = 'transactions'
    
    def test_func(self):
        # Allow SuperAdmin, Admin and SubDealer (with restricted data)
        return self.request.user.is_authenticated and (self.request.user.is_superadmin() or self.request.user.role == CustomUser.Roles.ADMIN or self.request.user.is_subdealer())

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
        return self.request.user.is_authenticated and (self.request.user.is_superadmin() or self.request.user.role == CustomUser.Roles.ADMIN)
    
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
        return self.request.user.is_authenticated and (self.request.user.is_superadmin() or self.request.user.role == CustomUser.Roles.ADMIN)

    def post(self, request, pk, action):
        tx = get_object_or_404(Transaction, pk=pk)
        
        # Action: Approve
        if action == 'approve':
            if tx.status != Transaction.Status.PENDING:
                messages.error(request, 'İşlem zaten sonuçlanmış.')
                return self._redirect_back(tx)

            # WITHDRAWAL LOGIC: Handle Receipt & Bank
            if tx.transaction_type == Transaction.TransactionType.WITHDRAW:
                form = WithdrawalApprovalForm(request.POST, request.FILES, instance=tx)
                if form.is_valid():
                    tx = form.save(commit=False)
                    tx.status = Transaction.Status.APPROVED
                    tx.processed_at = timezone.now()
                    tx.processed_by = request.user
                    tx.save()
                    
                    send_transaction_webhook(tx)
                    log_action(request, request.user, 'APPROVE_WITHDRAWAL', tx, details={
                        'amount': float(tx.amount),
                        'bank': str(tx.processed_by_bank)
                    })
                    messages.success(request, f'Çekim #{tx.id} onaylandı ve dekont kaydedildi.')
                    return self._redirect_back(tx)
                else:
                     # Form Error Handling
                    for field, errors in form.errors.items():
                        for error in errors:
                            messages.error(request, f"{field}: {error}")
                    return self._redirect_back(tx)
                
            # DEPOSIT LOGIC (Existing)
            # 1. RECALCULATE COMMISSION (Always based on current DB amount)
            # The amount should be updated via 'update_transaction_amount' view BEFORE approval if needed.
            # We explicitly recalculate here to be safe and ensure dealer gets correct cut.
            if tx.sub_dealer:
                rate = tx.sub_dealer.commission_rate
                # Calculate: Amount * (Rate / 100)
                tx.commission_amount = tx.amount * (rate / Decimal('100.00'))
            else:
                tx.commission_amount = Decimal('0.00')

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
                return JsonResponse({'status': 'success', 'message': f'İşlem #{tx.id} reddedildi.'}, encoder=DjangoJSONEncoder)
            
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
        return self.request.user.is_authenticated and (self.request.user.is_superadmin() or self.request.user.role == CustomUser.Roles.ADMIN)
    
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
        # Add active banks for the modal
        ctx['admin_banks'] = BankAccount.objects.filter(is_active=True).select_related('sub_dealer')
        return ctx

class ManualAdjustmentView(UserPassesTestMixin, FormView):
    template_name = 'web/manual_adjustment.html'
    form_class = ManualAdjustmentForm
    success_url = reverse_lazy('manual-adjustment')

    def test_func(self):
        return self.request.user.is_authenticated and (self.request.user.is_superadmin() or self.request.user.role == CustomUser.Roles.ADMIN)

    def form_valid(self, form):
        dealer = form.cleaned_data['dealer']
        tx_type = form.cleaned_data['transaction_type']
        category = form.cleaned_data['category']
        amount = form.cleaned_data['amount']
        desc = form.cleaned_data['description']
        
        # Create Transaction Record
        tx = Transaction.objects.create(
            sub_dealer=dealer,
            transaction_type=tx_type,
            category=category,
            status=Transaction.Status.APPROVED,
            amount=amount,
            #  Manuel İşlemlerde, aksi belirtilmedikçe komisyon genellikle 0'dır, ancak mevcut formda değildir.
            # Güvenlik açısından komisyonu açıkça 0 olarak belirledik.
            commission_amount=Decimal('0.00'),
            description=desc,
            processed_by=self.request.user,
            processed_at=timezone.now(),
            external_user_id=f"ADMIN: {self.request.user.username}" # Traceability
        )
        
        # Update Balance
        dealer.recalculate_balance()
        
        # Log Action
        log_action(self.request, self.request.user, 'MANUAL_ADJUSTMENT', tx, details={
            'amount': float(amount),
            'type': tx_type,
            'category': category
        })
        
        messages.success(self.request, f'Manuel işlem başarıyla kaydedildi ve bakiye güncellendi. (ID: {tx.id})')
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

class AdminDealerAnalyticsView(BaseAdminReportView, TemplateView):
    template_name = 'web/reports_dealer.html'

    # test_func inherited from BaseAdminReportView

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        
        # Determine Date Range from GET params or default
        date_start = self.request.GET.get('date_start')
        date_end = self.request.GET.get('date_end')
        
        from django.db.models import Sum, Count, Avg, F, Q, Case, When, FloatField, DurationField, ExpressionWrapper
        from django.db.models.functions import Cast
        
        # Base Queryset for Aggregation
        dealers = SubDealerProfile.objects.all().select_related('user')
        
        # We need to filter aggregation by date if provided
        date_filter = Q()
        if date_start:
            date_filter &= Q(transactions__created_at__date__gte=date_start)
        if date_end:
            date_filter &= Q(transactions__created_at__date__lte=date_end)
            
        # Main Aggregation Query
        dealer_stats = dealers.annotate(
            total_tx_count=Count('transactions', filter=date_filter),
            
            # Volume Metrics
            deposit_vol=Sum('transactions__amount', 
                filter=date_filter & Q(transactions__transaction_type='DEPOSIT') & Q(transactions__status='APPROVED'),
                default=0
            ),
            withdraw_vol=Sum('transactions__amount', 
                filter=date_filter & Q(transactions__transaction_type='WITHDRAW') & Q(transactions__status='APPROVED'),
                default=0
            ),
            
            # Commission Metrics
            total_commission=Sum('transactions__commission_amount', 
                filter=date_filter & Q(transactions__status='APPROVED'),
                default=0
            ),
            
            # Operational Metrics
            approved_count=Count('transactions', 
                filter=date_filter & Q(transactions__status='APPROVED')
            ),
            
            # Success Rate: Approved / Total (We handle division by zero in template or here)
            # Duration: Update - Create (Only for Approved transactions properly processed)
            avg_duration=Avg(
                ExpressionWrapper(F('transactions__processed_at') - F('transactions__created_at'), output_field=DurationField()),
                filter=date_filter & Q(transactions__status='APPROVED')
            )
        ).order_by('-deposit_vol')
        
        # Post-Processing
        report_data = []
        for d in dealer_stats:
            success_rate = 0
            if d.total_tx_count > 0:
                success_rate = (d.approved_count / d.total_tx_count) * 100
            
            # Calculate Net Volume (In - Out)
            net_vol = (d.deposit_vol or 0) - (d.withdraw_vol or 0)
            
            report_data.append({
                'dealer': d,
                'username': d.user.username,
                'deposit_vol': d.deposit_vol or 0,
                'withdraw_vol': d.withdraw_vol or 0,
                'net_volume': net_vol,
                'total_commission': d.total_commission or 0,
                'success_rate': success_rate,
                'avg_duration': d.avg_duration,
                'tx_count': d.total_tx_count
            })
            
        ctx['dealer_stats'] = report_data
        
        # Summary Cards (Top Performers)
        if report_data:
            # Sort for Top Volume
            ctx['top_volume_dealer'] = max(report_data, key=lambda x: x['net_volume'])
            # Sort for Fastest (exclude None duration)
            valid_durations = [d for d in report_data if d['avg_duration']]
            if valid_durations:
                ctx['fastest_dealer'] = min(valid_durations, key=lambda x: x['avg_duration'])
            
        return ctx

class CommissionReportView(BaseAdminReportView, TemplateView):
    template_name = 'web/reports_commission.html'

    # test_func inherited from BaseAdminReportView

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        
        dealer_id = self.request.GET.get('dealer')
        date_start = self.request.GET.get('date_start')
        date_end = self.request.GET.get('date_end')
        
        from django.db.models.functions import TruncDate
        from django.db.models import Sum, Count, Case, When, F, DecimalField
        
        # Base Query: All Approved Transactions
        qs = Transaction.objects.filter(status=Transaction.Status.APPROVED).select_related('sub_dealer')
        
        if dealer_id:
            qs = qs.filter(sub_dealer_id=dealer_id)
        if date_start:
            qs = qs.filter(created_at__date__gte=date_start)
        if date_end:
            qs = qs.filter(created_at__date__lte=date_end)
            
        # Group by Date
        daily_stats = qs.annotate(date=TruncDate('created_at')).values('date').annotate(
            # Volume: Deposits + Manual Credits
            volume=Sum(
                Case(
                    When(transaction_type__in=['DEPOSIT', 'MANUAL_CREDIT'], then=F('amount')),
                    default=0,
                    output_field=DecimalField()
                )
            ),
            # Commission: From DB field (since it is calculated on approval)
            # Differentiating sources if needed, but 'commission_amount' holds the cut.
            commission_total=Sum('commission_amount'),
            
            # Count
            count=Count('id')
        ).order_by('-date')
        
        # Prepare for Template
        report_data = []
        chart_labels = []
        chart_data = []
        
        total_earnings = Decimal('0.00')
        total_volume = Decimal('0.00')
        
        for d in daily_stats:
            vol = d['volume'] or Decimal('0.00')
            comm = d['commission_total'] or Decimal('0.00')
            
            report_data.append({
                'date': d['date'],
                'volume': vol,
                'commission': comm,
                'count': d['count']
            })
            
            total_earnings += comm
            total_volume += vol
            
            # For Chart (Reverse order usually better but let's strictly follow list or reverse in JS)
            chart_labels.append(d['date'].strftime('%Y-%m-%d'))
            chart_data.append(float(comm))
            
        ctx['report_data'] = report_data
        ctx['total_earnings'] = total_earnings
        ctx['total_volume'] = total_volume
        
        # Chart JSON
        import json
        ctx['chart_labels'] = json.dumps(list(reversed(chart_labels)))
        ctx['chart_data'] = json.dumps(list(reversed(chart_data)))
        
        ctx['sub_dealers'] = SubDealerProfile.objects.select_related('user').all()
        
        return ctx

class AdminWithdrawalPoolView(UserPassesTestMixin, ListView):
    model = Transaction
    template_name = 'web/admin_withdrawal_pool.html'
    context_object_name = 'transactions'

    def test_func(self):
        return self.request.user.is_authenticated and (self.request.user.is_superadmin() or self.request.user.role == CustomUser.Roles.ADMIN)

    def get_queryset(self):
        return Transaction.objects.filter(status=Transaction.Status.WAITING_ASSIGNMENT).order_by('created_at')

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        # We need dealers with their live current_net_balance
        ctx['dealers'] = SubDealerProfile.objects.filter(user__is_active=True).select_related('user')
        return ctx

class AssignWithdrawalView(UserPassesTestMixin, View):
    def test_func(self):
        return self.request.user.is_authenticated and (self.request.user.is_superadmin() or self.request.user.role == CustomUser.Roles.ADMIN)

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

class RejectPoolWithdrawalView(UserPassesTestMixin, View):
    def test_func(self):
        return self.request.user.is_authenticated and (self.request.user.is_superadmin() or self.request.user.role == CustomUser.Roles.ADMIN)

    def post(self, request, pk):
        txn = get_object_or_404(Transaction, pk=pk, status=Transaction.Status.WAITING_ASSIGNMENT)
        reason = request.POST.get('rejection_reason')
        
        txn.status = Transaction.Status.REJECTED
        txn.rejection_reason = reason or "Admin tarafından havuzdan reddedildi."
        txn.processed_at = timezone.now()
        txn.processed_by = request.user
        txn.save()

        messages.warning(request, f"#{txn.id} numaralı işlem reddedildi.")
        return redirect('admin-withdrawal-pool')

class ReturnToPoolView(UserPassesTestMixin, View):
    def test_func(self):
        return self.request.user.is_authenticated and (self.request.user.is_superadmin() or self.request.user.role == CustomUser.Roles.ADMIN)

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
        return self.request.user.is_authenticated and (self.request.user.is_superadmin() or self.request.user.role == CustomUser.Roles.ADMIN)

    def get_queryset(self):
        return AuditLog.objects.select_related('user').all().order_by('-created_at')



class ToggleUserStatusView(UserPassesTestMixin, View):
    """
    AJAX view to toggle user active status.
    Accessible by Staff users (Operational Admins) and Superadmins.
    """
    def test_func(self):
        return self.request.user.is_authenticated and (self.request.user.is_staff or self.request.user.role == CustomUser.Roles.ADMIN)

    def post(self, request):
        user_id = request.POST.get('user_id')
        if not user_id:
            return JsonResponse({'status': 'error', 'message': 'User ID required'}, status=400)
            
        target_user = get_object_or_404(CustomUser, pk=user_id)
        
        # Prevent disabling superusers or oneself
        if target_user.is_superuser:
            return JsonResponse({'status': 'error', 'message': 'Cannot modify Superuser'}, status=403)
        if target_user == request.user:
            return JsonResponse({'status': 'error', 'message': 'Cannot modify yourself'}, status=403)
            
        # Toggle
        target_user.is_active = not target_user.is_active
        target_user.save()
        
        # Log action
        log_action(request, request.user, 'TOGGLE_USER_STATUS', target_user, details={'new_status': target_user.is_active})
        
        return JsonResponse({
            'status': 'success', 
            'new_state': target_user.is_active,
            'message': f'User {target_user.username} is now ' + ('Active' if target_user.is_active else 'Inactive')
        })


class AdminBankListView(UserPassesTestMixin, ListView):
    model = BankAccount
    template_name = 'web/admin_all_banks.html'
    context_object_name = 'banks'

    def test_func(self):
        return self.request.user.is_authenticated and (self.request.user.is_staff or self.request.user.is_superuser or self.request.user.role == CustomUser.Roles.ADMIN)

    def get_queryset(self):
        # Show all banks, ordered by bank name
        return BankAccount.objects.select_related('sub_dealer__user').all().order_by('bank_name')


class UpdateTransactionAmountView(UserPassesTestMixin, View):
    """
    AJAX view to update transaction amount before approval.
    """
    def test_func(self):
        u = self.request.user
        return u.is_authenticated and (u.is_superuser or u.is_staff or u.is_subdealer() or u.role == CustomUser.Roles.ADMIN)

    def post(self, request):
        # 1. Permission Check: Can this user edit amounts?
        if request.user.is_subdealer() and not (request.user.is_superuser or request.user.is_staff):
             if hasattr(request.user, 'profile') and not request.user.profile.can_edit_amounts:
                  return JsonResponse({'status': 'error', 'message': 'Miktar düzenleme yetkiniz yok!'}, status=403)

        tx_id = request.POST.get('id')
        amount_str = request.POST.get('amount')
        
        if not tx_id or not amount_str:
            return JsonResponse({'status': 'error', 'message': 'Eksik Parametreler.'}, status=400)
            
        tx = get_object_or_404(Transaction, pk=tx_id)
        
        # Security: If SubDealer, ensure it's their transaction
        if request.user.is_subdealer() and not (request.user.is_superuser or request.user.is_staff):
             if tx.sub_dealer.user != request.user:
                 return JsonResponse({'status': 'error', 'message': 'Yetkilendirildi'}, status=403)
        
        if tx.status != Transaction.Status.PENDING:
             return JsonResponse({'status': 'error', 'message': 'Only PENDING transactions can be edited.'}, status=400)

        try:
            # Clean and parse amount
            clean_amount = amount_str.replace(',', '.')
            new_amount = Decimal(clean_amount)
            
            if new_amount <= 0:
                 return JsonResponse({'status': 'error', 'message': 'Amount must be positive.'}, status=400)

            tx.amount = new_amount
            tx.save(update_fields=['amount'])
            
            return JsonResponse({'status': 'success', 'new_amount': str(new_amount)})
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=400)
