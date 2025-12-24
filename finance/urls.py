from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import AccountSelectionView, TransactionViewSet
from .reporting_views import DailyReportView

router = DefaultRouter()
router.register(r'transactions', TransactionViewSet)

urlpatterns = [
    path('get-deposit-account/', AccountSelectionView.as_view(), name='get-deposit-account'),
    path('reports/daily/', DailyReportView.as_view(), name='daily-report'),
    path('', include(router.urls)),
]
