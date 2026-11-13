from django.urls import path, re_path

from . import owner_views, views

app_name = 'properties'

urlpatterns = [
    # Tenant
    path('browse/', views.browse, name='browse'),
    path('browse/<int:pk>/', views.property_detail, name='detail'),
    path('applications/', views.my_applications, name='my_applications'),
    path('applications/<int:pk>/withdraw/', views.withdraw_application, name='withdraw'),

    # Property owner
    path('owner/properties/', owner_views.property_list, name='owner_properties'),
    path('owner/properties/new/', owner_views.property_create, name='owner_property_create'),
    path('owner/properties/<int:pk>/', owner_views.property_manage, name='owner_property'),
    path('owner/properties/<int:pk>/edit/', owner_views.property_edit, name='owner_property_edit'),
    path('owner/properties/<int:pk>/delete/', owner_views.property_delete, name='owner_property_delete'),
    path('owner/properties/<int:pk>/units/new/', owner_views.unit_create, name='owner_unit_create'),
    path('owner/properties/units/<int:pk>/edit/', owner_views.unit_edit, name='owner_unit_edit'),
    path('owner/properties/units/<int:pk>/delete/', owner_views.unit_delete, name='owner_unit_delete'),
    path('owner/applications/', owner_views.application_list, name='owner_applications'),
    re_path(r'^owner/applications/(?P<pk>\d+)/(?P<decision>approve|reject)/$',
            owner_views.application_decide, name='owner_application_decide'),
]
