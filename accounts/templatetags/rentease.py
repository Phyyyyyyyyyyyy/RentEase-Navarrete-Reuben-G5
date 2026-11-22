import os

from django import template
from django.contrib.staticfiles import finders
from django.templatetags.static import static
from django.utils.safestring import mark_safe

register = template.Library()

# Same line icons as the original React prototype (components/Icons.jsx).
ICONS = {
    'home': '<path d="M3 11.5 12 4l9 7.5"/><path d="M5 10.5V20h14v-9.5"/><path d="M9 20v-6h6v6"/>',
    'users': '<path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M22 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/>',
    'building': '<rect x="4" y="3" width="16" height="18" rx="2"/><path d="M9 21v-4h6v4M8 7h2M14 7h2M8 11h2M14 11h2"/>',
    'search': '<circle cx="11" cy="11" r="7"/><path d="m20 20-4-4"/>',
    'file': '<path d="M14 2H6a2 2 0 0 0-2 2v16h16V8z"/><path d="M14 2v6h6M8 13h8M8 17h5"/>',
    'user': '<circle cx="12" cy="8" r="4"/><path d="M4 21a8 8 0 0 1 16 0"/>',
    'logout': '<path d="M10 17l5-5-5-5M15 12H3"/><path d="M21 19V5a2 2 0 0 0-2-2h-6"/>',
    'edit': '<path d="M12 20h9"/><path d="M16.5 3.5a2.12 2.12 0 0 1 3 3L8 18l-4 1 1-4z"/>',
    'menu': '<path d="M4 6h16M4 12h16M4 18h16"/>',
    'check': '<path d="m5 12 4 4L19 6"/>',
    'clock': '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>',
    'arrow': '<path d="M5 12h14M13 6l6 6-6 6"/>',
    'shield': '<path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/><path d="m9 12 2 2 4-4"/>',
    'key': '<circle cx="8" cy="15" r="4"/><path d="m11 12 9-9M15 8l2 2M17 6l2 2"/>',
    'chevron': '<path d="m9 18 6-6-6-6"/>',
    'wallet': '<path d="M19 7V5a2 2 0 0 0-2-2H5a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-3"/><path d="M21 9h-5a3 3 0 0 0 0 6h5z"/><circle cx="16" cy="12" r=".6"/>',
    'phone': '<rect x="7" y="2" width="10" height="20" rx="2"/><path d="M11 18h2"/>',
    'cash': '<rect x="2" y="6" width="20" height="12" rx="2"/><circle cx="12" cy="12" r="2.5"/><path d="M6 10v4M18 10v4"/>',
    'sun': '<circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M4.93 4.93l1.41 1.41M17.66 17.66l1.41 1.41M2 12h2M20 12h2M4.93 19.07l1.41-1.41M17.66 6.34l1.41-1.41"/>',
    'moon': '<path d="M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8z"/>',
    'monitor': '<rect x="2" y="4" width="20" height="13" rx="2"/><path d="M8 21h8M12 17v4"/>',
}


@register.simple_tag
def icon(name, size=20):
    paths = ICONS.get(name, ICONS['home'])
    return mark_safe(
        f'<svg width="{int(size)}" height="{int(size)}" viewBox="0 0 24 24" fill="none" '
        f'stroke="currentColor" stroke-width="1.8" stroke-linecap="round" '
        f'stroke-linejoin="round" aria-hidden="true">{paths}</svg>'
    )


ROLE_MENUS = {
    'admin': [
        ('accounts:dashboard_admin', 'Dashboard', 'home'),
        ('admin:index', 'Users & Access', 'users'),
        (None, 'Properties & Units', 'building'),
        (None, 'Applications', 'file'),
        ('accounts:profile', 'My Profile', 'user'),
    ],
    'owner': [
        ('accounts:dashboard_owner', 'Dashboard', 'home'),
        ('properties:owner_properties', 'My Properties', 'building'),
        ('properties:owner_applications', 'Applications', 'file'),
        ('payments:owner', 'Rent Payments', 'wallet'),
        ('accounts:profile', 'My Profile', 'user'),
    ],
    'tenant': [
        ('accounts:dashboard_tenant', 'Dashboard', 'home'),
        ('properties:browse', 'Browse Properties', 'search'),
        ('properties:my_applications', 'My Applications', 'file'),
        ('payments:tenant', 'Rent & Payments', 'wallet'),
        ('accounts:profile', 'My Profile', 'user'),
    ],
    'staff': [
        ('accounts:dashboard_staff', 'Dashboard', 'home'),
        (None, 'Property Records', 'building'),
        (None, 'Applications', 'file'),
        ('accounts:profile', 'My Profile', 'user'),
    ],
}


@register.simple_tag
def versioned_static(path):
    """Static URL with the file's modified time appended (?v=...), so browsers fetch
    the new file after every rebuild instead of reusing a stale cached copy."""
    url = static(path)
    found = finders.find(path)
    return f'{url}?v={int(os.path.getmtime(found))}' if found else url


@register.filter
def startswith(value, prefix):
    return bool(prefix) and str(value).startswith(str(prefix))


@register.filter
def peso(value):
    """Format a number as Philippine pesos, e.g. 12000 -> ₱12,000."""
    try:
        number = float(value)
    except (TypeError, ValueError):
        return '—'
    # Whole amounts stay short (₱8,500); partial payments keep their centavos (₱1,250.50).
    return f'₱{number:,.0f}' if number == int(number) else f'₱{number:,.2f}'


@register.simple_tag
def pending_payments(user):
    """GCash payments waiting for the owner to confirm them."""
    if getattr(user, 'role', '') != 'owner':
        return 0
    from payments.models import Payment
    return Payment.objects.filter(tenancy__unit__property__owner=user, status=Payment.Status.PENDING).count()


@register.simple_tag
def pending_applications(user):
    """Pending applications needing attention: a tenant's own applications awaiting
    review, or for an owner, applications for their units awaiting a decision."""
    from properties.models import Application
    role = getattr(user, 'role', '')
    if role == 'tenant':
        return user.applications.filter(status=Application.Status.PENDING).count()
    if role == 'owner':
        return Application.objects.filter(unit__property__owner=user, status=Application.Status.PENDING).count()
    return 0


@register.simple_tag
def role_menu(user):
    """Sidebar items for the user's role. A None url means the module is not built yet."""
    return ROLE_MENUS.get(getattr(user, 'role', ''), [])
