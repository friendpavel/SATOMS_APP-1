from django.contrib import admin
from django.urls import path, include
from django.conf.urls import handler404
from ascon_lic.views import index

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('ascon_lic.urls')),
]

handler404 = lambda request, exception: index(request)
