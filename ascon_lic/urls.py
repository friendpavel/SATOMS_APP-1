from django.urls import path
from . import views

app_name = 'ascon_lic'

urlpatterns = [
    path('', views.licenses_view, name='licenses'),
]
