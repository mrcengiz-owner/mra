from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django_otp.plugins.otp_totp.models import TOTPDevice

class Command(BaseCommand):
    help = 'Wipes all 2FA devices for a user (Emergency Reset)'

    def add_arguments(self, parser):
        parser.add_argument('username', type=str, help='Username to wipe')

    def handle(self, *args, **kwargs):
        username = kwargs['username']
        User = get_user_model()
        
        try:
            user = User.objects.get(username=username)
        except User.DoesNotExist:
            self.stdout.write(self.style.ERROR(f'User {username} not found'))
            return

        # Wipe TOTP
        count, _ = user.totpdevice_set.all().delete()
        
        # Wipe Static/Backup if any (usually linked via user relation too, but checking specifically for TOTP first)
        from django_otp.plugins.otp_static.models import StaticDevice
        s_count, _ = user.staticdevice_set.all().delete()
        
        self.stdout.write(self.style.SUCCESS(f'WIPED: {count} TOTP devices, {s_count} Static devices for {username}.'))
