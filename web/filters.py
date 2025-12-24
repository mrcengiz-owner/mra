import django_filters
from django import forms
from django_filters import DateFromToRangeFilter
from finance.models import Transaction
from accounts.models import SubDealerProfile

class TransactionFilter(django_filters.FilterSet):
    created_at = DateFromToRangeFilter(
        widget=django_filters.widgets.RangeWidget(attrs={'type': 'date', 'class': 'form-control'})
    )
    transaction_type = django_filters.ChoiceFilter(
        choices=Transaction.TransactionType.choices,
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    status = django_filters.ChoiceFilter(
        choices=Transaction.Status.choices,
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    
    # SubDealer Filter: Customize queryset based on user manually in View or limit here if possible?
    # It is safer to limit choices in the View's __init__ or use a custom method, 
    # but for standard filters, we can define the field here.
    sub_dealer = django_filters.ModelChoiceFilter(
        queryset=SubDealerProfile.objects.all(),
        widget=forms.Select(attrs={'class': 'form-select select2'})
    )

    class Meta:
        model = Transaction
        fields = ['created_at', 'transaction_type', 'status', 'sub_dealer']

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        
        # Security: If user is SubDealer, hide or limit sub_dealer filter
        if user:
            try:
                # Check directly if profile exists by accessing it
                profile = user.profile
                self.filters['sub_dealer'].queryset = SubDealerProfile.objects.filter(id=profile.id)
                self.filters['sub_dealer'].widget.attrs['disabled'] = True 
                self.form.fields['sub_dealer'].required = False
            except Exception:
                # User has no profile (e.g. SuperAdmin), allow all options
                pass
