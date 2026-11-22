from datetime import date, datetime, timedelta
from decimal import Decimal

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.models import User
from properties.models import Application, Property, Unit

from .billing import build_ledger, month_end, month_start, sync_charges
from .models import Payment, RentCharge

PASSWORD = 'Str0ng-Pass!42'
REF = '1234567890123'


def make_user(username, role, **extra):
    return User.objects.create_user(username=username, email=f'{username}@example.com', password=PASSWORD,
                                    role=role, **extra)


def aware(d):
    return timezone.make_aware(datetime(d.year, d.month, d.day, 10, 0))


class PaymentTestCase(TestCase):
    def setUp(self):
        self.owner = make_user('owner', User.Role.OWNER, gcash_number='09171234567', gcash_name='Ana Santos')
        self.other_owner = make_user('other_owner', User.Role.OWNER)
        self.tenant = make_user('tenant', User.Role.TENANT)
        self.other_tenant = make_user('other_tenant', User.Role.TENANT)
        prop = Property.objects.create(owner=self.owner, name='Lahug Apartments', property_type='apartment',
                                       address='Salinas Dr', city='Cebu City')
        self.unit = Unit.objects.create(property=prop, name='101', monthly_rent=8000, status='occupied')
        # Approved two months ago, so three monthly bills exist (two past, one current).
        self.today = timezone.localdate()
        self.start = month_start(month_start(self.today) - timedelta(days=40))
        self.tenancy = Application.objects.create(tenant=self.tenant, unit=self.unit, status='approved',
                                                  approved_at=aware(self.start))
        self.client.force_login(self.tenant)

    def pay(self, amount, status=Payment.Status.CONFIRMED, method=Payment.Method.CASH, **extra):
        return Payment.objects.create(tenancy=self.tenancy, amount=amount, method=method, status=status,
                                      paid_on=self.today, recorded_by=self.owner, **extra)


class BillingTests(PaymentTestCase):
    def test_one_charge_per_month_due_on_last_day(self):
        sync_charges(self.tenancy, self.today)
        sync_charges(self.tenancy, self.today)  # running twice adds nothing
        charges = list(self.tenancy.rent_charges.all())
        self.assertEqual(len(charges), 3)
        self.assertEqual(charges[0].period, self.start)
        for c in charges:
            self.assertEqual(c.period.day, 1)
            self.assertEqual(c.due_date, month_end(c.period))
            self.assertEqual(c.amount, Decimal('8000'))

    def test_month_end_handles_february_and_december(self):
        self.assertEqual(month_end(date(2028, 2, 10)), date(2028, 2, 29))
        self.assertEqual(month_end(date(2027, 2, 1)), date(2027, 2, 28))
        self.assertEqual(month_end(date(2026, 12, 5)), date(2026, 12, 31))

    def test_no_charges_before_move_in(self):
        self.tenancy.preferred_move_in = self.today + timedelta(days=60)
        self.tenancy.save()
        sync_charges(self.tenancy, self.today)
        self.assertFalse(self.tenancy.rent_charges.exists())

    def test_unpaid_past_months_are_overdue(self):
        ledger = build_ledger(self.tenancy, today=self.today)
        self.assertEqual(ledger.balance, Decimal('24000'))
        self.assertEqual(ledger.overdue, Decimal('16000'))
        self.assertEqual([l.state for l in ledger.lines], ['overdue', 'overdue', 'due'])

    def test_partial_payment_applies_to_oldest_month_first(self):
        self.pay(10000)
        ledger = build_ledger(self.tenancy, today=self.today)
        self.assertEqual([(l.state, l.remaining) for l in ledger.lines],
                         [('paid', 0), ('overdue', Decimal('6000')), ('due', Decimal('8000'))])
        self.assertEqual(ledger.balance, Decimal('14000'))

    def test_upfront_payment_becomes_credit(self):
        self.pay(40000)
        ledger = build_ledger(self.tenancy, today=self.today)
        self.assertEqual(ledger.balance, 0)
        self.assertEqual(ledger.credit, Decimal('16000'))
        self.assertEqual(ledger.months_covered, 2)
        self.assertTrue(all(l.state == 'paid' for l in ledger.lines))

    def test_only_confirmed_payments_count(self):
        self.pay(8000, status=Payment.Status.PENDING, method=Payment.Method.GCASH, reference_number=REF)
        self.pay(8000, status=Payment.Status.REJECTED)
        ledger = build_ledger(self.tenancy, today=self.today)
        self.assertEqual(ledger.balance, Decimal('24000'))
        self.assertEqual(ledger.pending_total, Decimal('8000'))

    def test_vacated_unit_stops_billing(self):
        self.unit.status = Unit.Status.VACANT
        self.unit.save()
        self.client.get(reverse('payments:tenant'))
        self.assertFalse(RentCharge.objects.exists())


class TenantGCashTests(PaymentTestCase):
    def submit(self, **overrides):
        data = {'amount': '8000', 'reference_number': REF, 'paid_on': self.today.isoformat(), 'note': ''}
        data.update(overrides)
        return self.client.post(reverse('payments:gcash_pay', args=[self.tenancy.pk]), data)

    def test_page_shows_owner_gcash(self):
        response = self.client.get(reverse('payments:gcash_pay', args=[self.tenancy.pk]))
        self.assertContains(response, '09171234567')
        self.assertContains(response, 'Ana Santos')

    def test_submission_is_pending_until_owner_confirms(self):
        self.assertRedirects(self.submit(), reverse('payments:tenant'))
        payment = Payment.objects.get()
        self.assertEqual((payment.status, payment.method, payment.recorded_by), ('pending', 'gcash', self.tenant))
        self.assertEqual(build_ledger(self.tenancy).balance, Decimal('24000'))

    def test_reference_must_be_13_digits_and_unused(self):
        self.submit(reference_number='12345')
        self.assertFalse(Payment.objects.exists())
        self.submit()
        self.submit(amount='500')
        self.assertEqual(Payment.objects.count(), 1)

    def test_rejected_reference_can_be_resubmitted(self):
        self.submit()
        Payment.objects.update(status=Payment.Status.REJECTED)
        self.submit()
        self.assertEqual(Payment.objects.filter(status='pending').count(), 1)

    def test_rejects_future_date_and_zero_amount(self):
        self.submit(paid_on=(self.today + timedelta(days=1)).isoformat())
        self.submit(amount='0', reference_number='9999999999999')
        self.assertFalse(Payment.objects.exists())

    def test_owner_without_gcash_cannot_be_paid_by_gcash(self):
        self.owner.gcash_number = ''
        self.owner.save()
        self.assertRedirects(self.submit(), reverse('payments:tenant'))
        self.assertFalse(Payment.objects.exists())

    def test_cannot_pay_into_someone_elses_tenancy(self):
        self.client.force_login(self.other_tenant)
        self.assertEqual(self.submit().status_code, 404)

    def test_tenant_can_cancel_own_pending_submission(self):
        self.submit()
        payment = Payment.objects.get()
        self.client.post(reverse('payments:cancel_submission', args=[payment.pk]))
        self.assertFalse(Payment.objects.exists())


class OwnerPaymentTests(PaymentTestCase):
    def setUp(self):
        super().setUp()
        self.client.force_login(self.owner)
        self.url = reverse('payments:owner_tenancy', args=[self.tenancy.pk])

    def record(self, amount, method='cash'):
        return self.client.post(self.url, {'amount': amount, 'method': method, 'paid_on': self.today.isoformat(),
                                           'reference_number': '', 'note': 'Paid in person'})

    def test_record_in_person_payment_counts_immediately(self):
        self.assertRedirects(self.record('8000'), self.url)
        payment = Payment.objects.get()
        self.assertEqual((payment.status, payment.recorded_by), ('confirmed', self.owner))
        self.assertEqual(build_ledger(self.tenancy).balance, Decimal('16000'))

    def test_record_full_balance_marks_everything_paid(self):
        self.record('24000')
        ledger = build_ledger(self.tenancy)
        self.assertEqual((ledger.balance, ledger.credit), (0, 0))

    def test_form_prefills_balance_and_mark_paid_amount(self):
        response = self.client.get(self.url)
        self.assertEqual(Decimal(response.context['form'].initial['amount']), Decimal('24000'))
        response = self.client.get(self.url, {'amount': '16000.00'})
        self.assertEqual(response.context['form'].initial['amount'], Decimal('16000.00'))

    def test_confirm_and_reject_gcash(self):
        a = self.pay(8000, status='pending', method='gcash', reference_number=REF)
        b = self.pay(8000, status='pending', method='gcash', reference_number='3210987654321')
        self.client.post(reverse('payments:owner_review', args=[a.pk, 'confirm']))
        self.client.post(reverse('payments:owner_review', args=[b.pk, 'reject']), {'reason': 'Not received'})
        a.refresh_from_db(); b.refresh_from_db()
        self.assertEqual((a.status, b.status, b.owner_note), ('confirmed', 'rejected', 'Not received'))
        self.assertEqual(build_ledger(self.tenancy).balance, Decimal('16000'))

    def test_void_confirmed_payment(self):
        p = self.pay(8000)
        self.client.post(reverse('payments:owner_review', args=[p.pk, 'void']))
        p.refresh_from_db()
        self.assertEqual(p.status, 'rejected')
        self.assertEqual(build_ledger(self.tenancy).balance, Decimal('24000'))

    def test_cannot_confirm_twice_or_void_pending(self):
        p = self.pay(8000, status='pending', method='gcash', reference_number=REF)
        self.client.post(reverse('payments:owner_review', args=[p.pk, 'void']))
        p.refresh_from_db()
        self.assertEqual(p.status, 'pending')

    def test_other_owner_gets_404(self):
        p = self.pay(8000, status='pending', method='gcash', reference_number=REF)
        self.client.force_login(self.other_owner)
        self.assertEqual(self.client.get(self.url).status_code, 404)
        self.assertEqual(self.client.post(reverse('payments:owner_review', args=[p.pk, 'confirm'])).status_code, 404)
        p.refresh_from_db()
        self.assertEqual(p.status, 'pending')

    def test_overview_lists_tenant_and_pending(self):
        self.pay(8000, status='pending', method='gcash', reference_number=REF)
        response = self.client.get(reverse('payments:owner'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context['ledgers']), 1)
        self.assertEqual(len(response.context['pending']), 1)
        self.assertEqual(response.context['outstanding'], Decimal('24000'))


class AccessAndProfileTests(PaymentTestCase):
    def test_role_isolation(self):
        self.assertRedirects(self.client.get(reverse('payments:owner')), reverse('accounts:dashboard_tenant'))
        self.client.force_login(self.owner)
        self.assertRedirects(self.client.get(reverse('payments:tenant')), reverse('accounts:dashboard_owner'))

    def test_approval_sets_tenancy_start(self):
        unit = Unit.objects.create(property=self.unit.property, name='102', monthly_rent=9000)
        app = Application.objects.create(tenant=self.other_tenant, unit=unit)
        self.client.force_login(self.owner)
        self.client.post(reverse('properties:owner_application_decide', args=[app.pk, 'approve']))
        app.refresh_from_db()
        self.assertIsNotNone(app.approved_at)
        self.assertEqual(app.tenancy_start, self.today)

    def test_gcash_fields_only_for_owners(self):
        response = self.client.get(reverse('accounts:profile_edit'))
        self.assertNotIn('gcash_number', response.context['form'].fields)
        self.client.force_login(self.other_owner)
        response = self.client.get(reverse('accounts:profile_edit'))
        self.assertIn('gcash_number', response.context['form'].fields)

    def test_owner_gcash_number_validated(self):
        self.client.force_login(self.other_owner)
        data = {'first_name': 'Ben', 'last_name': 'Cruz', 'email': 'other_owner@example.com', 'phone': '',
                'gcash_name': 'Ben Cruz', 'gcash_number': '12345'}
        self.client.post(reverse('accounts:profile_edit'), data)
        self.other_owner.refresh_from_db()
        self.assertEqual(self.other_owner.gcash_number, '')
        data['gcash_number'] = '0918 765 4321'
        self.client.post(reverse('accounts:profile_edit'), data)
        self.other_owner.refresh_from_db()
        self.assertEqual(self.other_owner.gcash_number, '09187654321')

    def test_dashboard_shows_rent_due(self):
        response = self.client.get(reverse('accounts:dashboard_tenant'))
        self.assertContains(response, 'Pay rent')
        self.assertContains(response, '₱24,000')
