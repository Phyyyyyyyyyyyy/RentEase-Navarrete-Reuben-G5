from django.test import TestCase
from django.urls import reverse

from .models import User

PASSWORD = 'Str0ng-Pass!42'


def make_user(username, role, **extra):
    return User.objects.create_user(
        username=username, email=f'{username}@example.com', password=PASSWORD,
        first_name=username.title(), last_name='Test', role=role, **extra,
    )


class RegistrationTests(TestCase):
    url = reverse('accounts:register')

    def data(self, **overrides):
        data = {
            'first_name': 'Juan', 'last_name': 'Dela Cruz', 'username': 'juan',
            'email': 'juan@example.com', 'phone': '09170000000', 'role': 'tenant',
            'password1': PASSWORD, 'password2': PASSWORD,
        }
        data.update(overrides)
        return data

    def test_register_success_hashes_password(self):
        response = self.client.post(self.url, self.data(), follow=True)
        self.assertRedirects(response, reverse('accounts:login'))
        self.assertContains(response, 'Account created successfully')
        user = User.objects.get(username='juan')
        self.assertNotEqual(user.password, PASSWORD)
        self.assertTrue(user.password.startswith('pbkdf2_sha256$'))
        self.assertTrue(user.check_password(PASSWORD))

    def test_required_fields(self):
        response = self.client.post(self.url, {})
        self.assertEqual(User.objects.count(), 0)
        self.assertContains(response, 'This field is required.')

    def test_invalid_email(self):
        response = self.client.post(self.url, self.data(email='not-an-email'))
        self.assertContains(response, 'Enter a valid email address.')

    def test_duplicate_email_and_username(self):
        make_user('juan', User.Role.TENANT)
        response = self.client.post(self.url, self.data(email='JUAN@example.com'))
        self.assertContains(response, 'An account with this email already exists.')
        self.assertContains(response, 'already')  # username taken
        self.assertEqual(User.objects.count(), 1)

    def test_password_mismatch(self):
        response = self.client.post(self.url, self.data(password2='different-Pass9'))
        self.assertContains(response, 'didn')  # "The two password fields didn't match."
        self.assertFalse(User.objects.filter(username='juan').exists())

    def test_cannot_self_register_as_admin(self):
        self.client.post(self.url, self.data(role='admin'))
        self.assertFalse(User.objects.filter(username='juan').exists())


class LoginLogoutTests(TestCase):
    def setUp(self):
        self.user = make_user('tina', User.Role.TENANT)

    def test_login_with_username_or_email_goes_to_role_dashboard(self):
        for identifier in ('tina', 'tina@example.com'):
            response = self.client.post(reverse('accounts:login'), {'username': identifier, 'password': PASSWORD}, follow=True)
            self.assertRedirects(response, reverse('accounts:dashboard_tenant'))
            self.client.post(reverse('accounts:logout'))

    def test_invalid_credentials_show_error(self):
        response = self.client.post(reverse('accounts:login'), {'username': 'tina', 'password': 'wrong'})
        self.assertContains(response, 'Invalid username/email or password')
        self.assertNotIn('_auth_user_id', self.client.session)

    def test_logout_ends_session(self):
        self.client.force_login(self.user)
        self.client.post(reverse('accounts:logout'))
        self.assertNotIn('_auth_user_id', self.client.session)
        response = self.client.get(reverse('accounts:profile'))
        self.assertRedirects(response, f"{reverse('accounts:login')}?next={reverse('accounts:profile')}")


class RoleDashboardTests(TestCase):
    dashboards = {
        User.Role.ADMIN: 'accounts:dashboard_admin',
        User.Role.OWNER: 'accounts:dashboard_owner',
        User.Role.TENANT: 'accounts:dashboard_tenant',
        User.Role.STAFF: 'accounts:dashboard_staff',
    }

    def test_logged_out_users_are_sent_to_login(self):
        for name in [*self.dashboards.values(), 'accounts:dashboard', 'accounts:profile', 'accounts:profile_edit']:
            url = reverse(name)
            self.assertRedirects(self.client.get(url), f"{reverse('accounts:login')}?next={url}")

    def test_each_role_only_opens_its_own_dashboard(self):
        for role, own in self.dashboards.items():
            user = make_user(f'user_{role}', role)
            self.client.force_login(user)
            self.assertRedirects(self.client.get(reverse('accounts:dashboard')), reverse(own))
            self.assertEqual(self.client.get(reverse(own)).status_code, 200)
            for other_role, other in self.dashboards.items():
                if other_role != role:
                    response = self.client.get(reverse(other))
                    self.assertRedirects(response, reverse(own))
            self.client.logout()

    def test_superuser_gets_admin_role(self):
        admin = User.objects.create_superuser('root', 'root@example.com', PASSWORD)
        self.assertEqual(admin.role, User.Role.ADMIN)


class ProfileTests(TestCase):
    def setUp(self):
        self.user = make_user('alice', User.Role.TENANT, phone='111')
        self.other = make_user('bob', User.Role.OWNER, phone='222')
        self.client.force_login(self.user)

    def test_view_own_profile_only(self):
        response = self.client.get(reverse('accounts:profile'))
        self.assertContains(response, 'alice@example.com')
        self.assertNotContains(response, 'bob@example.com')

    def test_update_profile(self):
        response = self.client.post(reverse('accounts:profile_edit'), {
            'first_name': 'Alicia', 'last_name': 'Reyes', 'email': 'alicia@example.com', 'phone': '0999',
        }, follow=True)
        self.assertContains(response, 'Profile updated successfully.')
        self.user.refresh_from_db()
        self.assertEqual((self.user.first_name, self.user.email, self.user.phone), ('Alicia', 'alicia@example.com', '0999'))
        self.other.refresh_from_db()
        self.assertEqual(self.other.email, 'bob@example.com')

    def test_cannot_take_another_users_email(self):
        response = self.client.post(reverse('accounts:profile_edit'), {
            'first_name': 'A', 'last_name': 'B', 'email': 'bob@example.com', 'phone': '1',
        })
        self.assertContains(response, 'already used by another account')

    def test_profile_edit_cannot_change_role(self):
        self.client.post(reverse('accounts:profile_edit'), {
            'first_name': 'A', 'last_name': 'B', 'email': 'alice@example.com', 'phone': '1', 'role': 'admin',
        })
        self.user.refresh_from_db()
        self.assertEqual(self.user.role, User.Role.TENANT)
