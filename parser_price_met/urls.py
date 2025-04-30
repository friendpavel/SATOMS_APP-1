from django.urls import path
from . import views

app_name = 'parser_price_met'

urlpatterns = [
    path('', views.price_analysis, name='price_analysis'),
]
