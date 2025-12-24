from django.urls import path
from django.contrib.auth import views as auth_views
from .views import (
    CustomLoginView, DashboardRedirectView, SuperAdminDashboardView, 
    SubDealerDashboardView,    ReportsPageView, export_reports_csv,
    DepositsListView, TransactionActionView, ManualAdjustmentView, GlobalSettingsView, WithdrawalsListView,
    DealerReportView, CommissionReportView, AdminWithdrawalPoolView, AssignWithdrawalView, ReturnToPoolView, AuditLogListView
)
from .views_dealer import (
    DealerDepositListView, DealerWithdrawalListView, DealerTransactionUpdateView, 
    DealerBankAccountListView, DealerBankAccountCreateView, DealerBankAccountUpdateView, DealerReportView, DealerTransactionActionView, toggle_bank_status
)
from .api_views import CreateWithdrawalAPIView, DepositRequestAPIView, DepositConfirmAPIView, WithdrawRequestAPIView

urlpatterns = [
    path('login/', CustomLoginView.as_view(), name='login'),
    # Add logout with next_page
    path('logout/', auth_views.LogoutView.as_view(next_page='login'), name='logout'),
    
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
    path('manual-adjustment/', ManualAdjustmentView.as_view(), name='manual-adjustment'),
    path('management/withdrawal-pool/', AdminWithdrawalPoolView.as_view(), name='admin-withdrawal-pool'),
    path('management/assign-withdrawal/<int:pk>/', AssignWithdrawalView.as_view(), name='assign-withdrawal'),
    
    # System Ops
    path('global-settings/', GlobalSettingsView.as_view(), name='global-settings'),
    
    # API
    path('api/create-withdrawal/', CreateWithdrawalAPIView.as_view(), name='api-create-withdrawal'),
    path('api/public/withdraw-request/', WithdrawRequestAPIView.as_view(), name='api-public-withdraw-request'),
    path('api/public/deposit-request/', DepositRequestAPIView.as_view(), name='api-deposit-request'),
    path('api/public/deposit-confirm/', DepositConfirmAPIView.as_view(), name='api-deposit-confirm'),

    path('reports/dealer/', DealerReportView.as_view(), name='dealer-report-page'),
    path('reports/commission/', CommissionReportView.as_view(), name='commission-report-page'),
    path('management/audit-logs/', AuditLogListView.as_view(), name='admin-audit-logs'),
    
    # Dealer Routes
    path('dealer/deposits/', DealerDepositListView.as_view(), name='dealer-deposits'),
    path('dealer/withdrawals/', DealerWithdrawalListView.as_view(), name='dealer-withdrawals'),
    path('dealer/transaction/<int:pk>/update/', DealerTransactionUpdateView.as_view(), name='dealer-transaction-update'),
    path('dealer/bank-accounts/', DealerBankAccountListView.as_view(), name='dealer-banks'),
    path('dealer/bank-accounts/add/', DealerBankAccountCreateView.as_view(), name='dealer-bank-add'),
    path('dealer/bank-accounts/<int:pk>/edit/', DealerBankAccountUpdateView.as_view(), name='dealer-bank-edit'),
    path('dealer/reports/', DealerReportView.as_view(), name='dealer-reports'), # This likely needs its own specific View for the SUbDealer, but re-using for now if allowed, or it was meant to be the admin view for dealers.
    path('dealer/transaction/<int:pk>/action/<str:action>/', DealerTransactionActionView.as_view(), name='dealer-transaction-action'),
    path('api/dealer/toggle-bank/', toggle_bank_status, name='toggle-bank-status'),
]
