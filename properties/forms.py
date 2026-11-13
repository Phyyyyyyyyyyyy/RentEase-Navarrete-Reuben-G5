from django import forms
from django.utils import timezone

from .models import Application, Property, Unit


class BrowseFilterForm(forms.Form):
    q = forms.CharField(required=False, widget=forms.TextInput(attrs={'placeholder': 'Search by name, address, or city'}))
    type = forms.ChoiceField(required=False, choices=[('', 'All types'), *Property.Type.choices])
    max_rent = forms.IntegerField(required=False, min_value=0, widget=forms.NumberInput(attrs={'placeholder': 'Max rent (₱)'}))


class ApplicationForm(forms.ModelForm):
    unit = forms.ModelChoiceField(queryset=Unit.objects.none(), widget=forms.RadioSelect, empty_label=None,
                                  error_messages={'required': 'Please choose a vacant unit.'})

    class Meta:
        model = Application
        fields = ('unit', 'preferred_move_in', 'message')
        widgets = {
            'preferred_move_in': forms.DateInput(attrs={'type': 'date'}),
            'message': forms.Textarea(attrs={'rows': 4, 'placeholder': 'Introduce yourself and mention when you can move in.'}),
        }
        labels = {'message': 'Message to the owner'}

    def __init__(self, *args, property_obj, tenant, **kwargs):
        super().__init__(*args, **kwargs)
        self.tenant = tenant
        self.fields['unit'].queryset = property_obj.units.filter(status=Unit.Status.VACANT)

    def clean_preferred_move_in(self):
        date = self.cleaned_data.get('preferred_move_in')
        if date and date < timezone.localdate():
            raise forms.ValidationError('Move-in date cannot be in the past.')
        return date

    def clean(self):
        cleaned = super().clean()
        unit = cleaned.get('unit')
        if unit and Application.objects.filter(tenant=self.tenant, unit=unit, status=Application.Status.PENDING).exists():
            raise forms.ValidationError('You already have a pending application for this unit.')
        return cleaned
