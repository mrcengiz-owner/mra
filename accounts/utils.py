from .models import AuditLog

def get_client_ip(request):
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0].strip()
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip

def log_action(request, user, action, target_object=None, details=None):
    """
    Utility function to log an action in the AuditLog.
    """
    ip_address = get_client_ip(request) if request else None
    user_agent = request.META.get('HTTP_USER_AGENT', '')[:500] if request else ''
    
    target_model = target_object._meta.model_name.capitalize() if target_object else None
    target_object_id = str(target_object.pk) if target_object else None
    
    AuditLog.objects.create(
        user=user,
        action=action,
        target_model=target_model,
        target_object_id=target_object_id,
        ip_address=ip_address,
        user_agent=user_agent,
        details=details or {}
    )


def get_client_ip(request):
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip