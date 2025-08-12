"""
URL configuration for panel_de_control project.
"""
from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    # 1. Ruta para el panel de administración de Django
    path('admin/', admin.site.urls),
    
    # 2. Esta única línea dirige TODO el tráfico (incluida la raíz del sitio, '/')
    #    a tu archivo de URLs de la app 'actividades' para que él decida qué hacer.
    path('', include('actividades.urls')),
]