from django import forms
from django.utils import timezone

from .models import Application, Property, Unit


class BrowseFilterForm(forms.Form):
    q = forms.CharField(required=False, widget=forms.TextInput(attrs={'placeholder': 'Search by name, address, or city'}))
    type = forms.ChoiceField(required=False, choices=[('', 'All types'), *Property.Type.choices])
    max_rent = forms.IntegerField(required=False, min_value=0, widget=forms.NumberInput(attrs={'placeholder': 'Max rent (₱)'}))


class MoveInDateMixin:
    def clean_preferred_move_in(self):
        date = self.cleaned_data.get('preferred_move_in')
        if date and date < timezone.localdate():
            raise forms.ValidationError('Move-in date cannot be in the past.')
        return date


class ApplicationEditForm(MoveInDateMixin, forms.ModelForm):
    """Lets a tenant change the move-in date and message of a pending application.

    The unit can't be changed: to apply for a different unit, withdraw and apply again.
    """

    class Meta:
        model = Application
        fields = ('preferred_move_in', 'message')
        widgets = {
            'preferred_move_in': forms.DateInput(attrs={'type': 'date'}, format='%Y-%m-%d'),
            'message': forms.Textarea(attrs={'rows': 5}),
        }
        labels = {'message': 'Message to the owner'}


class ApplicationForm(MoveInDateMixin, forms.ModelForm):
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

    def clean(self):
        cleaned = super().clean()
        unit = cleaned.get('unit')
        if unit and Application.objects.filter(tenant=self.tenant, unit=unit, status=Application.Status.PENDING).exists():
            raise forms.ValidationError('You already have a pending application for this unit.')
        return cleaned


class PropertyForm(forms.ModelForm):
    class Meta:
        model = Property
        fields = ('name', 'property_type', 'address', 'city', 'description', 'amenities')
        widgets = {
            'name': forms.TextInput(attrs={'placeholder': 'e.g. Lahug Apartments'}),
            'address': forms.TextInput(attrs={'placeholder': 'Street, barangay'}),
            'city': forms.TextInput(attrs={'placeholder': 'e.g. Cebu City'}),
            'description': forms.Textarea(attrs={'rows': 4, 'placeholder': 'What makes this place a good home?'}),
            'amenities': forms.TextInput(attrs={'placeholder': 'Wi-Fi, Parking, CCTV'}),
        }
        help_texts = {'amenities': 'Separate amenities with commas.'}

    def __init__(self, *args, owner, **kwargs):
        super().__init__(*args, **kwargs)
        self.owner = owner

    def clean(self):
        # The database constraint is case-insensitive; check here too for a friendly error.
        cleaned = super().clean()
        for field in ('name', 'address', 'city'):
            if cleaned.get(field):
                cleaned[field] = cleaned[field].strip()
        name, address, city = cleaned.get('name'), cleaned.get('address'), cleaned.get('city')
        if name and address and city:
            clash = (Property.objects.filter(owner=self.owner, name__iexact=name, address__iexact=address,
                                             city__iexact=city)
                     .exclude(pk=self.instance.pk))
            if clash.exists():
                raise forms.ValidationError('You already have a property with this name at this address.')
        return cleaned


class UnitForm(forms.ModelForm):
    class Meta:
        model = Unit
        fields = ('name', 'bedrooms', 'bathrooms', 'floor_area', 'monthly_rent', 'status')
        widgets = {
            'name': forms.TextInput(attrs={'placeholder': 'e.g. Unit 101'}),
            'monthly_rent': forms.NumberInput(attrs={'min': 0, 'step': '0.01', 'placeholder': '8500'}),
        }
        labels = {'monthly_rent': 'Monthly rent (₱)', 'bedrooms': 'Bedrooms (0 = studio)'}

    def __init__(self, *args, property_obj, **kwargs):
        super().__init__(*args, **kwargs)
        self.property_obj = property_obj

    def clean_name(self):
        # The (property, name) unique constraint isn't checked by the form because
        # `property` isn't a form field, so check it here for a friendly error.
        name = self.cleaned_data['name'].strip()
        clash = self.property_obj.units.filter(name__iexact=name).exclude(pk=self.instance.pk)
        if clash.exists():
            raise forms.ValidationError('This property already has a unit with that name.')
        return name

    def clean_monthly_rent(self):
        rent = self.cleaned_data['monthly_rent']
        if rent is not None and rent <= 0:
            raise forms.ValidationError('Monthly rent must be greater than zero.')
        return rent
