from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _
from .models import CustomUser, SubDealerProfile, APIClient, AuditLog

@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ('user', 'action', 'target_model', 'ip_address', 'created_at')
    list_filter = ('action', 'target_model', 'created_at')
    search_fields = ('user__username', 'action', 'details', 'ip_address')
    readonly_fields = [f.name for f in AuditLog._meta.fields]
    
    def has_add_permission(self, request): return False
    def has_change_permission(self, request, obj=None): return False
    def has_delete_permission(self, request, obj=None): return False

@admin.register(APIClient)
class APIClientAdmin(admin.ModelAdmin):
    list_display = ('name', 'api_key', 'is_active', 'created_at')
    list_filter = ('is_active',)
    search_fields = ('name', 'api_key')
    readonly_fields = ('api_key', 'created_at')
    fieldsets = (
        (None, {
            'fields': ('name', 'api_key', 'is_active')
        }),
        ('Security', {
            'fields': ('allowed_ips',),
            'description': "Virgülle ayrılmış IP adresleri (Örn: 127.0.0.1, 85.10.20.30)"
        }),
        ('Metadata', {
            'fields': ('created_at',),
            'classes': ('collapse',)
        }),
    )
from decimal import Decimal

@admin.register(CustomUser)
class CustomUserAdmin(UserAdmin):
    list_display = ('username', 'email', 'role', 'is_staff')
    list_filter = ('role', 'is_staff')
    fieldsets = UserAdmin.fieldsets + (
        ('Role Info', {'fields': ('role',)}),
    )

@admin.register(SubDealerProfile)
class SubDealerProfileAdmin(admin.ModelAdmin):
    list_display = (
        'user_link', 'colored_net_balance', 'net_balance_limit', 
        'usage_progress_bar', 'is_active_by_system', 'commission_rate', 'actions_buttons'
    )
    list_editable = ('commission_rate',)
    search_fields = ('user__username', 'user__email', 'api_key')
    list_filter = ('is_active_by_system',)
    readonly_fields = ('current_net_balance', 'api_key')
    actions = ['reset_balance_cache']

    def user_link(self, obj):
        return obj.user.username
    user_link.short_description = 'User'

    def colored_net_balance(self, obj):
        color = 'green' if obj.current_net_balance >= 0 else 'red'
        return format_html(
            '<span style="color: {}; font-weight: bold;">{} TL</span>',
            color, obj.current_net_balance
        )
    colored_net_balance.short_description = 'Net Balance'

    def usage_progress_bar(self, obj):
        if obj.net_balance_limit <= 0:
            return "No Limit"
        percent = (obj.current_net_balance / obj.net_balance_limit) * Decimal('100.00')
        percent = min(percent, Decimal('100.00')) # Cap at 100 for visual
        
        color = 'bg-success'
        if percent > 80: color = 'bg-warning'
        if percent > 95: color = 'bg-danger'
        
        formatted_percent = "{:.1f}".format(percent)
        
        return format_html(
            '''
            <div style="width: 100px; background-color: #444; border-radius: 4px;">
                <div class="{}" style="width: {}%; height: 10px; border-radius: 4px;"></div>
            </div>
            <div style="font-size: 10px; text-align: center;">{}%</div>
            ''',
            color, percent, formatted_percent
        )
    usage_progress_bar.short_description = 'Limit Usage'

    def actions_buttons(self, obj):
        return format_html(
            '<a class="button" href="/admin/finance/transaction/?sub_dealer__id__exact={}">History</a>',
            obj.id
        )
    actions_buttons.short_description = 'Quick Actions'

    @admin.action(description="Reset Balance Cache (Recalculate)")
    def reset_balance_cache(self, request, queryset):
        for profile in queryset:
            profile.recalculate_balance()
        self.message_user(request, f"{queryset.count()} profiles updated.")
