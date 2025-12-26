from django.shortcuts import render
from two_factor.views import SetupView
import base64

class FixedSetupView(SetupView):
    """
    Standard SetupView'ı override ediyoruz.
    Secret Key'i (base32) context'e ekliyoruz.
    """
    def get_context_data(self, form, **kwargs):
        context = super().get_context_data(form, **kwargs)
        
        if self.steps.current == 'generator':
            try:
                # 1. Yöntem: View'ın kendi metodunu dene (Argümansız)
                # Not: Kütüphaneye göre get_device() argüman almayabilir.
                device = self.get_device()
                
                # 2. Yöntem: Eğer yukarıdaki boş dönerse DB'den bul
                if not device:
                    user = self.request.user
                    if user.is_authenticated:
                        device = user.totpdevice_set.filter(confirmed=False).first()

                if device and hasattr(device, 'bin_key'):
                     # Base32 formatına çevir (JBSWY3DZE...)
                     encoded_key = base64.b32encode(device.bin_key).decode('utf-8')
                     context['secret_key'] = encoded_key
            except Exception as e:
                print(f"Secret key extraction error: {e}")
                
        return context

    def get_success_url(self):
        from django.urls import reverse
        return reverse('dashboard-redirect')

from django.views import View
from django.http import JsonResponse
from django.utils.decorators import method_decorator
from django.contrib.auth.decorators import user_passes_test
from .models import CustomUser
import json

@method_decorator(user_passes_test(lambda u: u.is_superuser), name='dispatch')
class ToggleDealerStatusView(View):
    def post(self, request):
        try:
            data = json.loads(request.body)
            user_id = data.get('user_id')
            user = CustomUser.objects.get(id=user_id)
            
            # Toggle is_active
            new_status = not user.is_active
            user.is_active = new_status
            user.save()
            
            # SubDealerProfile active check override
            if hasattr(user, 'profile'):
                user.profile.is_active_by_system = new_status
                user.profile.save()
                print(f"Dealer {user.username} toggled to {new_status} (System & User Level)")

            return JsonResponse({'success': True, 'new_status': new_status})
        except CustomUser.DoesNotExist:
            return JsonResponse({'success': False, 'error': 'User not found'}, status=404)
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)}, status=500)
