from rest_framework.authentication import SessionAuthentication

class CsrfExemptSessionAuthentication(SessionAuthentication):
    """
    Özel SessionAuthentication sınıfı. 
    API isteklerinde CSRF doğrulamasını devre dışı bırakır (enforce_csrf methodunu ezerek).
    Böylece 'CSRF cookie not set' hatası almadan POST isteği atılabilir.
    """
    def enforce_csrf(self, request):
        return  # CSRF kontrolünü atla (pass)
