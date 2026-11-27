"""Copy files from the local media/ folder to the configured storage (Supabase Storage).

Run once after adding the SUPABASE_S3_* settings to .env, so photos uploaded
before the switch keep working (ISS-01). Files already in the bucket are skipped,
so it's safe to run again.

    python manage.py upload_local_media
"""
from pathlib import Path

from django.conf import settings
from django.core.files import File
from django.core.files.storage import FileSystemStorage, default_storage
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = 'Upload files from the local media/ folder to Supabase Storage.'

    def handle(self, *args, **options):
        if isinstance(default_storage, FileSystemStorage):  # the lazy proxy reports the real class
            raise CommandError('Uploads are still stored locally. Add the SUPABASE_S3_* settings to .env first.')
        root = Path(settings.MEDIA_ROOT)
        if not root.is_dir():
            self.stdout.write('No local media/ folder: nothing to upload.')
            return
        uploaded = skipped = 0
        for path in sorted(p for p in root.rglob('*') if p.is_file()):
            name = path.relative_to(root).as_posix()
            if default_storage.exists(name):
                skipped += 1
                continue
            with path.open('rb') as f:
                saved = default_storage.save(name, File(f))
            if saved != name:  # file_overwrite=False could rename it; the database must point at the same name
                default_storage.delete(saved)
                raise CommandError(f'{name} could not be stored under the same name.')
            uploaded += 1
            self.stdout.write(f'Uploaded {name}')
        self.stdout.write(self.style.SUCCESS(f'Done: {uploaded} uploaded, {skipped} already in storage.'))
