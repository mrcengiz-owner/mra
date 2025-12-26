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
    
    # Sanitize details (Convert Decimal to float/str)
    from decimal import Decimal
    from django.core.serializers.json import DjangoJSONEncoder
    import json

    safe_details = details or {}
    
    # Simple recursive function to handle decimals inside dicts/lists
    def make_serializable(obj):
        if isinstance(obj, Decimal):
            return float(obj)
        elif isinstance(obj, dict):
            return {k: make_serializable(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [make_serializable(i) for i in obj]
        return obj

    try:
        safe_details = make_serializable(safe_details)
    except Exception:
        safe_details = str(details)

    AuditLog.objects.create(
        user=user,
        action=action,
        target_model=target_model,
        target_object_id=target_object_id,
        ip_address=ip_address,
        user_agent=user_agent,
        details=safe_details
    )


def get_client_ip(request):
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip