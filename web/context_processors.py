from django.conf import settings
from finance.models import SystemConfig

def global_config(request):
    return {
        'system_config': SystemConfig.get_solo(),
        'PUSHER_KEY': settings.PUSHER_KEY,
        'PUSHER_CLUSTER': settings.PUSHER_CLUSTER,
    }
