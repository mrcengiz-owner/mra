from django.db import models

class Blacklist(models.Model):
    class BlacklistType(models.TextChoices):
        IBAN = 'IBAN', 'IBAN'
        IP = 'IP', 'IP Address'
        USER_ID = 'USER_ID', 'User ID'

    type = models.CharField(max_length=20, choices=BlacklistType.choices)
    value = models.CharField(max_length=255, help_text="The blocked value (e.g., IBAN, IP, or User ID)")
    reason = models.TextField(blank=True, null=True, help_text="Reason for blocking")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.type}: {self.value}"
