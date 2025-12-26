"""
URL configuration for paygate project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.0/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include

from two_factor.urls import urlpatterns as tf_urls
from two_factor.admin import AdminSiteOTPRequired

# Force Admin to check for 2FA
admin.site.__class__ = AdminSiteOTPRequired

from two_factor.views import LoginView

from accounts.views import FixedSetupView

from web.api_views import DepositRequestAPIView, WithdrawRequestAPIView, DepositConfirmAPIView
from django.views.decorators.csrf import csrf_exempt

urlpatterns = [
    path('', LoginView.as_view(template_name='two_factor/core/login.html'), name='login'),
    # Custom View - Standart olanı eziyoruz
    path('account/two_factor/setup/', FixedSetupView.as_view(), name='setup'),
    path('', include(tf_urls)),
    path('i18n/', include('django.conf.urls.i18n')),
    path('admin/', admin.site.urls),

    # PUBLIC API ENDPOINTS (CSRF Exempt - Root Level)
    path('api/public/withdraw-request/', csrf_exempt(WithdrawRequestAPIView.as_view()), name='root-api-public-withdraw'),
    path('api/public/deposit-request/', csrf_exempt(DepositRequestAPIView.as_view()), name='root-api-deposit-request'),
    path('api/public/deposit-confirm/', csrf_exempt(DepositConfirmAPIView.as_view()), name='root-api-deposit-confirm'),

    path('api/', include('finance.urls')),
    path('web/', include('web.urls')),
]

from django.conf import settings
from django.conf.urls.static import static

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
