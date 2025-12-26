from django.db import models
import uuid
from decimal import Decimal
from accounts.models import SubDealerProfile

class Blacklist(models.Model):
    class BlacklistType(models.TextChoices):
        IBAN = 'IBAN', 'IBAN'
        IP = 'IP', 'IP Address'
        USER_ID = 'USER_ID', 'User ID'

    type = models.CharField(max_length=20, choices=BlacklistType.choices)
    value = models.CharField(max_length=255, help_text="The blocked value (e.g., IBAN, IP, or User ID)")
    reason = models.TextField(blank=True, null=True, help_text="Reason for blocking")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.type}: {self.value}"

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

    @property
    def formatted_iban(self):
        """IBAN'ı 4'erli gruplar halinde gösterir"""
        if not self.iban: return ""
        clean_iban = self.iban.replace(" ", "")
        return " ".join(clean_iban[i:i+4] for i in range(0, len(clean_iban), 4))

    @property
    def bank_icon_class(self):
        """Banka adına göre ikon/renk sınıfı döndürür"""
        name = self.bank_name.lower()
        if 'ziraat' in name: return 'text-danger'
        if 'garanti' in name: return 'text-success'
        if 'yapı' in name and 'kredi' in name: return 'text-info'
        if 'akbank' in name: return 'text-danger'
        if 'iş' in name and 'bank' in name: return 'text-primary'
        if 'vakıf' in name: return 'text-warning'
        if 'finans' in name: return 'text-info'
        if 'papara' in name: return 'text-dark'
        return 'text-primary'

    @property
    def full_display_name(self):
        return f"{self.bank_name} - {self.account_holder}"

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

    class Category(models.TextChoices):
        TAKVIYE = 'TAKVIYE', 'Kasa Takviyesi'
        TESLIMAT = 'TESLIMAT', 'Elden Teslimat'
        MASRAF = 'MASRAF', 'Operasyonel Masraf'
        DUZELTME = 'DUZELTME', 'Hatalı İşlem Düzeltme'
        DIGER = 'DIGER', 'Diğer'

    category = models.CharField(max_length=20, choices=Category.choices, null=True, blank=True, verbose_name="Kategori")
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
    callback_url = models.URLField(max_length=500, null=True, blank=True, verbose_name="Callback URL", help_text="Notification URL for status updates")
    sender_full_name = models.CharField(max_length=255, null=True, blank=True, verbose_name="Gönderen Adı Soyadı")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Oluşturulma Tarihi")
    processed_at = models.DateTimeField(null=True, blank=True, verbose_name="İşlem Tarihi")
    processed_by = models.ForeignKey('accounts.CustomUser', on_delete=models.SET_NULL, null=True, blank=True, verbose_name="İşlem Yapan")
    rejection_reason = models.TextField(null=True, blank=True, verbose_name="Ret Sebebi")
    receipt_file = models.FileField(upload_to='receipts/%Y/%m/', null=True, blank=True, verbose_name="Dekont")
    processed_by_bank = models.ForeignKey(BankAccount, on_delete=models.SET_NULL, null=True, blank=True, related_name='processed_transactions', verbose_name="Ödenen Banka")

    def save(self, *args, **kwargs):
        # Auto-calculate commission for API Deposits if not manually set
        if self.transaction_type == self.TransactionType.DEPOSIT and not self.commission_amount and self.sub_dealer:
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
    allow_withdrawals = models.BooleanField(default=True, help_text="Global switch to enable/disable withdrawals.")
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
