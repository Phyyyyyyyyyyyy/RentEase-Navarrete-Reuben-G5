"""Monthly rent and payments for approved tenancies.

A tenancy is an approved `properties.Application`. While its unit is occupied,
the tenant owes one `RentCharge` per month, due on the last day of that month.

A `Payment` counts toward the balance only once it is CONFIRMED:
  * GCash payments submitted by the tenant start PENDING until the owner
    confirms the reference number against their GCash history.
  * Payments the owner records (cash, in person, bank, upfront) are
    confirmed immediately.

Payments are not tied to a specific month. Confirmed money is applied to the
oldest unpaid month first, so partial payments and upfront (advance)
payments both work, and any excess shows as credit for future months.
"""
from django.conf import settings
from django.core.validators import MinValueValidator, RegexValidator
from django.db import models
from django.db.models import Q

from properties.models import Application

# GCash reference numbers are 13 digits (shown on the receipt after sending money).
gcash_reference_validator = RegexValidator(r'^\d{13}$', 'Enter the 13-digit reference number from your GCash receipt.')


class RentCharge(models.Model):
    tenancy = models.ForeignKey(Application, on_delete=models.CASCADE, related_name='rent_charges')
    period = models.DateField(help_text='First day of the month this rent is for.')
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    due_date = models.DateField(help_text='Last day of the month.')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['period']
        constraints = [
            models.UniqueConstraint(fields=['tenancy', 'period'], name='one_rent_charge_per_tenancy_month'),
        ]

    def __str__(self):
        return f'{self.tenancy.unit} – {self.period:%B %Y}'


class Payment(models.Model):
    class Method(models.TextChoices):
        GCASH = 'gcash', 'GCash'
        CASH = 'cash', 'Cash (in person)'
        BANK = 'bank', 'Bank transfer'
        OTHER = 'other', 'Other'

    class Status(models.TextChoices):
        PENDING = 'pending', 'Awaiting confirmation'
        CONFIRMED = 'confirmed', 'Confirmed'
        REJECTED = 'rejected', 'Rejected'

    tenancy = models.ForeignKey(Application, on_delete=models.CASCADE, related_name='payments')
    amount = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(1)])
    method = models.CharField(max_length=10, choices=Method.choices)
    reference_number = models.CharField(max_length=20, blank=True)
    proof = models.ImageField('receipt screenshot', upload_to='payment_proofs/', blank=True)
    paid_on = models.DateField()
    note = models.CharField(max_length=255, blank=True)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDING)
    recorded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='+')
    reviewed_at = models.DateTimeField(null=True, blank=True)
    owner_note = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-paid_on', '-created_at']
        constraints = [
            models.CheckConstraint(condition=Q(amount__gt=0), name='payment_amount_positive'),
            # The same GCash transfer cannot be submitted twice (unless it was rejected).
            models.UniqueConstraint(
                fields=['reference_number'],
                condition=Q(method='gcash') & ~Q(reference_number='') & ~Q(status='rejected'),
                name='unique_active_gcash_reference',
            ),
        ]

    def __str__(self):
        return f'{self.get_method_display()} ₱{self.amount:,.2f} for {self.tenancy.unit} ({self.get_status_display()})'

    @property
    def recorded_by_owner(self):
        return self.recorded_by_id is not None and self.recorded_by_id != self.tenancy.tenant_id
