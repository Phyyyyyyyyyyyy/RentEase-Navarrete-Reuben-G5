"""Custom error pages: no Django debug or traceback page is ever shown.

Django runs tests with DEBUG=False, which is how these pages behave for real users.
"""
from django.test import Client, TestCase, override_settings
from django.urls import path, reverse

from accounts.models import User
from config import urls as project_urls
from properties.models import Property


def broken_view(request):
    raise RuntimeError('Simulated server error')


# The real URLs plus one view that always crashes, to trigger a 500.
urlpatterns = [path('test-500/', broken_view)] + project_urls.urlpatterns


class ErrorPageTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user('owner', 'owner@example.com', 'Str0ng-Pass!42', role=User.Role.OWNER)
        self.other = User.objects.create_user('other', 'other@example.com', 'Str0ng-Pass!42', role=User.Role.OWNER)
        self.theirs = Property.objects.create(owner=self.other, name='Not Mine', property_type='house',
                                              address='Talamban', city='Cebu City')

    def assert_custom_404(self, response):
        self.assertEqual(response.status_code, 404)
        self.assertTemplateUsed(response, '404.html')
        self.assertContains(response, 'Page not found', status_code=404)
        self.assertNotContains(response, 'Traceback', status_code=404)
        self.assertNotContains(response, 'URLconf', status_code=404)

    def test_unknown_url_shows_custom_404(self):
        self.assert_custom_404(self.client.get('/this-page-does-not-exist/'))

    def test_missing_record_id_shows_custom_404(self):
        self.client.force_login(self.owner)
        self.assert_custom_404(self.client.get(reverse('properties:owner_property', args=[999999])))

    def test_other_users_record_shows_custom_404(self):
        self.client.force_login(self.owner)
        self.assert_custom_404(self.client.get(reverse('properties:owner_property', args=[self.theirs.pk])))

    @override_settings(ROOT_URLCONF='config.test_error_pages')
    def test_server_error_shows_custom_500(self):
        client = Client(raise_request_exception=False)
        response = client.get('/test-500/')
        self.assertEqual(response.status_code, 500)
        self.assertTemplateUsed(response, '500.html')
        self.assertContains(response, 'Something went wrong', status_code=500)
        self.assertNotContains(response, 'RuntimeError', status_code=500)
        self.assertNotContains(response, 'Simulated server error', status_code=500)

    def test_missing_csrf_token_shows_custom_403(self):
        client = Client(enforce_csrf_checks=True)
        response = client.post(reverse('accounts:login'), {'username': 'owner', 'password': 'Str0ng-Pass!42'})
        self.assertEqual(response.status_code, 403)
        self.assertTemplateUsed(response, '403_csrf.html')
        self.assertContains(response, 'This form has expired', status_code=403)
