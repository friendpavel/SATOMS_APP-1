from django.shortcuts import render

def home(request):
    """Домашняя страница."""
    return render(request, 'home.html')