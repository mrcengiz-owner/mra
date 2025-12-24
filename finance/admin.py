from django.contrib import admin
from django.utils.html import format_html
from django.utils import timezone
from .models import BankAccount, Transaction, SystemConfig

@admin.register(SystemConfig)
class SystemConfigAdmin(admin.ModelAdmin):
    list_display = ('__str__', 'is_maintenance_mode', 'global_deposit_limit')
    list_editable = ('is_maintenance_mode', 'global_deposit_limit')

    def has_add_permission(self, request):
        return not SystemConfig.objects.exists()

@admin.register(BankAccount)
class BankAccountAdmin(admin.ModelAdmin):
    list_display = ('bank_name', 'iban', 'account_holder', 'sub_dealer', 'daily_limit', 'is_active')
    list_filter = ('bank_name', 'is_active')
    list_editable = ('is_active', 'daily_limit')
    search_fields = ('iban', 'account_holder', 'sub_dealer__user__username')
    
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs
        if hasattr(request.user, 'profile'):
            return qs.filter(sub_dealer=request.user.profile)
        return qs.none() 

    def get_readonly_fields(self, request, obj=None):
        if not request.user.is_superuser:
            return ('sub_dealer', 'daily_limit') # Dealers cannot change limit or owner
        return ()

    def save_model(self, request, obj, form, change):
        if not obj.pk and not request.user.is_superuser and hasattr(request.user, 'profile'):
            obj.sub_dealer = request.user.profile
        super().save_model(request, obj, form, change)

@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    list_display = (
        'id', 'sub_dealer', 'transaction_type', 'amount', 
        'status_colored', 'created_at', 'actions_buttons'
    )
    list_filter = ('status', 'transaction_type', 'created_at')
    search_fields = ('external_user_id', 'sub_dealer__user__username', 'id')
    readonly_fields = ('created_at', 'processed_at', 'amount', 'transaction_type', 'sub_dealer')
    actions = ['bulk_approve', 'bulk_reject']
    date_hierarchy = 'created_at'

    def status_colored(self, obj):
        colors = {
            'PENDING': 'orange',
            'APPROVED': 'green',
            'REJECTED': 'red',
        }
        color = colors.get(obj.status, 'gray')
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}</span>',
            color, obj.get_status_display()
        )
    status_colored.short_description = 'Status'

    def actions_buttons(self, obj):
        if obj.status == 'PENDING':
            return format_html(
                '<a class="button" style="background-color: green; color: white;" href="/transaction/{}/approve/">Approve</a>&nbsp;'
                '<a class="button" style="background-color: red; color: white;" href="/transaction/{}/reject/">Reject</a>',
                obj.id, obj.id
            )
        return "-"
    actions_buttons.short_description = 'Quick Actions'

    @admin.action(description="Bulk Approve Selected Transactions")
    def bulk_approve(self, request, queryset):
        count = 0
        for tx in queryset.filter(status='PENDING'):
            tx.status = 'APPROVED'
            tx.processed_at = timezone.now()
            tx.save() # Signal triggers balance update
            count += 1
        self.message_user(request, f"{count} transactions approved.")

    @admin.action(description="Bulk Reject Selected Transactions")
    def bulk_reject(self, request, queryset):
        count = queryset.filter(status='PENDING').update(status='REJECTED', processed_at=timezone.now())
        self.message_user(request, f"{count} transactions rejected.")

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs
        if hasattr(request.user, 'profile'):
            return qs.filter(sub_dealer=request.user.profile)
        return qs.none()
    
    def has_add_permission(self, request):
        return False # Only via API or Special Forms
