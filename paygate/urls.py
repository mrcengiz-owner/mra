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
from django.urls import path, include, re_path
from django.conf import settings
from django.views.static import serve

from two_factor.urls import urlpatterns as tf_urls
from two_factor.admin import AdminSiteOTPRequired

# Force Admin to check for 2FA
admin.site.__class__ = AdminSiteOTPRequired

# Strict Access: Only Superusers
def permission_check(request):
    return request.user.is_active and request.user.is_superuser
admin.site.has_permission = permission_check

from two_factor.views import LoginView

from accounts.views import FixedSetupView

from web.api_views import DepositRequestAPIView, WithdrawRequestAPIView, DepositConfirmAPIView
from django.views.decorators.csrf import csrf_exempt

from rest_framework import permissions
from drf_yasg.views import get_schema_view
from drf_yasg import openapi

schema_view = get_schema_view(
   openapi.Info(
      title="NexKasa API",
      default_version='v1',
      description="Public API Documentation for NexKasa Payment Gateway",
      terms_of_service="https://www.nexkasa.com/terms/",
      contact=openapi.Contact(email="support@nexkasa.com"),
      license=openapi.License(name="BSD License"),
   ),
   public=True,
   permission_classes=(permissions.AllowAny,),
)

urlpatterns = [
    # Swagger / Redoc
    path('swagger/', schema_view.with_ui('swagger', cache_timeout=0), name='schema-swagger-ui'),
    path('redoc/', schema_view.with_ui('redoc', cache_timeout=0), name='schema-redoc'),
    path('swagger.json', schema_view.without_ui(cache_timeout=0), name='schema-json'),

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
    
    # Force Serve Static/Media (Bypass Nginx/Whitenoise issues)
    re_path(r'^media/(?P<path>.*)$', serve, {'document_root': settings.MEDIA_ROOT}),
    re_path(r'^static/(?P<path>.*)$', serve, {'document_root': settings.STATIC_ROOT}),
]
