from django.db import models
from django.contrib.auth.models import AbstractUser
from django.db.models import Sum, F, Case, When, DecimalField
from decimal import Decimal
import uuid
import logging

logger = logging.getLogger(__name__)

class CustomUser(AbstractUser):
    class Roles(models.TextChoices):
        SUPERADMIN = 'SUPERADMIN', 'Super Admin'
        ADMIN = 'ADMIN', 'Admin'
        SUBDEALER = 'SUBDEALER', 'Alt Bayi'

    role = models.CharField(max_length=20, choices=Roles.choices, default=Roles.SUBDEALER)

    def is_subdealer(self):
        return self.role == self.Roles.SUBDEALER and not self.is_superuser
    
    def is_superadmin(self):
        return self.role == self.Roles.SUPERADMIN or self.is_superuser

class SubDealerProfile(models.Model):
    user = models.OneToOneField(CustomUser, on_delete=models.CASCADE, related_name='profile')
    commission_rate = models.DecimalField(max_digits=5, decimal_places=2, default=0.00, help_text="Percentage commission, e.g. 2.50")
    net_balance_limit = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    current_net_balance = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    is_active_by_system = models.BooleanField(default=True, help_text="Automatically set to False if limit is reached")
    can_edit_amounts = models.BooleanField(default=False, verbose_name="Miktar Düzenleyebilir mi?")
    api_key = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)

    class Meta:
        verbose_name = "Alt Bayi"
        verbose_name_plural = "Alt Bayiler (Sahalar)"

    def __str__(self):
        return f"{self.user.username} - Balance: {self.current_net_balance}/{self.net_balance_limit}"

    def recalculate_balance(self):
        """
        Calculates Net Balance and updates System Status.
        Net Balance = (Total Approved Deposits) - (Total Approved Withdrawals) - (Total Commission)
        """
        # Avoid circular import by importing inside method if needed, or rely on reverse relation
        # We can use self.transactions.all()
        from finance.models import Transaction

        approved_txs = self.transactions.filter(status=Transaction.Status.APPROVED)

        totals = approved_txs.aggregate(
            total_deposits=Sum(
                Case(
                    When(transaction_type='DEPOSIT', then=F('amount')),
                    default=0,
                    output_field=DecimalField()
                )
            ),
            total_withdrawals=Sum(
                Case(
                    When(transaction_type='WITHDRAW', then=F('amount')),
                    default=0,
                    output_field=DecimalField()
                )
            ),
            total_manual_credits=Sum(
                Case(
                    When(transaction_type='MANUAL_CREDIT', then=F('amount')),
                    default=0,
                    output_field=DecimalField()
                )
            ),
            total_manual_debits=Sum(
                Case(
                    When(transaction_type='MANUAL_DEBIT', then=F('amount')),
                    default=0,
                    output_field=DecimalField()
                )
            ),
            total_commission=Sum('commission_amount'),
            # Legacy Manual support
            total_manual=Sum(
                Case(
                    When(transaction_type='MANUAL', then=F('amount')),
                    default=0,
                    output_field=DecimalField()
                )
            )
        )

        total_deposits = totals['total_deposits'] or Decimal('0.00')
        total_withdrawals = totals['total_withdrawals'] or Decimal('0.00')
        total_manual_credits = totals['total_manual_credits'] or Decimal('0.00')
        total_manual_debits = totals['total_manual_debits'] or Decimal('0.00')
        total_legacy_manual = totals['total_manual'] or Decimal('0.00')
        total_commission = totals['total_commission'] or Decimal('0.00')

        # New Balance Calculation:
        # Credits (In): Deposits + Manual Credits + Legacy Manual
        # Debits (Out): Withdrawals + Manual Debits
        # Commissions (System Fee): Deducted from total
        new_balance = (total_deposits + total_manual_credits + total_legacy_manual) - (total_withdrawals + total_manual_debits + total_commission)
        self.current_net_balance = new_balance

        # Auto-Passive Logic
        if new_balance >= self.net_balance_limit:
            if self.is_active_by_system:
                self.is_active_by_system = False
                logger.warning(f"SubDealer {self.user.username} REACHED LIMIT ({new_balance}). Set to PASSIVE.")
        
        # Optional: Auto-Active (Commented out per safely)
        # elif not self.is_active_by_system and new_balance < self.net_balance_limit:
        #     self.is_active_by_system = True

        self.save()
        return new_balance

class APIClient(models.Model):
    name = models.CharField(max_length=100, verbose_name="Müşteri Adı")
    api_key = models.CharField(max_length=64, unique=True, blank=True, verbose_name="API Key")
    allowed_ips = models.TextField(default="127.0.0.1", help_text="Virgülle ayrılmış IP listesi", verbose_name="İzinli IP'ler")
    is_active = models.BooleanField(default=True, verbose_name="Aktif mi?")
    created_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        if not self.api_key:
            import secrets
            self.api_key = secrets.token_hex(32) # Generate 64 char hex string
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = "API İstemcisi"
        verbose_name_plural = "API İstemcileri"

class AuditLog(models.Model):
    user = models.ForeignKey(CustomUser, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Kullanıcı")
    action = models.CharField(max_length=100, verbose_name="İşlem")
    target_model = models.CharField(max_length=100, null=True, blank=True, verbose_name="Hedef Tablo")
    target_object_id = models.CharField(max_length=100, null=True, blank=True, verbose_name="Hedef ID")
    ip_address = models.GenericIPAddressField(null=True, blank=True, verbose_name="IP Adresi")
    user_agent = models.CharField(max_length=500, null=True, blank=True, verbose_name="Cihaz Bilgisi")
    details = models.JSONField(default=dict, verbose_name="Detaylar")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Tarih")

    class Meta:
        ordering = ['-created_at']
        verbose_name = "Denetim Kaydı"
        verbose_name_plural = "Denetim Kayıtları"

    def __str__(self):
        return f"{self.user} - {self.action} ({self.created_at})"
