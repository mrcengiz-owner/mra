from django import forms
from django.contrib.auth.forms import UserCreationForm, UserChangeForm
from .models import CustomUser

class CustomUserCreationForm(UserCreationForm):
    password_1 = forms.CharField(
        label="Parola",
        widget=forms.PasswordInput,
        strip=False,
        help_text="Parolanız en az 8 karakter olmalıdır. Tamamen sayısal olamaz.",
    )
    password_2 = forms.CharField(
        label="Parola (Tekrar)",
        widget=forms.PasswordInput,
        strip=False,
        help_text="Onay için parolayı tekrar girin.",
    )

    class Meta:
        model = CustomUser
        # We must include all fields from UserCreationForm (username) + our custom field (role, email)
        # Note: password_1/2 are form fields, NOT model fields, so they should NOT be in Meta.fields
        fields = ('username', 'email', 'role')

class CustomUserChangeForm(UserChangeForm):
    class Meta:
        model = CustomUser
        fields = '__all__'
