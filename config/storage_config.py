"""Where uploaded files (profile photos, GCash QR codes, payment receipts) are stored.

Fixes PD2 issue ISS-01: uploads used to be saved only in the local `media/`
folder, which isn't in Git, so a photo uploaded on one computer was a broken
image on every other computer.

With the five SUPABASE_S3_* settings in `.env`, uploads go to a private
Supabase Storage bucket through its S3-compatible API (django-storages), so
every computer sees the same files. The bucket is private: pages show images
through signed links that expire after an hour, so a copied link stops working.

Without those settings, uploads stay in the local `media/` folder.
"""
from django.core.exceptions import ImproperlyConfigured

S3_SETTINGS = (
    'SUPABASE_S3_ENDPOINT',
    'SUPABASE_S3_REGION',
    'SUPABASE_S3_ACCESS_KEY_ID',
    'SUPABASE_S3_SECRET_ACCESS_KEY',
    'SUPABASE_S3_BUCKET',
)
SIGNED_URL_SECONDS = 3600

LOCAL_STORAGE = {'BACKEND': 'django.core.files.storage.FileSystemStorage'}


def default_storage(getenv):
    """Return the STORAGES['default'] entry, reading settings with `getenv(name)`."""
    values = {name: (getenv(name) or '').strip() for name in S3_SETTINGS}
    present = [name for name, value in values.items() if value]
    if not present:
        return LOCAL_STORAGE
    missing = [name for name in S3_SETTINGS if not values[name]]
    if missing:
        # Half-configured storage would silently save uploads locally again (ISS-01).
        raise ImproperlyConfigured(
            f'Supabase Storage is partly configured. Add these to .env: {", ".join(missing)}'
        )
    return {
        'BACKEND': 'storages.backends.s3.S3Storage',
        'OPTIONS': {
            'endpoint_url': values['SUPABASE_S3_ENDPOINT'],
            'region_name': values['SUPABASE_S3_REGION'],
            'access_key': values['SUPABASE_S3_ACCESS_KEY_ID'],
            'secret_key': values['SUPABASE_S3_SECRET_ACCESS_KEY'],
            'bucket_name': values['SUPABASE_S3_BUCKET'],
            'addressing_style': 'path',  # Supabase serves buckets at /<bucket>/..., not <bucket>.host
            'signature_version': 's3v4',
            'querystring_auth': True,  # private bucket: every URL is signed...
            'querystring_expire': SIGNED_URL_SECONDS,  # ...and expires
            'default_acl': None,
            'file_overwrite': False,  # two uploads named photo.png never replace each other
        },
    }
