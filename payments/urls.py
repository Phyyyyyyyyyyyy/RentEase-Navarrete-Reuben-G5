from django.urls import path, re_path

from . import views

app_name = 'payments'

urlpatterns = [
    # Tenant
    path('payments/', views.tenant_payments, name='tenant'),
    path('payments/<int:pk>/gcash/', views.gcash_pay, name='gcash_pay'),
    path('payments/submissions/<int:pk>/cancel/', views.cancel_submission, name='cancel_submission'),
    path('payments/<int:pk>/receipt/', views.payment_proof, name='proof'),

    # Property owner
    path('owner/payments/', views.owner_payments, name='owner'),
    path('owner/payments/tenancy/<int:pk>/', views.owner_tenancy, name='owner_tenancy'),
    re_path(r'^owner/payments/(?P<pk>\d+)/(?P<decision>confirm|reject|void)/$',
            views.owner_review, name='owner_review'),
]
