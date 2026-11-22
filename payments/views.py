"""Rent payment pages for tenants and property owners.

Tenant queries are filtered by `tenant=request.user` and owner queries by
`unit__property__owner=request.user`, so nobody can see or change another
person's payments (they get a 404).
"""
from decimal import Decimal, InvalidOperation

from django.contrib import messages
from django.db import IntegrityError, transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from accounts.decorators import role_required
from accounts.models import User

from .billing import build_ledger, is_active, latest_approved_by_unit, ledgers_for, tenancies_for
from .forms import GCashPaymentForm, RecordPaymentForm, RejectPaymentForm
from .models import Payment

TENANT, OWNER = User.Role.TENANT, User.Role.OWNER


def _ledger(tenancy):
    return build_ledger(tenancy, active=is_active(tenancy, latest_approved_by_unit([tenancy.unit_id])))


# -------------------------------------------------------------------- tenant

@role_required(TENANT)
def tenant_payments(request):
    ledgers = ledgers_for(tenancies_for(tenant=request.user))
    history = (Payment.objects.filter(tenancy__tenant=request.user)
               .select_related('tenancy__unit__property'))
    return render(request, 'payments/tenant_payments.html', {'ledgers': ledgers, 'history': history})


@role_required(TENANT)
def gcash_pay(request, pk):
    tenancy = get_object_or_404(tenancies_for(tenant=request.user), pk=pk)
    owner = tenancy.unit.property.owner
    if not owner.accepts_gcash:
        messages.error(request, f'{owner.get_full_name() or owner.username} has not set up GCash yet. '
                                'Pay them in person, and they will record it here.')
        return redirect('payments:tenant')
    ledger = _ledger(tenancy)

    form = GCashPaymentForm(request.POST or None, request.FILES or None,
                            initial={'amount': ledger.suggested_amount, 'paid_on': timezone.localdate()})
    if request.method == 'POST':
        if form.is_valid():
            payment = form.save(commit=False)
            payment.tenancy, payment.method, payment.recorded_by = tenancy, Payment.Method.GCASH, request.user
            try:
                payment.save()
            except IntegrityError:  # same reference submitted at the same moment by another request
                form.add_error('reference_number', 'This reference number has already been submitted.')
            else:
                messages.success(request, f'GCash payment of ₱{payment.amount:,.2f} submitted. '
                                          'It will count toward your balance once the owner confirms it.')
                return redirect('payments:tenant')
        messages.error(request, 'Please fix the errors below.')
    return render(request, 'payments/gcash_pay.html', {'ledger': ledger, 'owner': owner, 'form': form})


@role_required(TENANT)
@require_POST
def cancel_submission(request, pk):
    payment = get_object_or_404(Payment, pk=pk, tenancy__tenant=request.user, recorded_by=request.user,
                                status=Payment.Status.PENDING)
    payment.delete()
    messages.success(request, 'GCash submission cancelled.')
    return redirect('payments:tenant')


# --------------------------------------------------------------------- owner

@role_required(OWNER)
def owner_payments(request):
    ledgers = ledgers_for(tenancies_for(unit__property__owner=request.user))
    ledgers.sort(key=lambda l: (not l.active, -l.balance, l.tenancy.unit.property.name, l.tenancy.unit.name))
    pending = (Payment.objects.filter(tenancy__unit__property__owner=request.user, status=Payment.Status.PENDING)
               .select_related('tenancy__tenant', 'tenancy__unit__property').order_by('created_at'))
    return render(request, 'payments/owner_payments.html', {
        'ledgers': ledgers,
        'pending': pending,
        'outstanding': sum(l.balance for l in ledgers),
        'gcash_ready': request.user.accepts_gcash,
    })


@role_required(OWNER)
def owner_tenancy(request, pk):
    tenancy = get_object_or_404(tenancies_for(unit__property__owner=request.user), pk=pk)
    ledger = _ledger(tenancy)
    try:  # "Record ₱X" links on the month list prefill the amount
        amount = Decimal(request.GET['amount']).quantize(Decimal('0.01'))
    except (KeyError, InvalidOperation):
        amount = ledger.suggested_amount
    form = RecordPaymentForm(request.POST or None, initial={
        'amount': amount, 'method': Payment.Method.CASH, 'paid_on': timezone.localdate(),
    })
    if request.method == 'POST':
        if form.is_valid():
            payment = form.save(commit=False)
            payment.tenancy, payment.recorded_by = tenancy, request.user
            payment.status, payment.reviewed_at = Payment.Status.CONFIRMED, timezone.now()
            try:
                payment.save()
            except IntegrityError:
                form.add_error('reference_number', 'This GCash reference number is already recorded.')
            else:
                after = _ledger(tenancy)
                status = (f'₱{after.balance:,.2f} still owed.' if after.balance
                          else f'Fully paid, with ₱{after.credit:,.2f} credit for future months.' if after.credit
                          else 'Fully paid.')
                messages.success(request, f'Recorded ₱{payment.amount:,.2f} from '
                                          f'{tenancy.tenant.get_full_name() or tenancy.tenant.username}. {status}')
                return redirect('payments:owner_tenancy', pk=tenancy.pk)
        messages.error(request, 'Please fix the errors below.')
    return render(request, 'payments/owner_tenancy.html', {
        'ledger': ledger, 'form': form,
        'history': tenancy.payments.select_related('recorded_by'),
    })


@role_required(OWNER)
@require_POST
def owner_review(request, pk, decision):
    with transaction.atomic():
        payment = get_object_or_404(
            Payment.objects.select_related('tenancy__tenant').select_for_update(of=('self',)),
            pk=pk, tenancy__unit__property__owner=request.user,
        )
        back = (redirect('payments:owner_tenancy', pk=payment.tenancy_id) if request.POST.get('next') == 'tenancy'
                else redirect(reverse('payments:owner')))
        tenant = payment.tenancy.tenant.get_full_name() or payment.tenancy.tenant.username
        allowed = {'confirm': Payment.Status.PENDING, 'reject': Payment.Status.PENDING,
                   'void': Payment.Status.CONFIRMED}[decision]
        if payment.status != allowed:
            messages.error(request, 'That payment has already been handled.')
            return back

        payment.reviewed_at = timezone.now()
        if decision == 'confirm':
            payment.status = Payment.Status.CONFIRMED
            messages.success(request, f"Confirmed ₱{payment.amount:,.2f} GCash payment from {tenant}.")
        else:
            form = RejectPaymentForm(request.POST)
            reason = form.cleaned_data['reason'].strip() if form.is_valid() else ''
            payment.status = Payment.Status.REJECTED
            payment.owner_note = reason or ('Voided by owner' if decision == 'void' else '')
            verb = 'Voided' if decision == 'void' else 'Rejected'
            messages.success(request, f'{verb} ₱{payment.amount:,.2f} payment from {tenant}. '
                                      'It no longer counts toward the balance.')
        payment.save(update_fields=['status', 'reviewed_at', 'owner_note'])
    return back
