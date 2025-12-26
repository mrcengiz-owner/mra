from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django_otp.plugins.otp_totp.models import TOTPDevice
import time

class Command(BaseCommand):
    help = 'Kullanıcının 2FA kodunu sunucu tarafında doğrular ve beklenen kodu gösterir (Debug 2FA)'

    def add_arguments(self, parser):
        parser.add_argument('username', type=str, help='Kullanıcı adı')
        parser.add_argument('code', type=str, help='Telefondaki 6 haneli kod')

    def handle(self, *args, **kwargs):
        username = kwargs['username']
        code = kwargs['code']
        User = get_user_model()

        try:
            user = User.objects.get(username=username)
        except User.DoesNotExist:
            self.stdout.write(self.style.ERROR(f'Hata: "{username}" bulunamadı.'))
            return

        devices = TOTPDevice.objects.filter(user=user)
        if not devices.exists():
            self.stdout.write(self.style.WARNING(f'Uyarı: {username} için kayıtlı TOTP cihazı yok.'))
            return

        for device in devices:
            self.stdout.write(self.style.SUCCESS(f'--- Cihaz Kontrolü: {device.name} ---'))
            
            # 1. Doğrulama
            is_valid = device.verify_token(code)
            if is_valid:
                self.stdout.write(self.style.SUCCESS('✅ KOD GEÇERLİ! (Zaman senkronizasyonu başarılı)'))
                device.confirmed = True
                device.save()
            else:
                self.stdout.write(self.style.ERROR('❌ KOD GEÇERSİZ.'))

            # 2. Beklenen Kod (Debug)
            # Not: TOTP anlık değişir, bu yüzden o anlık kodu üretip basarız.
            # verify_token işlemi counter'ı ileri atabilir, dikkat.
            # Ancak biz sadece debug için üretiyoruz.
            current_token = device.token() # O anki geçerli token
            self.stdout.write(f'   Sunucunun beklediği anlık token: [{current_token}]')
            self.stdout.write(f'   Girdiğiniz token: [{code}]')
            
            # Zaman kayması tahmini
            import otpt
            totp = otpt.TOTP(device.bin_key)
            self.stdout.write(f'   Drift Testi:')
            for offset in range(-3, 4):
                t = totp.token(time.time() + (offset * 30))
                mark = '<-- EŞLEŞTİ' if str(t) == str(code) else ''
                self.stdout.write(f'   Offset {offset}: {t} {mark}')
            
            self.stdout.write('--------------------------------------------\n')
