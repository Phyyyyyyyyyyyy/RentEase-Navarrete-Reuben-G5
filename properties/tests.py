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
