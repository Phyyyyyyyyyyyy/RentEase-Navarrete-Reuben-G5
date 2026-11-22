from django.contrib import admin

from .models import Payment, RentCharge


@admin.register(RentCharge)
class RentChargeAdmin(admin.ModelAdmin):
    list_display = ('tenancy', 'period', 'amount', 'due_date')
    list_filter = ('period',)
    search_fields = ('tenancy__tenant__username', 'tenancy__unit__name', 'tenancy__unit__property__name')


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ('tenancy', 'amount', 'method', 'reference_number', 'paid_on', 'status')
    list_filter = ('status', 'method')
    search_fields = ('reference_number', 'tenancy__tenant__username', 'tenancy__unit__property__name')
