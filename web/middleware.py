from django.http import JsonResponse, HttpResponse
from django.conf import settings
from django.shortcuts import redirect
from finance.models import SystemConfig
import logging

class MasterAccessMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        path = request.path_info
        
        # Only check /admin/ paths
        if path.startswith('/admin/'):
             # If user is authenticated but NOT superadmin
             if request.user.is_authenticated and not request.user.is_superuser:
                 # Redirect Operational Admins (is_staff=True but not superuser) to their dashboard
                 if request.user.is_staff:
                     return redirect('/web/admin-dashboard/')
                 else:
                     return redirect('/web/dealer-dashboard/') # Fallback for plain users

        return self.get_response(request)

class MaintenanceMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # 1. Check if maintenance mode is active
        try:
            config = SystemConfig.get_solo()
            is_maintenance = config.is_maintenance_mode
        except:
            is_maintenance = False

        if is_maintenance:
            # 2. Check exemptions
            # Allow:
            # - Requests to /admin/
            # - Requests from Superadmins (if authenticated)
            # - Static/Media files (handled by web server or Whitenoise usually, but good to ignore here)
            
            path = request.path_info
            
            if path.startswith('/admin/') or path.startswith('/static/') or path.startswith('/media/'):
                return self.get_response(request)

            if request.user.is_authenticated and request.user.is_superadmin():
                 return self.get_response(request)

            # 3. Block logic
            # API paths return JSON
            if path.startswith('/api/'):
                return JsonResponse(
                    {"error": "Sistem şu an bakım modundadır. Lütfen daha sonra tekrar deneyiniz."},
                    status=503
                )
            
            # Others return HTML
            return HttpResponse(
                """
                <div style="font-family: sans-serif; text-align: center; padding-top: 50px;">
                    <h1>Sistem Bakımda</h1>
                    <p>Sistemimizde güncelleme çalışması yapılmaktadır. Lütfen kısa bir süre sonra tekrar deneyiniz.</p>
                </div>
                """,
                status=503
            )

        return self.get_response(request)

class Enforce2FAMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # 1. Check if user is authenticated
        if request.user.is_authenticated:
            # 2. Check path exemptions (logout, setup, admin logout, static)
            path = request.path_info
            if path.startswith('/account/two_factor/') or \
               path.startswith('/logout/') or \
               path.startswith('/account/logout/') or \
               path.startswith('/admin/logout/') or \
               path.startswith('/static/') or \
               path.startswith('/media/') or \
               path == '/' or \
               path.startswith('/web/redirect/'):
                return self.get_response(request)

            # 3. Check if user has TOTP device
            # django-two-factor uses default_device usually
            from django_otp import user_has_device
            if not user_has_device(request.user):
                # Redirect to setup
                from django.urls import reverse
                return redirect('two_factor:setup')

        return self.get_response(request)
