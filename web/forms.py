from django import forms
from finance.models import SystemConfig, Transaction
from accounts.models import SubDealerProfile

class SystemConfigForm(forms.ModelForm):
    class Meta:
        model = SystemConfig
        fields = ['is_maintenance_mode', 'global_deposit_limit']
        widgets = {
            'is_maintenance_mode': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'global_deposit_limit': forms.NumberInput(attrs={'class': 'form-control'}),
        }

class ManualAdjustmentForm(forms.Form):
    dealer = forms.ModelChoiceField(
        queryset=SubDealerProfile.objects.all(),
        widget=forms.Select(attrs={'class': 'form-select select2'})
    )
    transaction_type = forms.ChoiceField(
        choices=[('MANUAL_CREDIT', 'Kasa Eklesi (+)'), ('MANUAL_DEBIT', 'Kasa Çıkışı (-)')],
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    amount = forms.DecimalField(
        max_digits=12, decimal_places=2,
        widget=forms.NumberInput(attrs={'class': 'form-control', 'placeholder': '0.00'})
    )
    commission_rate = forms.DecimalField(
        max_digits=5, decimal_places=2, initial=0.00,
        widget=forms.NumberInput(attrs={'class': 'form-control', 'placeholder': '0.00'})
    )
    description = forms.CharField(
        widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Reason for adjustment...'})
    )
