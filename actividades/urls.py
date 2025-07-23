# En el nuevo archivo actividades/urls.py

from django.urls import path
from . import views
from .views import registrar_reporte_maquinaria

urlpatterns = [
    # Cuando alguien visite '.../registrar/', se ejecutará la vista 'registrar_avance'
    path('registrar/', views.registrar_avance, name='registrar_avance'),
    path('lista/', views.lista_avances, name='lista_avances'),
    path('avance/editar/<int:pk>/', views.editar_avance, name='editar_avance'),
    path('avance/borrar/<int:pk>/', views.borrar_avance, name='borrar_avance'),
     path('maquinaria/reporte/nuevo/', registrar_reporte_maquinaria, name='registrar_reporte_maquinaria'),
     path('personal/reporte/nuevo/', views.registrar_reporte_personal, name='registrar_reporte_personal'),
]