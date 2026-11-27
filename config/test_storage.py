"""Upload storage settings (ISS-01). No network: signed URLs are created locally by boto3."""
from django.core.exceptions import ImproperlyConfigured
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.test import SimpleTestCase
from storages.backends.s3 import S3Storage

from config.storage_config import LOCAL_STORAGE, S3_SETTINGS, SIGNED_URL_SECONDS, default_storage as storage_for

FAKE_ENV = {
    'SUPABASE_S3_ENDPOINT': 'https://example-ref.storage.supabase.co/storage/v1/s3',
    'SUPABASE_S3_REGION': 'ap-south-1',
    'SUPABASE_S3_ACCESS_KEY_ID': 'test-key-id',
    'SUPABASE_S3_SECRET_ACCESS_KEY': 'test-secret',
    'SUPABASE_S3_BUCKET': 'media',
}


class StorageConfigTests(SimpleTestCase):
    def test_all_settings_use_private_supabase_bucket(self):
        config = storage_for(FAKE_ENV.get)
        self.assertEqual(config['BACKEND'], 'storages.backends.s3.S3Storage')
        options = config['OPTIONS']
        self.assertEqual(options['bucket_name'], 'media')
        self.assertEqual(options['endpoint_url'], FAKE_ENV['SUPABASE_S3_ENDPOINT'])
        self.assertTrue(options['querystring_auth'])
        self.assertIsNone(options['default_acl'])
        self.assertFalse(options['file_overwrite'])

    def test_no_settings_use_local_folder(self):
        self.assertEqual(storage_for({}.get), LOCAL_STORAGE)

    def test_partial_settings_are_an_error(self):
        for missing in S3_SETTINGS:
            env = {k: v for k, v in FAKE_ENV.items() if k != missing}
            with self.subTest(missing=missing), self.assertRaisesMessage(ImproperlyConfigured, missing):
                storage_for(env.get)

    def test_blank_values_count_as_missing(self):
        env = {**FAKE_ENV, 'SUPABASE_S3_SECRET_ACCESS_KEY': '   '}
        with self.assertRaisesMessage(ImproperlyConfigured, 'SUPABASE_S3_SECRET_ACCESS_KEY'):
            storage_for(env.get)

    def test_file_links_are_signed_and_expire(self):
        storage = S3Storage(**storage_for(FAKE_ENV.get)['OPTIONS'])
        url = storage.url('payment_proofs/receipt.png')
        self.assertTrue(url.startswith('https://example-ref.storage.supabase.co/storage/v1/s3/media/payment_proofs/'))
        self.assertIn('X-Amz-Signature=', url)
        self.assertIn(f'X-Amz-Expires={SIGNED_URL_SECONDS}', url)


class TestRunStorageTests(SimpleTestCase):
    def test_tests_never_upload_to_the_real_bucket(self):
        self.assertEqual(default_storage.__class__.__name__, 'InMemoryStorage')
        name = default_storage.save('profile_photos/test.png', ContentFile(b'x'))
        self.assertTrue(default_storage.exists(name))
        default_storage.delete(name)
