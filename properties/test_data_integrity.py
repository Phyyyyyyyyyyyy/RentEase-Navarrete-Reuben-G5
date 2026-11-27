"""Data integrity: database constraints, protected deletes, and upload limits."""
import io
import os
from decimal import Decimal

from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import IntegrityError, transaction
from django.db.models import ProtectedError
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from PIL import Image

from accounts.models import User
from payments.models import Payment, RentCharge

from .models import Application, Property, Unit

PASSWORD = 'Str0ng-Pass!42'


def make_user(username, role):
    return User.objects.create_user(username=username, email=f'{username}@example.com', password=PASSWORD, role=role)


class IntegrityTestCase(TestCase):
    def setUp(self):
        self.owner = make_user('owner', User.Role.OWNER)
        self.tenant = make_user('tenant', User.Role.TENANT)
        self.prop = Property.objects.create(owner=self.owner, name='Lahug Apartments', property_type='apartment',
                                            address='Salinas Dr', city='Cebu City')
        self.unit = Unit.objects.create(property=self.prop, name='101', monthly_rent=8000, status='occupied')
        self.tenancy = Application.objects.create(tenant=self.tenant, unit=self.unit, status='approved',
                                                  approved_at=timezone.now())
        self.client.force_login(self.owner)

    def add_payment(self):
        return Payment.objects.create(tenancy=self.tenancy, amount=8000, method=Payment.Method.CASH,
                                      status=Payment.Status.CONFIRMED, paid_on=timezone.localdate(),
                                      recorded_by=self.owner)

    def end_tenancy(self):
        self.unit.status = Unit.Status.VACANT
        self.unit.save()


class ProtectedDeleteTests(IntegrityTestCase):
    def test_cannot_delete_unit_with_current_tenant(self):
        response = self.client.post(reverse('properties:owner_unit_delete', args=[self.unit.pk]), follow=True)
        self.assertTrue(Unit.objects.filter(pk=self.unit.pk).exists())
        self.assertContains(response, 'has a current tenant')

    def test_cannot_delete_unit_with_payment_history(self):
        self.add_payment()
        self.end_tenancy()
        response = self.client.post(reverse('properties:owner_unit_delete', args=[self.unit.pk]), follow=True)
        self.assertTrue(Unit.objects.filter(pk=self.unit.pk).exists())
        self.assertEqual(Payment.objects.count(), 1)
        self.assertContains(response, 'has rent payment records')

    def test_cannot_delete_property_with_payment_history(self):
        self.add_payment()
        self.end_tenancy()
        response = self.client.post(reverse('properties:owner_property_delete', args=[self.prop.pk]), follow=True)
        self.assertTrue(Property.objects.filter(pk=self.prop.pk).exists())
        self.assertEqual(Payment.objects.count(), 1)
        self.assertContains(response, 'has rent payment records')

    def test_can_delete_vacant_unit_without_history(self):
        empty = Unit.objects.create(property=self.prop, name='102', monthly_rent=9000)
        Application.objects.create(tenant=self.tenant, unit=empty, status='rejected')
        response = self.client.post(reverse('properties:owner_unit_delete', args=[empty.pk]), follow=True)
        self.assertFalse(Unit.objects.filter(pk=empty.pk).exists())
        self.assertContains(response, '102 deleted.')

    def test_database_protects_payments_from_cascade(self):
        self.add_payment()
        with self.assertRaises(ProtectedError):
            self.tenancy.delete()
        self.assertEqual(Payment.objects.count(), 1)


class ConstraintTests(IntegrityTestCase):
    def test_database_rejects_zero_or_negative_rent(self):
        for rent in (0, -500):
            with self.subTest(rent=rent), self.assertRaises(IntegrityError), transaction.atomic():
                Unit.objects.create(property=self.prop, name=f'Bad {rent}', monthly_rent=rent)

    def test_database_rejects_zero_rent_charge(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            RentCharge.objects.create(tenancy=self.tenancy, period=timezone.localdate().replace(day=1),
                                      amount=0, due_date=timezone.localdate())

    def test_model_validation_rejects_zero_rent(self):
        unit = Unit(property=self.prop, name='103', monthly_rent=Decimal('0.00'))
        with self.assertRaises(Exception) as ctx:
            unit.full_clean()
        self.assertIn('monthly_rent', ctx.exception.message_dict)


class InputHardeningTests(IntegrityTestCase):
    def test_invalid_amount_in_url_is_ignored(self):
        url = reverse('payments:owner_tenancy', args=[self.tenancy.pk])
        for bad in ('NaN', 'Infinity', '-50', '0', 'abc', '1e999999'):
            with self.subTest(amount=bad):
                response = self.client.get(url, {'amount': bad})
                self.assertEqual(response.status_code, 200)
                initial = response.context['form'].initial['amount']
                self.assertTrue(initial.is_finite() and initial > 0)

    def test_profile_photo_over_5_mb_is_rejected(self):
        # A real PNG made of random pixels, so it can't compress below 5 MB.
        buffer = io.BytesIO()
        Image.frombytes('RGB', (1400, 1400), os.urandom(1400 * 1400 * 3)).save(buffer, format='PNG')
        self.assertGreater(buffer.tell(), 5 * 1024 * 1024)
        photo = SimpleUploadedFile('big.png', buffer.getvalue(), content_type='image/png')
        response = self.client.post(reverse('accounts:profile_edit'), {
            'first_name': 'Ana', 'last_name': 'Santos', 'email': 'owner@example.com', 'profile_photo': photo})
        self.assertEqual(response.status_code, 200)
        self.assertIn('The profile photo must be 5 MB or smaller.', response.context['form'].errors['profile_photo'])
        self.owner.refresh_from_db()
        self.assertFalse(self.owner.profile_photo)
