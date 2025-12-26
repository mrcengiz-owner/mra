from rest_framework.authentication import BaseAuthentication
from rest_framework.exceptions import AuthenticationFailed
from accounts.models import APIClient
from django.contrib.auth.models import AnonymousUser

class ApiKeyAuthentication(BaseAuthentication):
    """
    Custom Authentication class for API Key.
    Reads 'X-API-KEY' from the header.
    Validates against APIClient model.
    """
    def authenticate(self, request):
        api_key = request.META.get('HTTP_X_API_KEY')
        if not api_key:
            return None  # No API Key provided, move to next auth class or fail if perm requires it

        try:
            client = APIClient.objects.get(api_key=api_key, is_active=True)
        except APIClient.DoesNotExist:
            raise AuthenticationFailed('Invalid API Key')

        # Since APIClient is not a Django User, we return AnonymousUser as the user
        # and the client object as the 'auth' context.
        # This prevents 403 "Authentication credentials were not provided" if permissions need named user.
        # But for IsAuthenticatedClient permission, this is sufficient.
        return (AnonymousUser(), client)
