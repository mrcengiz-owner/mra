from rest_framework.authentication import BaseAuthentication
from rest_framework.exceptions import AuthenticationFailed
from accounts.models import APIClient
from django.contrib.auth.models import AnonymousUser

class ApiKeyAuthentication(BaseAuthentication):
    """
    Database-backed API Key Authentication.
    Reads 'X-API-KEY' from header.
    Validates against accounts.models.APIClient.
    """
    def authenticate(self, request):
        api_key = request.META.get('HTTP_X_API_KEY')
        if not api_key:
            return None  # Pass to next auth class (if any)

        try:
            # Query the database for the key
            client = APIClient.objects.get(api_key=api_key, is_active=True)
        except APIClient.DoesNotExist:
            raise AuthenticationFailed('Invalid API Key')
        
        # Return AnonymousUser as user, and client object as auth
        return (AnonymousUser(), client)
