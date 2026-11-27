"""PD3 core feature tests: Property Listing & Rental Applications.

Covers the four required kinds of test (valid input, invalid input, login
required, blocked access to another user's record) plus the end-to-end flow,
POST-only actions, wrong roles, duplicate submissions, and HTML escaping.
"""
from datetime import timedelta

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.models import User

from .models import Application, Property, Unit

PASSWORD = 'Str0ng-Pass!42'


def make_user(username, role):
    return User.objects.create_user(username=username, email=f'{username}@example.com', password=PASSWORD, role=role)


class CoreFeatureTestCase(TestCase):
    def setUp(self):
        self.owner = make_user('owner', User.Role.OWNER)
        self.other_owner = make_user('other_owner', User.Role.OWNER)
        self.tenant = make_user('tenant', User.Role.TENANT)
        self.other_tenant = make_user('other_tenant', User.Role.TENANT)
        self.staff = make_user('staff', User.Role.STAFF)
        self.prop = Property.objects.create(owner=self.owner, name='Lahug Apartments', property_type='apartment',
                                            address='Salinas Dr', city='Cebu City')
        self.unit = Unit.objects.create(property=self.prop, name='101', monthly_rent=8500)
        self.application = Application.objects.create(tenant=self.tenant, unit=self.unit,
                                                      message='Hello', status=Application.Status.PENDING)

    def page_urls(self):
        """Every core feature page that is opened with GET."""
        return [
            reverse('properties:browse'),
            reverse('properties:detail', args=[self.prop.pk]),
            reverse('properties:my_applications'),
            reverse('properties:edit_application', args=[self.application.pk]),
            reverse('properties:owner_properties'),
            reverse('properties:owner_property_create'),
            reverse('properties:owner_property', args=[self.prop.pk]),
            reverse('properties:owner_property_edit', args=[self.prop.pk]),
            reverse('properties:owner_unit_create', args=[self.prop.pk]),
            reverse('properties:owner_unit_edit', args=[self.unit.pk]),
            reverse('properties:owner_applications'),
        ]

    def action_urls(self):
        """Every core feature action that changes data (POST only)."""
        return [
            reverse('properties:withdraw', args=[self.application.pk]),
            reverse('properties:owner_property_delete', args=[self.prop.pk]),
            reverse('properties:owner_unit_delete', args=[self.unit.pk]),
            reverse('properties:owner_application_decide', args=[self.application.pk, 'approve']),
            reverse('properties:owner_application_decide', args=[self.application.pk, 'reject']),
        ]


class LoginRequiredTests(CoreFeatureTestCase):
    def test_core_pages_require_login(self):
        for url in self.page_urls():
            with self.subTest(url=url):
                self.assertRedirects(self.client.get(url), f"{reverse('accounts:login')}?next={url}")

    def test_core_actions_require_login(self):
        for url in self.action_urls():
            with self.subTest(url=url):
                self.assertRedirects(self.client.post(url), f"{reverse('accounts:login')}?next={url}")
        self.assertTrue(Property.objects.filter(pk=self.prop.pk).exists())
        self.application.refresh_from_db()
        self.assertEqual(self.application.status, Application.Status.PENDING)


class RoleTests(CoreFeatureTestCase):
    def test_staff_cannot_open_core_pages(self):
        self.client.force_login(self.staff)
        for url in self.page_urls():
            with self.subTest(url=url):
                self.assertRedirects(self.client.get(url), reverse('accounts:dashboard_staff'))

    def test_tenant_cannot_approve_even_by_posting_directly(self):
        self.client.force_login(self.tenant)
        url = reverse('properties:owner_application_decide', args=[self.application.pk, 'approve'])
        self.assertRedirects(self.client.post(url), reverse('accounts:dashboard_tenant'))
        self.application.refresh_from_db()
        self.assertEqual(self.application.status, Application.Status.PENDING)


class PostOnlyTests(CoreFeatureTestCase):
    def test_data_changing_actions_reject_get(self):
        self.client.force_login(self.owner)
        owner_actions = [u for u in self.action_urls() if '/owner/' in u]
        for url in owner_actions:
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 405)
        self.client.force_login(self.tenant)
        self.assertEqual(self.client.get(reverse('properties:withdraw', args=[self.application.pk])).status_code, 405)
        self.assertTrue(Unit.objects.filter(pk=self.unit.pk).exists())
        self.application.refresh_from_db()
        self.assertEqual(self.application.status, Application.Status.PENDING)


class OtherUsersRecordTests(CoreFeatureTestCase):
    def test_tenant_cannot_open_or_change_another_tenants_application(self):
        self.client.force_login(self.other_tenant)
        self.assertEqual(self.client.get(reverse('properties:edit_application', args=[self.application.pk])).status_code, 404)
        self.assertEqual(self.client.post(reverse('properties:withdraw', args=[self.application.pk])).status_code, 404)
        self.application.refresh_from_db()
        self.assertEqual(self.application.status, Application.Status.PENDING)

    def test_owner_cannot_open_change_or_decide_another_owners_records(self):
        self.client.force_login(self.other_owner)
        for url in [reverse('properties:owner_property', args=[self.prop.pk]),
                    reverse('properties:owner_property_edit', args=[self.prop.pk]),
                    reverse('properties:owner_unit_edit', args=[self.unit.pk])]:
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 404)
        for url in self.action_urls()[1:]:  # owner actions
            with self.subTest(url=url):
                self.assertEqual(self.client.post(url).status_code, 404)
        self.assertTrue(Unit.objects.filter(pk=self.unit.pk).exists())
        self.application.refresh_from_db()
        self.assertEqual(self.application.status, Application.Status.PENDING)

    def test_other_owner_does_not_see_the_application_in_their_list(self):
        self.client.force_login(self.other_owner)
        response = self.client.get(reverse('properties:owner_applications'), {'status': 'all'})
        self.assertNotIn(self.application, response.context['applications'])


class EndToEndTests(CoreFeatureTestCase):
    def test_full_flow_list_apply_approve(self):
        # Owner lists a property and a unit.
        self.client.force_login(self.owner)
        self.client.post(reverse('properties:owner_property_create'), {
            'name': 'Banilad Homes', 'property_type': 'house', 'address': 'Gov. Cuenco', 'city': 'Cebu City'})
        prop = Property.objects.get(name='Banilad Homes')
        self.client.post(reverse('properties:owner_unit_create', args=[prop.pk]), {
            'name': 'A', 'bedrooms': 2, 'bathrooms': 1, 'floor_area': 60, 'monthly_rent': '18000', 'status': 'vacant'})
        unit = prop.units.get(name='A')

        # Tenant finds it and applies.
        self.client.force_login(self.other_tenant)
        self.assertContains(self.client.get(reverse('properties:browse')), 'Banilad Homes')
        move_in = (timezone.localdate() + timedelta(days=14)).isoformat()
        response = self.client.post(reverse('properties:detail', args=[prop.pk]),
                                    {'unit': unit.pk, 'preferred_move_in': move_in, 'message': 'Hi'}, follow=True)
        self.assertContains(response, 'Application for A submitted.')
        application = Application.objects.get(tenant=self.other_tenant, unit=unit)
        self.assertEqual(application.status, Application.Status.PENDING)

        # Owner approves; the unit is filled.
        self.client.force_login(self.owner)
        self.client.post(reverse('properties:owner_application_decide', args=[application.pk, 'approve']))
        application.refresh_from_db()
        unit.refresh_from_db()
        self.assertEqual(application.status, Application.Status.APPROVED)
        self.assertEqual(unit.status, Unit.Status.OCCUPIED)

        # The tenant sees it approved, and the unit is no longer listed as vacant.
        self.client.force_login(self.other_tenant)
        response = self.client.get(reverse('properties:my_applications'), {'status': 'approved'})
        self.assertIn(application, response.context['applications'])
        self.assertNotContains(self.client.get(reverse('properties:browse')), 'Banilad Homes')


class InvalidInputTests(CoreFeatureTestCase):
    def test_apply_without_choosing_a_unit(self):
        self.client.force_login(self.other_tenant)
        response = self.client.post(reverse('properties:detail', args=[self.prop.pk]), {'message': 'Hi'})
        self.assertEqual(response.status_code, 200)
        self.assertIn('Please choose a vacant unit.', response.context['form'].errors['unit'])
        self.assertFalse(Application.objects.filter(tenant=self.other_tenant).exists())

    def test_unit_form_rejects_bad_numbers(self):
        self.client.force_login(self.owner)
        response = self.client.post(reverse('properties:owner_unit_create', args=[self.prop.pk]), {
            'name': '102', 'bedrooms': -1, 'bathrooms': 'two', 'floor_area': 50, 'monthly_rent': 'abc',
            'status': 'vacant'})
        self.assertEqual(response.status_code, 200)
        errors = response.context['form'].errors
        for field in ('bedrooms', 'bathrooms', 'monthly_rent'):
            self.assertIn(field, errors)
        self.assertFalse(Unit.objects.filter(name='102').exists())

    def test_unknown_status_value_is_rejected(self):
        self.client.force_login(self.owner)
        response = self.client.post(reverse('properties:owner_unit_create', args=[self.prop.pk]), {
            'name': '103', 'monthly_rent': '9000', 'status': 'demolished'})
        self.assertIn('status', response.context['form'].errors)
        self.assertFalse(Unit.objects.filter(name='103').exists())


class DuplicateSubmissionTests(CoreFeatureTestCase):
    def test_apply_redirects_and_a_resubmit_is_rejected(self):
        self.client.force_login(self.other_tenant)
        url = reverse('properties:detail', args=[self.prop.pk])
        first = self.client.post(url, {'unit': self.unit.pk})
        self.assertRedirects(first, reverse('properties:my_applications'))  # Post/Redirect/Get
        second = self.client.post(url, {'unit': self.unit.pk})
        self.assertEqual(second.status_code, 200)
        self.assertIn('You already have a pending application for this unit.', second.context['form'].non_field_errors())
        self.assertEqual(Application.objects.filter(tenant=self.other_tenant, unit=self.unit).count(), 1)


class EscapingTests(CoreFeatureTestCase):
    def test_user_input_is_html_escaped(self):
        script = '<script>alert("x")</script>'
        self.prop.name = script
        self.prop.save()
        self.client.force_login(self.tenant)
        response = self.client.get(reverse('properties:browse'))
        self.assertNotContains(response, script)
        self.assertContains(response, '&lt;script&gt;')
