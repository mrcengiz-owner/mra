from django.db import models
from accounts.models import SubDealerProfile

class BankAccount(models.Model):
    sub_dealer = models.ForeignKey(SubDealerProfile, on_delete=models.CASCADE, related_name='bank_accounts')
    bank_name = models.CharField(max_length=100)
    iban = models.CharField(max_length=34)
    account_holder = models.CharField(max_length=255)
    daily_limit = models.DecimalField(max_digits=12, decimal_places=2, help_text="Daily limit for this specific account")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.bank_name} - {self.iban} ({self.sub_dealer.user.username})"

class Transaction(models.Model):
    class TransactionType(models.TextChoices):
        DEPOSIT = 'DEPOSIT', 'Deposit'
        WITHDRAW = 'WITHDRAW', 'Withdraw'

    class Status(models.TextChoices):
        PENDING = 'PENDING', 'Pending'
        APPROVED = 'APPROVED', 'Approved'
        REJECTED = 'REJECTED', 'Rejected'

    sub_dealer = models.ForeignKey(SubDealerProfile, on_delete=models.CASCADE, related_name='transactions')
    bank_account = models.ForeignKey(BankAccount, on_delete=models.SET_NULL, null=True, blank=True, related_name='transactions')
    transaction_type = models.CharField(max_length=20, choices=TransactionType.choices)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    external_user_id = models.CharField(max_length=100, help_text="User ID from external system")
    created_at = models.DateTimeField(auto_now_add=True)
    processed_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"{self.transaction_type} - {self.amount} ({self.status})"
