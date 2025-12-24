from django.db import models
import uuid
from decimal import Decimal
from accounts.models import SubDealerProfile

class BankAccount(models.Model):
    sub_dealer = models.ForeignKey(SubDealerProfile, on_delete=models.CASCADE, related_name='bank_accounts')
    bank_name = models.CharField(max_length=100)
    iban = models.CharField(max_length=34)
    account_holder = models.CharField(max_length=255)
    daily_limit = models.DecimalField(max_digits=12, decimal_places=2, help_text="Daily limit for this specific account")
    min_deposit_limit = models.DecimalField(max_digits=12, decimal_places=2, default=100.00, help_text="Minimum deposit amount")
    max_deposit_limit = models.DecimalField(max_digits=12, decimal_places=2, default=50000.00, help_text="Maximum deposit amount")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.bank_name} - {self.iban} ({self.sub_dealer.user.username})"

class Transaction(models.Model):
    class TransactionType(models.TextChoices):
        DEPOSIT = 'DEPOSIT', 'Yatırım'

        WITHDRAW = 'WITHDRAW', 'Çekim'
        MANUAL_CREDIT = 'MANUAL_CREDIT', 'Manuel Ekleme (+)'
        MANUAL_DEBIT = 'MANUAL_DEBIT', 'Manuel Kesinti (-)'
        # Deprecated: MANUAL
        MANUAL = 'MANUAL', 'Manuel (Eski)'

    class Status(models.TextChoices):
        WAITING_ASSIGNMENT = 'WAITING_ASSIGNMENT', 'Atama Bekliyor'
        PENDING = 'PENDING', 'Bekliyor'
        APPROVED = 'APPROVED', 'Onaylandı'
        REJECTED = 'REJECTED', 'Reddedildi'

    class Meta:
        verbose_name = "İşlem"
        verbose_name_plural = "İşlemler"

    token = models.UUIDField(default=uuid.uuid4, editable=False, unique=True, null=True)
    sub_dealer = models.ForeignKey(SubDealerProfile, on_delete=models.CASCADE, related_name='transactions', verbose_name="Alt Bayi", null=True, blank=True)
    bank_account = models.ForeignKey(BankAccount, on_delete=models.SET_NULL, null=True, blank=True, related_name='transactions', verbose_name="Banka Hesabı")
    transaction_type = models.CharField(max_length=20, choices=TransactionType.choices, verbose_name="İşlem Tipi")
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING, verbose_name="Durum")
    amount = models.DecimalField(max_digits=12, decimal_places=2, verbose_name="Miktar")
    commission_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0.00, verbose_name="Komisyon Tutarı")
    description = models.TextField(null=True, blank=True, help_text="Admin notes for this transaction", verbose_name="Açıklama")
    target_iban = models.CharField(max_length=34, null=True, blank=True, help_text="Target IBAN for withdrawals", verbose_name="Hedef IBAN")
    target_name = models.CharField(max_length=255, null=True, blank=True, help_text="Target Account Holder Name", verbose_name="Hedef Ad Soyad")
    external_user_id = models.CharField(max_length=100, help_text="User ID from external system", verbose_name="Harici Kullanıcı ID")
    sender_full_name = models.CharField(max_length=255, null=True, blank=True, verbose_name="Gönderen Adı Soyadı")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Oluşturulma Tarihi")
    processed_at = models.DateTimeField(null=True, blank=True, verbose_name="İşlem Tarihi")
    processed_by = models.ForeignKey('accounts.CustomUser', on_delete=models.SET_NULL, null=True, blank=True, verbose_name="İşlem Yapan")
    rejection_reason = models.TextField(null=True, blank=True, verbose_name="Ret Sebebi")

    def save(self, *args, **kwargs):
        # Auto-calculate commission for API Deposits if not manually set
        if self.transaction_type == self.TransactionType.DEPOSIT and not self.commission_amount:
            # We use the current rate from sub_dealer
            self.commission_amount = self.amount * (self.sub_dealer.commission_rate / Decimal('100.00'))
        super().save(*args, **kwargs)

    @property
    def net_amount(self):
        if self.transaction_type in [self.TransactionType.DEPOSIT, self.TransactionType.MANUAL_CREDIT]:
            return self.amount - self.commission_amount
        return self.amount


    def __str__(self):
        return f"{self.transaction_type} - {self.amount} ({self.status})"

class SystemConfig(models.Model):
    is_maintenance_mode = models.BooleanField(default=False, help_text="If Active, no new transactions can be created via API.")
    global_deposit_limit = models.DecimalField(max_digits=12, decimal_places=2, default=100000.00, help_text="Global limit for daily deposits.")

    def save(self, *args, **kwargs):
        # Ensure only one instance
        if not self.pk and SystemConfig.objects.exists():
            return SystemConfig.objects.first()
        return super(SystemConfig, self).save(*args, **kwargs)

    @classmethod
    def get_solo(cls):
        obj, created = cls.objects.get_or_create(id=1)
        return obj

    def __str__(self):
        return "System Configuration"
