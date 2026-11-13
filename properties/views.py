from django.contrib import messages
from django.db.models import Count, Min, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from accounts.decorators import role_required
from accounts.models import User

from .forms import ApplicationForm, BrowseFilterForm
from .models import Application, Property, Unit

TENANT = User.Role.TENANT
VACANT = Q(units__status=Unit.Status.VACANT)


@role_required(TENANT)
def browse(request):
    form = BrowseFilterForm(request.GET or None)
    properties = (
        Property.objects
        .annotate(vacant_count=Count('units', filter=VACANT), min_rent=Min('units__monthly_rent', filter=VACANT))
        .filter(vacant_count__gt=0)
        .order_by('name')  # Meta.ordering is not applied to aggregate (GROUP BY) queries
    )
    if form.is_valid():
        q, ptype, max_rent = form.cleaned_data['q'], form.cleaned_data['type'], form.cleaned_data['max_rent']
        if q:
            properties = properties.filter(Q(name__icontains=q) | Q(address__icontains=q) | Q(city__icontains=q))
        if ptype:
            properties = properties.filter(property_type=ptype)
        if max_rent is not None:
            properties = properties.filter(min_rent__lte=max_rent)
    return render(request, 'properties/browse.html', {
        'form': form,
        'properties': properties,
        'filtered': bool(request.GET),
    })


@role_required(TENANT)
def property_detail(request, pk):
    property_obj = get_object_or_404(Property.objects.select_related('owner'), pk=pk)
    if request.method == 'POST':
        form = ApplicationForm(request.POST, property_obj=property_obj, tenant=request.user)
        if form.is_valid():
            application = form.save(commit=False)
            application.tenant = request.user
            application.save()
            messages.success(request, f'Application for {application.unit.name} submitted. The owner will review it soon.')
            return redirect('properties:my_applications')
        messages.error(request, 'Please fix the errors below.')
    else:
        form = ApplicationForm(property_obj=property_obj, tenant=request.user)
    pending_unit_ids = set(
        request.user.applications.filter(status=Application.Status.PENDING, unit__property=property_obj)
        .values_list('unit_id', flat=True)
    )
    return render(request, 'properties/property_detail.html', {
        'property': property_obj,
        'units': property_obj.units.all(),
        'form': form,
        'pending_unit_ids': pending_unit_ids,
    })


@role_required(TENANT)
def my_applications(request):
    status = request.GET.get('status', '')
    applications = request.user.applications.select_related('unit__property')
    counts = {s: 0 for s, _ in Application.Status.choices}
    counts.update(dict(applications.values_list('status').annotate(n=Count('id')).order_by()))
    if status in counts:
        applications = applications.filter(status=status)
    return render(request, 'properties/my_applications.html', {
        'applications': applications,
        'status': status,
        'status_tabs': [('', 'All', sum(counts.values()))] + [(s, label, counts[s]) for s, label in Application.Status.choices],
    })


@role_required(TENANT)
@require_POST
def withdraw_application(request, pk):
    # Filtering by tenant means a tenant can only withdraw their own applications.
    application = get_object_or_404(Application, pk=pk, tenant=request.user)
    if application.can_withdraw:
        application.status = Application.Status.WITHDRAWN
        application.save(update_fields=['status', 'updated_at'])
        messages.success(request, f'Application for {application.unit.name} withdrawn.')
    else:
        messages.error(request, 'Only pending applications can be withdrawn.')
    return redirect('properties:my_applications')
