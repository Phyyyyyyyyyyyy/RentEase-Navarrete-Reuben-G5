from django.core.management.base import BaseCommand

from accounts.models import User

DEMO_USERS = [
    ('admin', 'admin@rentease.local', 'System', 'Administrator', User.Role.ADMIN, '0917 000 0001'),
    ('owner', 'owner@rentease.local', 'Maria', 'Santos', User.Role.OWNER, '0917 000 0002'),
    ('tenant', 'tenant@rentease.local', 'Juan', 'Dela Cruz', User.Role.TENANT, '0917 000 0003'),
    ('staff', 'staff@rentease.local', 'Ana', 'Reyes', User.Role.STAFF, '0917 000 0004'),
]


class Command(BaseCommand):
    help = 'Create one demo account per role (password: RentEase@2026). Skips accounts that already exist.'

    def add_arguments(self, parser):
        parser.add_argument('--password', default='RentEase@2026', help='Password for all demo accounts.')

    def handle(self, *args, password, **options):
        for username, email, first, last, role, phone in DEMO_USERS:
            if User.objects.filter(username=username).exists():
                self.stdout.write(f'  skip   {username} (already exists)')
                continue
            user = User(username=username, email=email, first_name=first, last_name=last, role=role, phone=phone)
            user.set_password(password)  # hashed, never stored as plain text
            user.save()
            self.stdout.write(self.style.SUCCESS(f'  create {username} ({user.get_role_display()})'))
        self.stdout.write(f'Demo password: {password}')
