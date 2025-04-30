from django.contrib import admin
from django.urls import path, include
from . import views

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', views.home),
    path('licenses/', include('ascon_lic.urls')),
    path('parser/', include('parser_price_met.urls')),
]