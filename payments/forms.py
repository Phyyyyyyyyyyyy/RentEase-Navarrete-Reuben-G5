from django import forms
from django.utils import timezone

from .models import Payment, gcash_reference_validator

MAX_PROOF_BYTES = 5 * 1024 * 1024


class _PaymentForm(forms.ModelForm):
    def clean_paid_on(self):
        paid_on = self.cleaned_data['paid_on']
        if paid_on > timezone.localdate():
            raise forms.ValidationError('The payment date cannot be in the future.')
        return paid_on


class GCashPaymentForm(_PaymentForm):
    """Tenant: report a GCash transfer they made to the owner's number."""

    reference_number = forms.CharField(
        label='GCash reference number', max_length=20, validators=[gcash_reference_validator],
        widget=forms.TextInput(attrs={'inputmode': 'numeric', 'autocomplete': 'off', 'placeholder': '13 digits'}),
    )

    class Meta:
        model = Payment
        fields = ('amount', 'reference_number', 'paid_on', 'proof', 'note')
        labels = {'amount': 'Amount sent (₱)', 'paid_on': 'Date sent', 'note': 'Note for the owner'}
        widgets = {
            'amount': forms.NumberInput(attrs={'step': '0.01', 'min': '1'}),
            'paid_on': forms.DateInput(attrs={'type': 'date'}, format='%Y-%m-%d'),
            'proof': forms.ClearableFileInput(attrs={'accept': 'image/*'}),
        }

    def clean_reference_number(self):
        ref = self.cleaned_data['reference_number'].replace(' ', '')
        gcash_reference_validator(ref)
        taken = Payment.objects.filter(method=Payment.Method.GCASH, reference_number=ref).exclude(
            status=Payment.Status.REJECTED)
        if taken.exists():
            raise forms.ValidationError('This reference number has already been submitted.')
        return ref

    def clean_proof(self):
        proof = self.cleaned_data.get('proof')
        if proof and proof.size > MAX_PROOF_BYTES:
            raise forms.ValidationError('The screenshot must be 5 MB or smaller.')
        return proof


class RecordPaymentForm(_PaymentForm):
    """Owner: record money received in person, upfront, or any other way. Counts immediately."""

    class Meta:
        model = Payment
        fields = ('amount', 'method', 'paid_on', 'reference_number', 'note')
        labels = {'amount': 'Amount received (₱)', 'paid_on': 'Date received',
                  'reference_number': 'Reference / receipt no.'}
        widgets = {
            'amount': forms.NumberInput(attrs={'step': '0.01', 'min': '1'}),
            'paid_on': forms.DateInput(attrs={'type': 'date'}, format='%Y-%m-%d'),
            'note': forms.TextInput(attrs={'placeholder': 'e.g. Paid 3 months upfront'}),
        }

    def clean(self):
        cleaned = super().clean()
        ref = (cleaned.get('reference_number') or '').strip()
        cleaned['reference_number'] = ref
        if cleaned.get('method') == Payment.Method.GCASH and ref:
            if Payment.objects.filter(method=Payment.Method.GCASH, reference_number=ref).exclude(
                    status=Payment.Status.REJECTED).exists():
                self.add_error('reference_number', 'This GCash reference number is already recorded.')
        return cleaned


class RejectPaymentForm(forms.Form):
    reason = forms.CharField(max_length=255, required=False)
