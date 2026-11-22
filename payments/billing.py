"""Rent billing: create monthly charges and work out what a tenant owes.

Charges are created lazily (whenever a payments page or dashboard is opened)
rather than by a scheduled job, so no cron setup is needed.
"""
import calendar
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal

from django.db.models import Sum
from django.utils import timezone

from properties.models import Application, Unit

from .models import Payment, RentCharge

ZERO = Decimal('0.00')


def month_start(d):
    return d.replace(day=1)


def month_end(d):
    return d.replace(day=calendar.monthrange(d.year, d.month)[1])


def next_month(d):
    return date(d.year + d.month // 12, d.month % 12 + 1, 1)


def tenancies_for(**filters):
    """Approved applications, newest approval first, with the unit, property, and people loaded."""
    return (
        Application.objects.filter(status=Application.Status.APPROVED, approved_at__isnull=False, **filters)
        .select_related('tenant', 'unit__property__owner')
        .order_by('-approved_at')
    )


def is_active(tenancy, latest_by_unit):
    """A tenancy is active while its unit is occupied and no later tenant was approved for that unit."""
    return tenancy.unit.status == Unit.Status.OCCUPIED and latest_by_unit.get(tenancy.unit_id) == tenancy.pk


def latest_approved_by_unit(unit_ids):
    latest = {}
    for pk, unit_id in (Application.objects.filter(status=Application.Status.APPROVED, unit_id__in=unit_ids,
                                                   approved_at__isnull=False)
                        .order_by('unit_id', '-approved_at').values_list('pk', 'unit_id')):
        latest.setdefault(unit_id, pk)
    return latest


def sync_charges(tenancy, today=None):
    """Create any missing monthly charges from the tenancy's first month up to this month."""
    today = today or timezone.localdate()
    start = tenancy.tenancy_start
    if start is None or start > today:
        return
    existing = set(tenancy.rent_charges.values_list('period', flat=True))
    missing, period = [], month_start(start)
    while period <= today:
        if period not in existing:
            missing.append(RentCharge(tenancy=tenancy, period=period, amount=tenancy.unit.monthly_rent,
                                      due_date=month_end(period)))
        period = next_month(period)
    if missing:
        RentCharge.objects.bulk_create(missing, ignore_conflicts=True)


@dataclass
class MonthLine:
    charge: RentCharge
    paid: Decimal
    remaining: Decimal
    through_total: Decimal  # amount that would settle everything up to and including this month
    state: str  # paid | partial | due | overdue

    @property
    def label(self):
        return {'paid': 'Paid', 'partial': 'Partly paid', 'due': 'Due', 'overdue': 'Overdue'}[self.state]


@dataclass
class Ledger:
    tenancy: Application
    active: bool
    today: date
    lines: list = field(default_factory=list)
    total_charged: Decimal = ZERO
    total_paid: Decimal = ZERO
    pending_total: Decimal = ZERO
    pending_count: int = 0

    @property
    def balance(self):
        return max(self.total_charged - self.total_paid, ZERO)

    @property
    def credit(self):
        return max(self.total_paid - self.total_charged, ZERO)

    @property
    def overdue(self):
        return sum((l.remaining for l in self.lines if l.state == 'overdue'), ZERO)

    @property
    def current(self):
        """This month's line, if the tenancy has started."""
        return self.lines[-1] if self.lines and self.lines[-1].charge.period == month_start(self.today) else None

    @property
    def months_covered(self):
        """How many future months the credit pays for at the current rent."""
        rent = self.tenancy.unit.monthly_rent
        return int(self.credit // rent) if rent else 0

    @property
    def suggested_amount(self):
        """Prefill for a payment form: the balance, or one month's rent if nothing is owed (paying ahead)."""
        return self.balance or self.tenancy.unit.monthly_rent

    @property
    def lines_newest_first(self):
        return list(reversed(self.lines))


def build_ledger(tenancy, active=True, today=None):
    today = today or timezone.localdate()
    if active:
        sync_charges(tenancy, today)
    charges = list(tenancy.rent_charges.order_by('period'))
    payments = tenancy.payments.values('status').annotate(total=Sum('amount')).order_by()
    totals = {row['status']: row['total'] for row in payments}
    ledger = Ledger(
        tenancy=tenancy, active=active, today=today,
        total_charged=sum((c.amount for c in charges), ZERO),
        total_paid=totals.get(Payment.Status.CONFIRMED) or ZERO,
        pending_total=totals.get(Payment.Status.PENDING) or ZERO,
        pending_count=tenancy.payments.filter(status=Payment.Status.PENDING).count(),
    )
    # Apply confirmed payments to the oldest month first.
    available, running = ledger.total_paid, ZERO
    for charge in charges:
        paid = min(available, charge.amount)
        available -= paid
        remaining = charge.amount - paid
        running += remaining
        if remaining == 0:
            state = 'paid'
        elif charge.due_date < today:
            state = 'overdue'
        elif paid > 0:
            state = 'partial'
        else:
            state = 'due'
        ledger.lines.append(MonthLine(charge, paid, remaining, running, state))
    return ledger


def ledgers_for(tenancies, today=None):
    """Ledgers for active tenancies, plus ended ones that still have charges or payments on record."""
    tenancies = list(tenancies)
    latest = latest_approved_by_unit({t.unit_id for t in tenancies})
    ledgers = []
    for tenancy in tenancies:
        active = is_active(tenancy, latest)
        if not active and not (tenancy.rent_charges.exists() or tenancy.payments.exists()):
            continue
        ledgers.append(build_ledger(tenancy, active=active, today=today))
    return ledgers
