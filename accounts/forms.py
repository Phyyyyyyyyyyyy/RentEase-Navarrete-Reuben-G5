from django import forms
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm

from .models import User, gcash_number_validator


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
        fields = ('first_name', 'last_name', 'email', 'phone', 'profile_photo', 'gcash_name', 'gcash_number', 'gcash_qr')
        widgets = {
            'profile_photo': forms.ClearableFileInput(),
            'gcash_number': forms.TextInput(attrs={'inputmode': 'numeric', 'placeholder': '09171234567'}),
            'gcash_qr': forms.ClearableFileInput(),
        }

    GCASH_FIELDS = ('gcash_name', 'gcash_number', 'gcash_qr')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Only property owners receive rent, so only they set GCash details.
        if self.instance.role != User.Role.OWNER:
            for name in self.GCASH_FIELDS:
                del self.fields[name]
        else:
            # Accept "0917 123 4567" or "0917-123-4567": validate after removing spaces and dashes.
            number = self.fields['gcash_number']
            number.validators = []
            number.max_length = number.widget.attrs['maxlength'] = 15

    def clean_gcash_number(self):
        number = self.cleaned_data['gcash_number'].replace(' ', '').replace('-', '')
        if number:
            gcash_number_validator(number)
        return number

    def clean(self):
        cleaned = super().clean()
        if cleaned.get('gcash_number') and not (cleaned.get('gcash_name') or '').strip():
            self.add_error('gcash_name', 'Enter the name on your GCash account so tenants can check they are paying you.')
        return cleaned

    def clean_email(self):
        email = self.cleaned_data['email'].strip().lower()
        if User.objects.filter(email__iexact=email).exclude(pk=self.instance.pk).exists():
            raise forms.ValidationError('That email is already used by another account.')
        return email
