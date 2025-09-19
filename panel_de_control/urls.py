# panel_de_control/urls.py

from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    # Usa la línea original del admin de Django
    path('admin/', admin.site.urls),
    
    # Incluye las URLs de tu aplicación
    path('', include('actividades.urls')),
]