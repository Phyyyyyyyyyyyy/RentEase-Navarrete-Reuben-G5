from django.urls import path

from . import views

app_name = 'properties'

urlpatterns = [
    path('browse/', views.browse, name='browse'),
    path('browse/<int:pk>/', views.property_detail, name='detail'),
    path('applications/', views.my_applications, name='my_applications'),
    path('applications/<int:pk>/withdraw/', views.withdraw_application, name='withdraw'),
]
