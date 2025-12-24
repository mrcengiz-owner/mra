from django.db import models
from django.contrib.auth.models import AbstractUser
import uuid

class CustomUser(AbstractUser):
    class Roles(models.TextChoices):
        SUPERADMIN = 'SUPERADMIN', 'Super Admin'
        ADMIN = 'ADMIN', 'Admin'
        SUBDEALER = 'SUBDEALER', 'Sub Dealer'

    role = models.CharField(max_length=20, choices=Roles.choices, default=Roles.SUBDEALER)

    def is_subdealer(self):
        return self.role == self.Roles.SUBDEALER
    
    def is_superadmin(self):
        return self.role == self.Roles.SUPERADMIN

class SubDealerProfile(models.Model):
    user = models.OneToOneField(CustomUser, on_delete=models.CASCADE, related_name='profile')
    commission_rate = models.DecimalField(max_digits=5, decimal_places=2, default=0.00, help_text="Percentage commission, e.g. 2.50")
    net_balance_limit = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    current_net_balance = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    is_active_by_system = models.BooleanField(default=True, help_text="Automatically set to False if limit is reached")
    api_key = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)

    def __str__(self):
        return f"{self.user.username} - Balance: {self.current_net_balance}/{self.net_balance_limit}"

    def update_balance(self, amount):
        """Helper to update balance manually if needed, though signals handle transactions."""
        self.current_net_balance += amount
        self.save()
