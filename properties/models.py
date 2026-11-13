import builtins

from django.conf import settings
from django.db import models
from django.db.models import Q


class Property(models.Model):
    class Type(models.TextChoices):
        APARTMENT = 'apartment', 'Apartment'
        HOUSE = 'house', 'House'
        TOWNHOUSE = 'townhouse', 'Townhouse'
        STUDIO = 'studio', 'Studio'
        CONDO = 'condo', 'Condominium'
        BOARDING = 'boarding', 'Boarding House'

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='properties',
        limit_choices_to={'role': 'owner'},
    )
    name = models.CharField(max_length=150)
    property_type = models.CharField('type', max_length=20, choices=Type.choices)
    address = models.CharField(max_length=255)
    city = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    amenities = models.CharField(max_length=255, blank=True, help_text='Comma-separated, e.g. "Wi-Fi, Parking, CCTV"')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name_plural = 'properties'
        ordering = ['name']

    def __str__(self):
        return self.name

    @property
    def amenity_list(self):
        return [a.strip() for a in self.amenities.split(',') if a.strip()]


class Unit(models.Model):
    class Status(models.TextChoices):
        VACANT = 'vacant', 'Vacant'
        OCCUPIED = 'occupied', 'Occupied'

    property = models.ForeignKey(Property, on_delete=models.CASCADE, related_name='units')
    name = models.CharField(max_length=100)
    bedrooms = models.PositiveSmallIntegerField(default=0)
    bathrooms = models.PositiveSmallIntegerField(default=1)
    floor_area = models.PositiveIntegerField('floor area (sqm)', default=0)
    monthly_rent = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.VACANT)

    class Meta:
        ordering = ['property', 'name']
        constraints = [
            models.UniqueConstraint(fields=['property', 'name'], name='unique_unit_name_per_property'),
        ]

    def __str__(self):
        return f'{self.property.name} – {self.name}'

    @builtins.property  # plain @property is shadowed by the `property` field above
    def is_vacant(self):
        return self.status == self.Status.VACANT


class Application(models.Model):
    class Status(models.TextChoices):
        PENDING = 'pending', 'Pending'
        APPROVED = 'approved', 'Approved'
        REJECTED = 'rejected', 'Rejected'
        WITHDRAWN = 'withdrawn', 'Withdrawn'

    tenant = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='applications',
        limit_choices_to={'role': 'tenant'},
    )
    unit = models.ForeignKey(Unit, on_delete=models.CASCADE, related_name='applications')
    message = models.TextField(blank=True)
    preferred_move_in = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDING)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        constraints = [
            # A tenant can have only one pending application per unit.
            models.UniqueConstraint(
                fields=['tenant', 'unit'], condition=Q(status='pending'),
                name='one_pending_application_per_tenant_unit',
            ),
        ]

    def __str__(self):
        return f'{self.tenant} → {self.unit} ({self.get_status_display()})'

    @property
    def can_withdraw(self):
        return self.status == self.Status.PENDING
