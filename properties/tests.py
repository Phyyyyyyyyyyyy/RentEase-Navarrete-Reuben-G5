from datetime import timedelta

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.models import User

from .models import Application, Property, Unit

PASSWORD = 'Str0ng-Pass!42'


def make_user(username, role):
    return User.objects.create_user(username=username, email=f'{username}@example.com', password=PASSWORD, role=role)


class PropertyTestCase(TestCase):
    def setUp(self):
        self.owner = make_user('owner', User.Role.OWNER)
        self.tenant = make_user('tenant', User.Role.TENANT)
        self.apt = Property.objects.create(owner=self.owner, name='Lahug Apartments', property_type='apartment',
                                           address='Salinas Dr', city='Cebu City', amenities='Wi-Fi, Parking')
        self.vacant = Unit.objects.create(property=self.apt, name='101', monthly_rent=8500)
        self.occupied = Unit.objects.create(property=self.apt, name='102', monthly_rent=9000, status='occupied')
        self.studio = Property.objects.create(owner=self.owner, name='Mabolo Studios', property_type='studio',
                                              address='MJ Cuenco', city='Cebu City')
        Unit.objects.create(property=self.studio, name='3A', monthly_rent=15000)
        self.full = Property.objects.create(owner=self.owner, name='Full House', property_type='house',
                                            address='Banilad', city='Cebu City')
        Unit.objects.create(property=self.full, name='Main', monthly_rent=20000, status='occupied')
        self.client.force_login(self.tenant)


class AccessTests(PropertyTestCase):
    def test_tenant_only(self):
        urls = [reverse('properties:browse'), reverse('properties:detail', args=[self.apt.pk]),
                reverse('properties:my_applications')]
        self.client.force_login(self.owner)
        for url in urls:
            self.assertRedirects(self.client.get(url), reverse('accounts:dashboard_owner'))
        self.client.logout()
        for url in urls:
            self.assertRedirects(self.client.get(url), f"{reverse('accounts:login')}?next={url}")


class BrowseTests(PropertyTestCase):
    def names(self, **params):
        response = self.client.get(reverse('properties:browse'), params)
        self.assertEqual(response.status_code, 200)
        return {p.name for p in response.context['properties']}

    def test_only_properties_with_vacant_units(self):
        self.assertEqual(self.names(), {'Lahug Apartments', 'Mabolo Studios'})

    def test_search_type_and_max_rent(self):
        self.assertEqual(self.names(q='mabolo'), {'Mabolo Studios'})
        self.assertEqual(self.names(type='apartment'), {'Lahug Apartments'})
        self.assertEqual(self.names(max_rent=10000), {'Lahug Apartments'})
        self.assertEqual(self.names(max_rent=1000), set())

    def test_invalid_max_rent_is_ignored(self):
        self.assertEqual(self.names(max_rent='abc'), {'Lahug Apartments', 'Mabolo Studios'})


class ApplyTests(PropertyTestCase):
    def apply(self, unit, **extra):
        return self.client.post(reverse('properties:detail', args=[self.apt.pk]),
                                {'unit': unit.pk, 'message': 'Hi', **extra}, follow=True)

    def test_apply_for_vacant_unit(self):
        response = self.apply(self.vacant)
        self.assertRedirects(response, reverse('properties:my_applications'))
        self.assertContains(response, 'submitted')
        app = Application.objects.get()
        self.assertEqual((app.tenant, app.unit, app.status), (self.tenant, self.vacant, 'pending'))

    def test_cannot_apply_for_occupied_unit(self):
        self.apply(self.occupied)
        self.assertFalse(Application.objects.exists())

    def test_cannot_apply_twice_while_pending(self):
        self.apply(self.vacant)
        response = self.apply(self.vacant)
        self.assertContains(response, 'already have a pending application')
        self.assertEqual(Application.objects.count(), 1)

    def test_unit_must_belong_to_property(self):
        other = self.studio.units.get()
        self.apply(other)
        self.assertFalse(Application.objects.exists())

    def test_move_in_date_cannot_be_past(self):
        response = self.apply(self.vacant, preferred_move_in=(timezone.localdate() - timedelta(days=1)).isoformat())
        self.assertContains(response, 'cannot be in the past')
        self.assertFalse(Application.objects.exists())


class MyApplicationsTests(PropertyTestCase):
    def setUp(self):
        super().setUp()
        self.mine = Application.objects.create(tenant=self.tenant, unit=self.vacant)
        self.other_tenant = make_user('other', User.Role.TENANT)
        self.theirs = Application.objects.create(tenant=self.other_tenant, unit=self.vacant, message='SECRET-NOTE')

    def test_lists_only_own_applications(self):
        response = self.client.get(reverse('properties:my_applications'))
        self.assertEqual(list(response.context['applications']), [self.mine])
        self.assertNotContains(response, 'SECRET-NOTE')

    def test_status_filter(self):
        response = self.client.get(reverse('properties:my_applications'), {'status': 'approved'})
        self.assertEqual(list(response.context['applications']), [])

    def test_withdraw_own_pending(self):
        response = self.client.post(reverse('properties:withdraw', args=[self.mine.pk]), follow=True)
        self.assertContains(response, 'withdrawn')
        self.mine.refresh_from_db()
        self.assertEqual(self.mine.status, 'withdrawn')

    def test_cannot_withdraw_someone_elses(self):
        response = self.client.post(reverse('properties:withdraw', args=[self.theirs.pk]))
        self.assertEqual(response.status_code, 404)
        self.theirs.refresh_from_db()
        self.assertEqual(self.theirs.status, 'pending')

    def test_withdraw_requires_post(self):
        self.assertEqual(self.client.get(reverse('properties:withdraw', args=[self.mine.pk])).status_code, 405)


class OwnerTestCase(PropertyTestCase):
    """Logged in as the owner of all three properties; `other_owner` owns `theirs`."""

    def setUp(self):
        super().setUp()
        self.other_owner = make_user('other', User.Role.OWNER)
        self.theirs = Property.objects.create(owner=self.other_owner, name='Not Mine', property_type='house',
                                              address='Talamban', city='Cebu City')
        self.their_unit = Unit.objects.create(property=self.theirs, name='A', monthly_rent=5000)
        self.client.force_login(self.owner)


class OwnerAccessTests(OwnerTestCase):
    def test_owner_pages_are_owner_only(self):
        urls = [reverse('properties:owner_properties'), reverse('properties:owner_applications'),
                reverse('properties:owner_property', args=[self.apt.pk])]
        self.client.force_login(self.tenant)
        for url in urls:
            self.assertRedirects(self.client.get(url), reverse('accounts:dashboard_tenant'))

    def test_lists_only_own_properties(self):
        response = self.client.get(reverse('properties:owner_properties'))
        names = {p.name for p in response.context['properties']}
        self.assertEqual(names, {'Lahug Apartments', 'Mabolo Studios', 'Full House'})

    def test_cannot_touch_another_owners_property_or_unit(self):
        for url in [reverse('properties:owner_property', args=[self.theirs.pk]),
                    reverse('properties:owner_property_edit', args=[self.theirs.pk]),
                    reverse('properties:owner_unit_create', args=[self.theirs.pk]),
                    reverse('properties:owner_unit_edit', args=[self.their_unit.pk])]:
            self.assertEqual(self.client.get(url).status_code, 404)
        self.client.post(reverse('properties:owner_property_delete', args=[self.theirs.pk]))
        self.client.post(reverse('properties:owner_unit_delete', args=[self.their_unit.pk]))
        self.assertTrue(Property.objects.filter(pk=self.theirs.pk).exists())
        self.assertTrue(Unit.objects.filter(pk=self.their_unit.pk).exists())


class OwnerPropertyTests(OwnerTestCase):
    def test_create_property_sets_owner(self):
        response = self.client.post(reverse('properties:owner_property_create'), {
            'name': 'Banilad Homes', 'property_type': 'house', 'address': 'Gov. Cuenco', 'city': 'Cebu City'})
        prop = Property.objects.get(name='Banilad Homes')
        self.assertEqual(prop.owner, self.owner)
        self.assertRedirects(response, reverse('properties:owner_property', args=[prop.pk]))

    def test_create_property_requires_fields(self):
        response = self.client.post(reverse('properties:owner_property_create'), {'name': ''})
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context['form'].errors)

    def test_edit_and_delete_property(self):
        self.client.post(reverse('properties:owner_property_edit', args=[self.studio.pk]), {
            'name': 'Mabolo Lofts', 'property_type': 'studio', 'address': 'MJ Cuenco', 'city': 'Cebu City'})
        self.studio.refresh_from_db()
        self.assertEqual(self.studio.name, 'Mabolo Lofts')
        self.client.post(reverse('properties:owner_property_delete', args=[self.studio.pk]))
        self.assertFalse(Property.objects.filter(pk=self.studio.pk).exists())

    def test_delete_requires_post(self):
        response = self.client.get(reverse('properties:owner_property_delete', args=[self.studio.pk]))
        self.assertEqual(response.status_code, 405)


class OwnerUnitTests(OwnerTestCase):
    def unit_data(self, **overrides):
        return {'name': '201', 'bedrooms': 1, 'bathrooms': 1, 'floor_area': 30, 'monthly_rent': 9500,
                'status': 'vacant', **overrides}

    def test_add_unit(self):
        self.client.post(reverse('properties:owner_unit_create', args=[self.apt.pk]), self.unit_data())
        self.assertTrue(self.apt.units.filter(name='201', monthly_rent=9500).exists())

    def test_duplicate_unit_name_rejected(self):
        response = self.client.post(reverse('properties:owner_unit_create', args=[self.apt.pk]),
                                    self.unit_data(name='101'))
        self.assertIn('name', response.context['form'].errors)

    def test_same_unit_name_allowed_in_other_property(self):
        self.client.post(reverse('properties:owner_unit_create', args=[self.studio.pk]), self.unit_data(name='101'))
        self.assertTrue(self.studio.units.filter(name='101').exists())

    def test_rent_must_be_positive(self):
        response = self.client.post(reverse('properties:owner_unit_create', args=[self.apt.pk]),
                                    self.unit_data(monthly_rent=0))
        self.assertIn('monthly_rent', response.context['form'].errors)

    def test_edit_unit_keeping_its_name_and_delete(self):
        self.client.post(reverse('properties:owner_unit_edit', args=[self.vacant.pk]),
                         self.unit_data(name='101', status='occupied'))
        self.vacant.refresh_from_db()
        self.assertEqual(self.vacant.status, 'occupied')
        self.client.post(reverse('properties:owner_unit_delete', args=[self.vacant.pk]))
        self.assertFalse(Unit.objects.filter(pk=self.vacant.pk).exists())


class OwnerApplicationTests(OwnerTestCase):
    def setUp(self):
        super().setUp()
        self.tenant2 = make_user('tenant2', User.Role.TENANT)
        self.app1 = Application.objects.create(tenant=self.tenant, unit=self.vacant)
        self.app2 = Application.objects.create(tenant=self.tenant2, unit=self.vacant)
        self.their_app = Application.objects.create(tenant=self.tenant, unit=self.their_unit)

    def decide(self, app, decision):
        return self.client.post(reverse('properties:owner_application_decide', args=[app.pk, decision]))

    def test_lists_only_applications_for_own_units(self):
        response = self.client.get(reverse('properties:owner_applications'))
        self.assertEqual(set(response.context['applications']), {self.app1, self.app2})

    def test_approve_occupies_unit_and_rejects_others(self):
        self.decide(self.app1, 'approve')
        for obj in (self.app1, self.app2, self.vacant):
            obj.refresh_from_db()
        self.assertEqual(self.app1.status, 'approved')
        self.assertEqual(self.app2.status, 'rejected')
        self.assertEqual(self.vacant.status, 'occupied')

    def test_reject(self):
        self.decide(self.app1, 'reject')
        self.app1.refresh_from_db()
        self.vacant.refresh_from_db()
        self.assertEqual(self.app1.status, 'rejected')
        self.assertEqual(self.vacant.status, 'vacant')

    def test_cannot_approve_for_occupied_unit(self):
        Unit.objects.filter(pk=self.vacant.pk).update(status='occupied')
        self.decide(self.app1, 'approve')
        self.app1.refresh_from_db()
        self.assertEqual(self.app1.status, 'pending')

    def test_only_pending_can_be_decided(self):
        Application.objects.filter(pk=self.app1.pk).update(status='withdrawn')
        self.decide(self.app1, 'approve')
        self.app1.refresh_from_db()
        self.assertEqual(self.app1.status, 'withdrawn')

    def test_cannot_decide_another_owners_application(self):
        self.assertEqual(self.decide(self.their_app, 'approve').status_code, 404)
        self.their_app.refresh_from_db()
        self.assertEqual(self.their_app.status, 'pending')

    def test_unknown_decision_is_404(self):
        response = self.client.post(f'/owner/applications/{self.app1.pk}/delete/')
        self.assertEqual(response.status_code, 404)
