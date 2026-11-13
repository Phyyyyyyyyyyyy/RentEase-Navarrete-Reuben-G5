from django.core.management import call_command
from django.core.management.base import BaseCommand
from django.db import transaction

from accounts.models import User
from properties.models import Application, Property, Unit

V, O = Unit.Status.VACANT, Unit.Status.OCCUPIED

# Same sample data as the original React prototype (src/data/seed.js).
DEMO_PROPERTIES = [
    {
        'name': 'Cebu City Residences', 'property_type': Property.Type.APARTMENT,
        'address': 'Salinas Drive, Lahug', 'city': 'Cebu City',
        'description': 'Accessible apartment property near schools, offices, and public transportation.',
        'amenities': 'Wi-Fi Ready, Parking, CCTV',
        'units': [('Unit 101', 1, 1, 28, 8500, V), ('Unit 102', 1, 1, 28, 8500, O), ('Unit 201', 2, 1, 40, 12000, V)],
    },
    {
        'name': 'Banilad Townhomes', 'property_type': Property.Type.TOWNHOUSE,
        'address': 'Gov. M. Cuenco Avenue, Banilad', 'city': 'Cebu City',
        'description': 'Quiet residential units with practical access to commercial areas and transport routes.',
        'amenities': 'Parking, Pet Friendly, Water Included',
        'units': [('Townhome A', 2, 2, 68, 18000, V), ('Townhome B', 2, 2, 70, 18500, V)],
    },
    {
        'name': 'Mabolo Studio Hub', 'property_type': Property.Type.STUDIO,
        'address': 'M.J. Cuenco Avenue, Mabolo', 'city': 'Cebu City',
        'description': 'Compact studio units intended for students and young professionals.',
        'amenities': 'Wi-Fi Ready, CCTV',
        'units': [('Studio 3A', 0, 1, 20, 7000, O), ('Studio 3B', 0, 1, 21, 7200, V)],
    },
]


class Command(BaseCommand):
    help = 'Create sample properties, units, and one pending application. Skips properties that already exist.'

    @transaction.atomic
    def handle(self, *args, **options):
        if not User.objects.filter(username='owner').exists():
            call_command('seed_demo_users', stdout=self.stdout)
        owner = User.objects.get(username='owner')

        for data in DEMO_PROPERTIES:
            data = dict(data)
            units = data.pop('units')
            prop, created = Property.objects.get_or_create(name=data['name'], defaults={**data, 'owner': owner})
            if not created:
                self.stdout.write(f'  skip   {prop.name} (already exists)')
                continue
            for name, beds, baths, area, rent, status in units:
                Unit.objects.create(property=prop, name=name, bedrooms=beds, bathrooms=baths,
                                    floor_area=area, monthly_rent=rent, status=status)
            self.stdout.write(self.style.SUCCESS(f'  create {prop.name} ({len(units)} units)'))

        tenant = User.objects.filter(username='tenant').first()
        unit = Unit.objects.filter(property__name='Cebu City Residences', name='Unit 201').first()
        if tenant and unit and not Application.objects.filter(tenant=tenant, unit=unit).exists():
            Application.objects.create(
                tenant=tenant, unit=unit,
                message='I am interested in the two-bedroom unit and can move in next month.',
            )
            self.stdout.write(self.style.SUCCESS('  create pending application for tenant → Unit 201'))
