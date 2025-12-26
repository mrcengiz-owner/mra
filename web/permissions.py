from rest_framework import permissions
from accounts.models import APIClient
import logging

logger = logging.getLogger(__name__)

class IsAuthenticatedClient(permissions.BasePermission):
    """
    Custom permission for Public API clients.
    Checks X-API-KEY header and validates against whitelisted IPs.
    """
    def has_permission(self, request, view):
        # If ApiKeyAuthentication ran successfully, request.auth should be the APIClient object
        client = request.auth
        
        # If authentication failed or wasn't the ApiKeyAuthentication, try manual check (fallback)
        # But for DepositRequestAPIView, we enforce Auth class, so this strictly implies success.
        from accounts.models import APIClient # Ensure import if needed
        
        if not isinstance(client, APIClient):
            # Fallback for views that might not have the Auth class but use this Permission
            api_key = request.headers.get('X-API-KEY')
            if not api_key:
                return False
            try:
                client = APIClient.objects.get(api_key=api_key, is_active=True)
            except APIClient.DoesNotExist:
                logger.warning(f"Invalid API Key attempt: {api_key}")
                return False

        # IP Validation
        ip_addr = self.get_client_ip(request)
        
        # Ensure client has allowed_ips attribute
        if not hasattr(client, 'allowed_ips'):
             return False

        whitelisted_ips = [ip.strip() for ip in client.allowed_ips.split(',')]
        
        if ip_addr not in whitelisted_ips:
            logger.warning(f"Unauthorized IP access for client {client.name}: {ip_addr}")
            return False

        # Store client on request for later use if needed
        request.api_client = client
        return True

    def get_client_ip(self, request):
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0].strip()
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip


