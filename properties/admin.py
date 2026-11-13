from django.contrib import admin

from .models import Application, Property, Unit


class UnitInline(admin.TabularInline):
    model = Unit
    extra = 1


@admin.register(Property)
class PropertyAdmin(admin.ModelAdmin):
    list_display = ('name', 'property_type', 'city', 'owner')
    list_filter = ('property_type', 'city')
    search_fields = ('name', 'address', 'city')
    inlines = [UnitInline]


@admin.register(Unit)
class UnitAdmin(admin.ModelAdmin):
    list_display = ('name', 'property', 'monthly_rent', 'status')
    list_filter = ('status', 'property')


@admin.register(Application)
class ApplicationAdmin(admin.ModelAdmin):
    list_display = ('tenant', 'unit', 'status', 'created_at')
    list_filter = ('status',)
    search_fields = ('tenant__username', 'unit__name', 'unit__property__name')
