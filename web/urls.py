from django.urls import path
from django.contrib.auth import views as auth_views
from .views import (
    CustomLoginView, DashboardRedirectView, SuperAdminDashboardView, 
    SubDealerDashboardView,    ReportsPageView, export_reports_csv,
    DepositsListView, TransactionActionView, ManualAdjustmentView, GlobalSettingsView, WithdrawalsListView,
    AdminDealerAnalyticsView, CommissionReportView, AdminWithdrawalPoolView, AssignWithdrawalView, ReturnToPoolView, AuditLogListView, ToggleUserStatusView,
    AdminBankListView, UpdateTransactionAmountView, RejectPoolWithdrawalView
)
from .views_dealer import (
    DealerDepositListView, DealerWithdrawalListView, DealerTransactionUpdateView, 
    DealerBankAccountListView, DealerBankAccountCreateView, DealerBankAccountUpdateView, DealerReportView, DealerTransactionActionView, toggle_bank_status
)
from .api_views import CreateWithdrawalAPIView, DepositRequestAPIView, DepositConfirmAPIView, WithdrawRequestAPIView
from finance.views import BlacklistManagerView, AllDealersListView, UpdateDealerPermissionsView, get_dashboard_stats
from accounts.views import ToggleDealerStatusView
from django.views.decorators.csrf import csrf_exempt

urlpatterns = [

    # Add logout with next_page
    path('logout/', auth_views.LogoutView.as_view(next_page='login'), name='logout'),

    path('', CustomLoginView.as_view(template_name='web/login.html'), name='login'),
    # Dashboard Redirect
    path('dashboard/', DashboardRedirectView.as_view(), name='dashboard-redirect'),
    
    # Admin Panel
    path('web/admin-dashboard/', SuperAdminDashboardView.as_view(), name='admin-dashboard'),
    path('web/admin-panel/deposits/', DepositsListView.as_view(), name='admin-deposits'),
    path('web/admin-panel/withdrawals/', WithdrawalsListView.as_view(), name='admin-withdrawals'),
    # ... other admin paths
    
    # Reports (ADMIN)
    path('reports/', ReportsPageView.as_view(), name='daily-report-page'),
    path('reports/export/', export_reports_csv, name='export-reports-csv'),
    path('reports/dealer/', AdminDealerAnalyticsView.as_view(), name='dealer-analytics-report'), # Renamed View
    path('reports/commission/', CommissionReportView.as_view(), name='commission-report-page'),
    
    # ...
    
    # Dealer Panel
    path('web/dealer-dashboard/', SubDealerDashboardView.as_view(), name='dealer-dashboard'),
    path('dealer/deposits/', DealerDepositListView.as_view(), name='dealer-deposits'),
    path('dealer/withdrawals/', DealerWithdrawalListView.as_view(), name='dealer-withdrawals'),
    path('dealer/transaction/<int:pk>/update/', DealerTransactionUpdateView.as_view(), name='dealer-transaction-update'),
    path('dealer/bank-accounts/', DealerBankAccountListView.as_view(), name='dealer-banks'),
    path('dealer/bank-accounts/add/', DealerBankAccountCreateView.as_view(), name='dealer-bank-add'),
    path('dealer/bank-accounts/<int:pk>/edit/', DealerBankAccountUpdateView.as_view(), name='dealer-bank-edit'),
    path('dealer/reports/', DealerReportView.as_view(), name='dealer-reports'), # This uses views_dealer.DealerReportView
    path('logout/', auth_views.LogoutView.as_view(next_page='/'), name='logout'),
    
    path('redirect/', DashboardRedirectView.as_view(), name='dashboard-redirect'),
    
    path('admin-dashboard/', SuperAdminDashboardView.as_view(), name='admin-dashboard'),
    path('dealer-dashboard/', SubDealerDashboardView.as_view(), name='dealer-dashboard'),
    path('dealer-dashboard/', SubDealerDashboardView.as_view(), name='dealer-dashboard'),
    path('reports/', ReportsPageView.as_view(), name='daily-report-page'),
    path('reports/export/', export_reports_csv, name='export-reports-csv'),
    
    # Financial Ops
    path('yatirimlar/', DepositsListView.as_view(), name='deposits-list'),
    path('cekimler/', WithdrawalsListView.as_view(), name='withdrawal-queue'), # Keeping name for reverse compatibility if needed, but view is new
    path('transaction/<int:pk>/re-pool/', ReturnToPoolView.as_view(), name='transaction-re-pool'),
    path('transaction/<int:pk>/<str:action>/', TransactionActionView.as_view(), name='transaction-action'),
    path('transaction/update-amount/', UpdateTransactionAmountView.as_view(), name='transaction-update-amount'),
    path('manual-adjustment/', ManualAdjustmentView.as_view(), name='manual-adjustment'),
    path('management/withdrawal-pool/', AdminWithdrawalPoolView.as_view(), name='admin-withdrawal-pool'),
    path('management/assign-withdrawal/<int:pk>/', AssignWithdrawalView.as_view(), name='assign-withdrawal'),
    path('management/reject-withdrawal/<int:pk>/', RejectPoolWithdrawalView.as_view(), name='reject-pool-withdrawal'),
    
    # System Ops
    path('global-settings/', GlobalSettingsView.as_view(), name='global-settings'),
    
    # API
    path('api/create-withdrawal/', CreateWithdrawalAPIView.as_view(), name='api-create-withdrawal'),
    path('api/public/withdraw-request/', csrf_exempt(WithdrawRequestAPIView.as_view()), name='api-public-withdraw-request'),
    path('api/public/deposit-request/', csrf_exempt(DepositRequestAPIView.as_view()), name='api-deposit-request'),
    path('api/public/deposit-confirm/', csrf_exempt(DepositConfirmAPIView.as_view()), name='api-deposit-confirm'),

    path('reports/dealer/', DealerReportView.as_view(), name='dealer-report-page'),
    path('reports/commission/', CommissionReportView.as_view(), name='commission-report-page'),
    path('reports/commission/', CommissionReportView.as_view(), name='commission-report-page'),
    path('management/audit-logs/', AuditLogListView.as_view(), name='admin-audit-logs'),
    path('admin-panel/all-bank-accounts/', AdminBankListView.as_view(), name='admin-all-banks'),
    path('admin-panel/blacklist-manager/', BlacklistManagerView.as_view(), name='custom_blacklist'),
    
    # Dealer Routes
    path('dealer/deposits/', DealerDepositListView.as_view(), name='dealer-deposits'),
    path('dealer/withdrawals/', DealerWithdrawalListView.as_view(), name='dealer-withdrawals'),
    path('dealer/transaction/<int:pk>/update/', DealerTransactionUpdateView.as_view(), name='dealer-transaction-update'),
    path('dealer/bank-accounts/', DealerBankAccountListView.as_view(), name='dealer-banks'),
    path('dealer/bank-accounts/add/', DealerBankAccountCreateView.as_view(), name='dealer-bank-add'),
    path('dealer/bank-accounts/<int:pk>/edit/', DealerBankAccountUpdateView.as_view(), name='dealer-bank-edit'),
    path('dealer/reports/', ReportsPageView.as_view(), name='dealer-reports'), # SubDealer sees their own report via ReportsPageView logic
    path('dealer/transaction/<int:pk>/action/<str:action>/', DealerTransactionActionView.as_view(), name='dealer-transaction-action'),
    path('api/dealer/toggle-bank/', toggle_bank_status, name='toggle-bank-status'),
    path('api/management/toggle-user/', ToggleUserStatusView.as_view(), name='toggle-user-status'),
    path('api/management/toggle-dealer-status/', csrf_exempt(ToggleDealerStatusView.as_view()), name='toggle-dealer-status'),
    path('admin-panel/all-dealers/', AllDealersListView.as_view(), name='admin-all-dealers'),
    path('api/management/update-dealer-permission/', UpdateDealerPermissionsView.as_view(), name='update-dealer-permissions'),
    path('api/dashboard-stats/', get_dashboard_stats, name='dashboard_stats'),
]
