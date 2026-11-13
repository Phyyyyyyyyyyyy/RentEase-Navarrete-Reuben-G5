from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    """Custom user with a RentEase role, contact number, and profile photo.

    Passwords are hashed by Django's auth system (set_password); they are
    never stored in plain text.
    """

    class Role(models.TextChoices):
        ADMIN = 'admin', 'Admin'
        OWNER = 'owner', 'Property Owner'
        TENANT = 'tenant', 'Tenant'
        STAFF = 'staff', 'Staff'

    # Roles a visitor may pick on the public registration form.
    # Admin and Staff accounts are created by an administrator.
    SELF_REGISTER_ROLES = (Role.TENANT, Role.OWNER)

    email = models.EmailField('email address', unique=True)
    role = models.CharField(max_length=20, choices=Role.choices, default=Role.TENANT)
    phone = models.CharField('contact number', max_length=20, blank=True)
    profile_photo = models.ImageField(upload_to='profile_photos/', blank=True)

    def save(self, *args, **kwargs):
        # Keep the Admin role and Django's admin flags in sync:
        # `createsuperuser` accounts get the Admin dashboard, and Admin-role
        # users can open the Django admin site to manage users.
        if self.is_superuser:
            self.role = self.Role.ADMIN
        if self.role == self.Role.ADMIN:
            self.is_staff = True
            self.is_superuser = True
        super().save(*args, **kwargs)

    @property
    def initials(self):
        name = self.get_full_name() or self.username
        return ''.join(part[0] for part in name.split()[:2]).upper()

    @property
    def dashboard_url_name(self):
        return f'accounts:dashboard_{self.role}'

    def __str__(self):
        return f'{self.username} ({self.get_role_display()})'
