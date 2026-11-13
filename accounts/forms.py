from django import forms
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm

from .models import User


class RegistrationForm(UserCreationForm):
    first_name = forms.CharField(max_length=150, required=True)
    last_name = forms.CharField(max_length=150, required=True)
    email = forms.EmailField(required=True)
    phone = forms.CharField(label='Contact number', max_length=20, required=True)
    role = forms.ChoiceField(
        label='Account type',
        choices=[(r.value, r.label) for r in User.SELF_REGISTER_ROLES],
    )

    class Meta(UserCreationForm.Meta):
        model = User
        fields = ('first_name', 'last_name', 'username', 'email', 'phone', 'role')

    def clean_email(self):
        email = self.cleaned_data['email'].strip().lower()
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError('An account with this email already exists.')
        return email

    def clean_username(self):
        username = super().clean_username()
        if User.objects.filter(username__iexact=username).exists():
            raise forms.ValidationError('This username is already taken.')
        return username


class LoginForm(AuthenticationForm):
    username = forms.CharField(
        label='Username or email',
        widget=forms.TextInput(attrs={'autofocus': True, 'placeholder': 'username or name@example.com'}),
    )
    password = forms.CharField(
        label='Password', strip=False,
        widget=forms.PasswordInput(attrs={'placeholder': 'Enter your password'}),
    )
    error_messages = {
        'invalid_login': 'Invalid username/email or password. Please try again.',
        'inactive': 'This account is inactive. Contact an administrator.',
    }


class ProfileForm(forms.ModelForm):
    first_name = forms.CharField(max_length=150, required=True)
    last_name = forms.CharField(max_length=150, required=True)
    email = forms.EmailField(required=True)

    class Meta:
        model = User
        fields = ('first_name', 'last_name', 'email', 'phone', 'profile_photo')
        widgets = {'profile_photo': forms.ClearableFileInput()}

    def clean_email(self):
        email = self.cleaned_data['email'].strip().lower()
        if User.objects.filter(email__iexact=email).exclude(pk=self.instance.pk).exists():
            raise forms.ValidationError('That email is already used by another account.')
        return email
