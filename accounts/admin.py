from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import User


@admin.register(User)
class RentEaseUserAdmin(UserAdmin):
    list_display = ('username', 'email', 'first_name', 'last_name', 'role', 'is_active')
    list_filter = ('role', 'is_active', 'is_staff')
    fieldsets = UserAdmin.fieldsets + (
        ('RentEase', {'fields': ('role', 'phone', 'profile_photo')}),
    )
    add_fieldsets = UserAdmin.add_fieldsets + (
        ('RentEase', {'fields': ('email', 'first_name', 'last_name', 'role', 'phone')}),
    )
