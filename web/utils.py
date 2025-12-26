from finance.models import Blacklist

def is_blacklisted(value, type):
    """
    Checks if a given value is in the blacklist for the specified type.
    """
    return Blacklist.objects.filter(value=value, type=type, is_active=True).exists()

def get_client_ip(request):
    """
    Retrieves the client's IP address from the request.
    """
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip
