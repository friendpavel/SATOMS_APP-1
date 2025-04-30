from django.contrib import admin
from django.urls import path, include
from . import views

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', views.home, name='home'),
    path('parser/', include('parser_price_met.urls', namespace='parser_price_met')),
    path('licenses/', include('ascon_lic.urls', namespace='ascon_lic')),
]