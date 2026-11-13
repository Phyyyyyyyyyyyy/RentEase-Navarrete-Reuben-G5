from django.contrib import messages
from django.contrib.auth import views as auth_views
from django.contrib.auth.decorators import login_required
from django.db.models import Count
from django.shortcuts import redirect, render
from django.views.decorators.http import require_http_methods

from .decorators import role_required
from .forms import LoginForm, ProfileForm, RegistrationForm
from .models import User

Role = User.Role


def home(request):
    if request.user.is_authenticated:
        return redirect(request.user.dashboard_url_name)
    return redirect('accounts:login')


@require_http_methods(['GET', 'POST'])
def register(request):
    if request.user.is_authenticated:
        return redirect(request.user.dashboard_url_name)
    if request.method == 'POST':
        form = RegistrationForm(request.POST)
        if form.is_valid():
            form.save()  # UserCreationForm hashes the password via set_password()
            messages.success(request, 'Account created successfully. You can now sign in.')
            return redirect('accounts:login')
        messages.error(request, 'Please fix the errors below.')
    else:
        form = RegistrationForm()
    return render(request, 'accounts/register.html', {'form': form})


class LoginView(auth_views.LoginView):
    template_name = 'accounts/login.html'
    authentication_form = LoginForm
    redirect_authenticated_user = True

    def form_valid(self, form):
        response = super().form_valid(form)
        user = form.get_user()
        messages.success(self.request, f'Welcome back, {user.first_name or user.username}!')
        return response


class LogoutView(auth_views.LogoutView):
    def post(self, request, *args, **kwargs):
        response = super().post(request, *args, **kwargs)
        messages.info(request, 'You have been signed out.')
        return response


@login_required
def dashboard(request):
    """Send each user to the dashboard for their role."""
    return redirect(request.user.dashboard_url_name)


@role_required(Role.ADMIN)
def dashboard_admin(request):
    counts = dict(User.objects.values_list('role').annotate(n=Count('id')))
    context = {
        'total_users': User.objects.count(),
        'active_users': User.objects.filter(is_active=True).count(),
        'role_counts': [(label, counts.get(value, 0)) for value, label in Role.choices],
        'recent_users': User.objects.order_by('-date_joined')[:8],
    }
    return render(request, 'accounts/dashboards/admin.html', context)


@role_required(Role.OWNER)
def dashboard_owner(request):
    from properties.models import Application, Unit

    units = Unit.objects.filter(property__owner=request.user)
    pending = Application.objects.filter(unit__property__owner=request.user, status=Application.Status.PENDING)
    return render(request, 'accounts/dashboards/owner.html', {
        'property_count': request.user.properties.count(),
        'unit_count': units.count(),
        'vacant_units': units.filter(status=Unit.Status.VACANT).count(),
        'app_pending': pending.count(),
        'recent_pending': pending.select_related('tenant', 'unit__property')[:5],
    })


@role_required(Role.TENANT)
def dashboard_tenant(request):
    from properties.models import Application, Unit

    apps = request.user.applications
    return render(request, 'accounts/dashboards/tenant.html', {
        'vacant_units': Unit.objects.filter(status=Unit.Status.VACANT).count(),
        'app_total': apps.count(),
        'app_pending': apps.filter(status=Application.Status.PENDING).count(),
        'app_approved': apps.filter(status=Application.Status.APPROVED).count(),
    })


@role_required(Role.STAFF)
def dashboard_staff(request):
    return render(request, 'accounts/dashboards/staff.html', {
        'tenant_count': User.objects.filter(role=Role.TENANT, is_active=True).count(),
        'owner_count': User.objects.filter(role=Role.OWNER, is_active=True).count(),
    })


@login_required
def profile(request):
    # Always request.user: there is no user id in the URL, so nobody can view someone else's profile.
    return render(request, 'accounts/profile.html', {'profile_user': request.user})


@login_required
@require_http_methods(['GET', 'POST'])
def profile_edit(request):
    if request.method == 'POST':
        form = ProfileForm(request.POST, request.FILES, instance=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, 'Profile updated successfully.')
            return redirect('accounts:profile')
        messages.error(request, 'Please fix the errors below.')
    else:
        form = ProfileForm(instance=request.user)
    return render(request, 'accounts/profile_edit.html', {'form': form})
