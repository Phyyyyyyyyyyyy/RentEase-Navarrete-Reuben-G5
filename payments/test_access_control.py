"""Access control for payment receipts: only that tenant and the unit's owner can see one."""
import io
import os
import shutil
import tempfile

from django.core.files.uploadedfile import SimpleUploadedFile
from django.http import Http404
from django.test import RequestFactory, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from PIL import Image

from accounts.models import User
from config.urls import serve_public_media
from properties.models import Application, Property, Unit

from .models import Payment

PASSWORD = 'Str0ng-Pass!42'
MEDIA_ROOT = tempfile.mkdtemp(prefix='rentease-test-media-')


def make_user(username, role):
    return User.objects.create_user(username=username, email=f'{username}@example.com', password=PASSWORD, role=role)


def png_bytes():
    buffer = io.BytesIO()
    Image.new('RGB', (4, 4), 'white').save(buffer, format='PNG')
    return buffer.getvalue()


@override_settings(MEDIA_ROOT=MEDIA_ROOT)
class ReceiptAccessTests(TestCase):
    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(MEDIA_ROOT, ignore_errors=True)

    def setUp(self):
        self.owner = make_user('owner', User.Role.OWNER)
        self.tenant = make_user('tenant', User.Role.TENANT)
        self.other_owner = make_user('other_owner', User.Role.OWNER)
        self.other_tenant = make_user('other_tenant', User.Role.TENANT)
        self.staff = make_user('staff', User.Role.STAFF)
        prop = Property.objects.create(owner=self.owner, name='Lahug Apartments', property_type='apartment',
                                       address='Salinas Dr', city='Cebu City')
        unit = Unit.objects.create(property=prop, name='101', monthly_rent=8000, status='occupied')
        tenancy = Application.objects.create(tenant=self.tenant, unit=unit, status='approved',
                                             approved_at=timezone.now())
        self.payment = Payment.objects.create(
            tenancy=tenancy, amount=8000, method=Payment.Method.GCASH, reference_number='1234567890123',
            paid_on=timezone.localdate(), recorded_by=self.tenant,
            proof=SimpleUploadedFile('receipt.png', png_bytes(), content_type='image/png'),
        )
        self.url = reverse('payments:proof', args=[self.payment.pk])

    def test_tenant_can_view_own_receipt(self):
        self.client.force_login(self.tenant)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'image/png')
        self.assertIn('private', response['Cache-Control'])
        self.assertEqual(b''.join(response.streaming_content), png_bytes())

    def test_unit_owner_can_view_receipt(self):
        self.client.force_login(self.owner)
        self.assertEqual(self.client.get(self.url).status_code, 200)

    def test_other_tenant_gets_404(self):
        self.client.force_login(self.other_tenant)
        self.assertEqual(self.client.get(self.url).status_code, 404)

    def test_other_owner_gets_404(self):
        self.client.force_login(self.other_owner)
        self.assertEqual(self.client.get(self.url).status_code, 404)

    def test_wrong_role_is_redirected(self):
        self.client.force_login(self.staff)
        self.assertRedirects(self.client.get(self.url), reverse('accounts:dashboard_staff'))

    def test_login_required(self):
        response = self.client.get(self.url)
        self.assertRedirects(response, f"{reverse('accounts:login')}?next={self.url}")

    def test_payment_without_receipt_is_404(self):
        self.payment.proof = ''
        self.payment.save()
        self.client.force_login(self.tenant)
        self.assertEqual(self.client.get(self.url).status_code, 404)

    def test_post_not_allowed(self):
        self.client.force_login(self.tenant)
        self.assertEqual(self.client.post(self.url).status_code, 405)

    def test_owner_pages_link_to_protected_view(self):
        self.client.force_login(self.owner)
        response = self.client.get(reverse('payments:owner'))
        self.assertContains(response, self.url)
        self.assertNotContains(response, '/media/payment_proofs/')


@override_settings(MEDIA_ROOT=MEDIA_ROOT)
class PublicMediaTests(TestCase):
    """The development media server never hands out receipts directly."""

    def setUp(self):
        self.request = RequestFactory().get('/media/')

    def test_receipt_folder_is_blocked(self):
        for path in ('payment_proofs/receipt.png', 'x/../payment_proofs/receipt.png',
                     'Payment_Proofs/receipt.png', 'payment_proofs\\receipt.png', '/payment_proofs/receipt.png'):
            with self.subTest(path=path), self.assertRaises(Http404):
                serve_public_media(self.request, path)

    def test_other_uploads_are_served(self):
        folder = f'{MEDIA_ROOT}/profile_photos'
        os.makedirs(folder, exist_ok=True)
        with open(f'{folder}/me.png', 'wb') as f:
            f.write(png_bytes())
        response = serve_public_media(self.request, 'profile_photos/me.png')
        self.assertEqual(response.status_code, 200)
