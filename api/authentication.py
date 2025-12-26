from rest_framework.authentication import BaseAuthentication
from rest_framework.exceptions import AuthenticationFailed
from django.conf import settings
from django.contrib.auth.models import AnonymousUser

class ApiKeyAuthentication(BaseAuthentication):
    """
    Custom Authentication class for API Key.
    Reads 'X-API-KEY' from the header.
    Validates against settings.MY_SECRET_API_KEY.
    """
    def authenticate(self, request):
        api_key = request.META.get('HTTP_X_API_KEY')
        if not api_key:
            return None  # No API Key provided

        # Validate against Static Key from settings
        if api_key == getattr(settings, 'MY_SECRET_API_KEY', None):
             # Successful Auth
             # Return AnonymousUser (so manual login isn't triggered) 
             # and the api_key as the 'auth' object
             return (AnonymousUser(), api_key)
        
        # If key is present but wrong
        raise AuthenticationFailed('Invalid API Key')
