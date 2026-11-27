"""Property owner pages: manage your own properties and units, and review applications.

Every query is filtered by `owner=request.user`, so an owner can never view or
change another owner's properties, units, or applications (they get a 404).
"""
from django.contrib import messages
from django.db import transaction
from django.db.models import Count, ProtectedError, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from accounts.decorators import role_required
from accounts.models import User

from .forms import PropertyForm, UnitForm
from .models import Application, Property, Unit

OWNER = User.Role.OWNER


def owned_properties(user):
    return Property.objects.filter(owner=user)


def delete_blocker(units):
    """Why `units` can't be deleted (a reason phrase), or None if they can.

    A unit with a current tenant, or with any rent payment history, is kept so
    tenancies and money records are never lost by accident.
    """
    from payments.models import Payment

    if Application.objects.filter(unit__in=units, unit__status=Unit.Status.OCCUPIED,
                                  status=Application.Status.APPROVED).exists():
        return 'has a current tenant. Mark the unit vacant after they move out, then delete it'
    if Payment.objects.filter(tenancy__unit__in=units).exists():
        return 'has rent payment records, which must be kept'
    return None


# ---------------------------------------------------------------- properties

@role_required(OWNER)
def property_list(request):
    properties = (
        owned_properties(request.user)
        .annotate(
            unit_count=Count('units', distinct=True),
            vacant_count=Count('units', filter=Q(units__status=Unit.Status.VACANT), distinct=True),
            pending_count=Count('units__applications',
                                filter=Q(units__applications__status=Application.Status.PENDING), distinct=True),
        )
        .order_by('name')
    )
    return render(request, 'properties/owner/property_list.html', {'properties': properties})


@role_required(OWNER)
def property_create(request):
    form = PropertyForm(request.POST or None, owner=request.user)
    if request.method == 'POST':
        if form.is_valid():
            prop = form.save(commit=False)
            prop.owner = request.user
            prop.save()
            messages.success(request, f'{prop.name} added. Now add its units so tenants can apply.')
            return redirect('properties:owner_property', pk=prop.pk)
        messages.error(request, 'Please fix the errors below.')
    return render(request, 'properties/owner/property_form.html', {'form': form})


@role_required(OWNER)
def property_manage(request, pk):
    prop = get_object_or_404(owned_properties(request.user), pk=pk)
    units = prop.units.annotate(
        pending_count=Count('applications', filter=Q(applications__status=Application.Status.PENDING)),
    ).order_by('name')
    return render(request, 'properties/owner/property_manage.html', {'property': prop, 'units': units})


@role_required(OWNER)
def property_edit(request, pk):
    prop = get_object_or_404(owned_properties(request.user), pk=pk)
    form = PropertyForm(request.POST or None, instance=prop, owner=request.user)
    if request.method == 'POST':
        if form.is_valid():
            form.save()
            messages.success(request, f'{prop.name} updated.')
            return redirect('properties:owner_property', pk=prop.pk)
        messages.error(request, 'Please fix the errors below.')
    return render(request, 'properties/owner/property_form.html', {'form': form, 'property': prop})


@role_required(OWNER)
@require_POST
def property_delete(request, pk):
    prop = get_object_or_404(owned_properties(request.user), pk=pk)
    name = prop.name
    reason = delete_blocker(prop.units.all())
    if reason:
        messages.error(request, f"{name} can't be deleted: one of its units {reason}.")
        return redirect('properties:owner_property', pk=prop.pk)
    try:
        prop.delete()  # cascades to its units and their applications
    except ProtectedError:  # a payment was recorded between the check and the delete
        messages.error(request, f"{name} can't be deleted: one of its units has rent payment records.")
        return redirect('properties:owner_property', pk=prop.pk)
    messages.success(request, f'{name} deleted.')
    return redirect('properties:owner_properties')


# --------------------------------------------------------------------- units

@role_required(OWNER)
def unit_create(request, pk):
    prop = get_object_or_404(owned_properties(request.user), pk=pk)
    form = UnitForm(request.POST or None, property_obj=prop)
    if request.method == 'POST':
        if form.is_valid():
            unit = form.save(commit=False)
            unit.property = prop
            unit.save()
            messages.success(request, f'{unit.name} added to {prop.name}.')
            return redirect('properties:owner_property', pk=prop.pk)
        messages.error(request, 'Please fix the errors below.')
    return render(request, 'properties/owner/unit_form.html', {'form': form, 'property': prop})


@role_required(OWNER)
def unit_edit(request, pk):
    unit = get_object_or_404(Unit.objects.select_related('property'), pk=pk, property__owner=request.user)
    form = UnitForm(request.POST or None, instance=unit, property_obj=unit.property)
    if request.method == 'POST':
        if form.is_valid():
            form.save()
            messages.success(request, f'{unit.name} updated.')
            return redirect('properties:owner_property', pk=unit.property_id)
        messages.error(request, 'Please fix the errors below.')
    return render(request, 'properties/owner/unit_form.html', {'form': form, 'property': unit.property, 'unit': unit})


@role_required(OWNER)
@require_POST
def unit_delete(request, pk):
    unit = get_object_or_404(Unit, pk=pk, property__owner=request.user)
    property_id, name = unit.property_id, unit.name
    reason = delete_blocker([unit])
    if reason:
        messages.error(request, f"{name} can't be deleted: it {reason}.")
        return redirect('properties:owner_property', pk=property_id)
    try:
        unit.delete()
    except ProtectedError:
        messages.error(request, f"{name} can't be deleted: it has rent payment records.")
        return redirect('properties:owner_property', pk=property_id)
    messages.success(request, f'{name} deleted.')
    return redirect('properties:owner_property', pk=property_id)


# -------------------------------------------------------------- applications

@role_required(OWNER)
def application_list(request):
    status = request.GET.get('status', Application.Status.PENDING)
    applications = (
        Application.objects.filter(unit__property__owner=request.user)
        .select_related('tenant', 'unit__property')
    )
    counts = {s: 0 for s, _ in Application.Status.choices}
    counts.update(dict(applications.values_list('status').annotate(n=Count('id')).order_by()))
    if status in counts:
        applications = applications.filter(status=status)
    else:
        status = 'all'
    return render(request, 'properties/owner/application_list.html', {
        'applications': applications,
        'status': status,
        'status_tabs': [(s, label, counts[s]) for s, label in Application.Status.choices]
                       + [('all', 'All', sum(counts.values()))],
    })


@role_required(OWNER)
@require_POST
def application_decide(request, pk, decision):
    # Return to the tab the owner was on (only known tab values are accepted).
    tab = request.POST.get('tab', '')
    back = redirect(reverse('properties:owner_applications')
                    + (f'?status={tab}' if tab in {*Application.Status.values, 'all'} else ''))
    with transaction.atomic():
        application = get_object_or_404(
            Application.objects.select_related('tenant', 'unit').select_for_update(),
            pk=pk, unit__property__owner=request.user,
        )
        tenant_name = application.tenant.get_full_name() or application.tenant.username
        if application.status != Application.Status.PENDING:
            messages.error(request, 'Only pending applications can be approved or rejected.')
            return back

        if decision == 'reject':
            application.status = Application.Status.REJECTED
            application.save(update_fields=['status', 'updated_at'])
            messages.success(request, f"{tenant_name}'s application for {application.unit.name} rejected.")
            return back

        unit = Unit.objects.select_for_update().get(pk=application.unit_id)
        if not unit.is_vacant:
            messages.error(request, f'{unit.name} is already occupied. Mark it vacant first, or reject this application.')
            return back
        application.status = Application.Status.APPROVED
        application.approved_at = timezone.now()
        application.save(update_fields=['status', 'approved_at', 'updated_at'])
        unit.status = Unit.Status.OCCUPIED
        unit.save(update_fields=['status'])
        # The unit is taken now, so every other pending application for it is rejected.
        others = unit.applications.filter(status=Application.Status.PENDING).exclude(pk=application.pk)
        rejected = others.update(status=Application.Status.REJECTED, updated_at=timezone.now())

    note = f' {rejected} other pending application{"s were" if rejected != 1 else " was"} rejected.' if rejected else ''
    messages.success(request, f"{tenant_name} approved for {unit.name}. The unit is now marked occupied.{note}")
    return back
