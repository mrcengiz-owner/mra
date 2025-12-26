from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django_otp.plugins.otp_totp.models import TOTPDevice
from django_otp.plugins.otp_static.models import StaticDevice

class Command(BaseCommand):
    help = 'Belirtilen kullanıcının tüm 2FA cihazlarını sıfırlar (Reset 2FA)'

    def add_arguments(self, parser):
        parser.add_argument('username', type=str, help='Kullanıcı adı')

    def handle(self, *args, **kwargs):
        username = kwargs['username']
        User = get_user_model()

        try:
            user = User.objects.get(username=username)
        except User.DoesNotExist:
            self.stdout.write(self.style.ERROR(f'Hata: "{username}" adında bir kullanıcı bulunamadı.'))
            return

        # TOTP Cihazlarını Sil
        totp_count, _ = TOTPDevice.objects.filter(user=user).delete()
        
        # Static Cihazları Sil (Backup codes)
        static_count, _ = StaticDevice.objects.filter(user=user).delete()

        self.stdout.write(self.style.SUCCESS(
            f'BAŞARILI: {username} kullanıcısı için 2FA sıfırlandı.\n'
            f'- Silinen TOTP: {totp_count}\n'
            f'- Silinen Static: {static_count}'
        ))
