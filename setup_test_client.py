from accounts.models import APIClient

# Test Client oluştur veya getir
client, created = APIClient.objects.get_or_create(name='PostmanTest')
client.api_key = 'test-secret-key-123'
client.allowed_ips = '127.0.0.1, ::1'
client.is_active = True
client.save()

print("\n" + "="*40)
print("TEST API CLIENT HAZIR!")
print("="*40)
print(f"X-API-KEY: {client.api_key}")
print(f"IP Whitelist: {client.allowed_ips}")
print("="*40 + "\n")
