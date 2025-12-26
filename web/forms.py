from django import forms
from finance.models import SystemConfig, Transaction, BankAccount
from accounts.models import SubDealerProfile
import os

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
        label="Saha / Alt Bayi Seçiniz",
        widget=forms.Select(attrs={'class': 'form-select select2'})
    )
    transaction_type = forms.ChoiceField(
        choices=[('MANUAL_CREDIT', 'Kasa Girişi (+)'), ('MANUAL_DEBIT', 'Kasa Çıkışı (-)')],
        label="İşlem Yönü",
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    category = forms.ChoiceField(
        choices=Transaction.Category.choices,
        label="İşlem Sebebi (Kategori)",
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    amount = forms.DecimalField(
        max_digits=12, decimal_places=2,
        label="İşlem Tutarı (₺)",
        widget=forms.NumberInput(attrs={'class': 'form-control', 'placeholder': '0.00'})
    )
    # Commission removed as usually net adjustment is preferred, but user didn't ask to remove it,
    # however description is Mandatory.
    # User didn't ask for commission rate in the new structure, so I'll keep it optional/hidden or remove if not needed.
    # The prompt explicitly listed fields: Dealer, Direction, Category, Amount, Description. Commission is NOT in the list.
    # I will remove commission_rate to fit the spec exactly.
    
    description = forms.CharField(
        label="Detaylı Açıklama (Zorunlu)",
        widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'İşlem nedenini detaylıca belirtiniz...'})
    )

class WithdrawalApprovalForm(forms.ModelForm):
    class Meta:
        model = Transaction
        fields = ['processed_by_bank', 'receipt_file']
        
    processed_by_bank = forms.ModelChoiceField(
        queryset=BankAccount.objects.filter(is_active=True),
        widget=forms.Select(attrs={'class': 'form-select'}),
        label="Paranın Çıktığı Banka"
    )
    
    receipt_file = forms.FileField(
        widget=forms.FileInput(attrs={'class': 'form-control', 'accept': '.pdf,.jpg,.jpeg,.png'}),
        label="Dekont (PDF/Resim)",
        required=True
    )

    def clean_receipt_file(self):
        file = self.cleaned_data.get('receipt_file')
        if file:
            ext = os.path.splitext(file.name)[1].lower()
            valid_extensions = ['.pdf', '.jpg', '.jpeg', '.png']
            if ext not in valid_extensions:
                raise forms.ValidationError("Sadece PDF ve Resim dosyaları kabul edilir.")
            if file.size > 5 * 1024 * 1024:
                raise forms.ValidationError("Dosya boyutu 5MB'ı geçemez.")
        return file
