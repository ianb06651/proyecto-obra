# actividades/urls.py

from django.urls import path
from . import views

urlpatterns = [
    # --- URL para la página principal ---
    path('', views.pagina_principal, name='pagina_principal'),

    # --- URLS PARA AVANCES, REPORTES, ETC. ---
    
    # URL Simplificada: Ya no necesita el ID del proyecto
    path('avance/registrar/', views.registrar_avance, name='registrar_avance'),
    
    path('avance/editar/<int:pk>/', views.editar_avance, name='editar_avance'),
    path('avance/borrar/<int:pk>/', views.borrar_avance, name='borrar_avance'),
    path('maquinaria/reporte/nuevo/', views.registrar_reporte_maquinaria, name='registrar_reporte_maquinaria'),
    path('maquinaria/reporte/editar/<int:pk>/', views.editar_reporte_maquinaria, name='editar_reporte_maquinaria'),
    path('personal/reporte/nuevo/', views.registrar_reporte_personal, name='registrar_reporte_personal'),
    path('clima/', views.vista_clima, name='vista_clima'),
    
    # --- URLS PARA GESTIONAR LA JERARQUÍA (WBS) ---
    path('wbs/', views.ActividadListView.as_view(), name='actividad_list'),
    path('wbs/crear/', views.ActividadCreateView.as_view(), name='actividad_create'),
    path('wbs/<int:pk>/editar/', views.ActividadUpdateView.as_view(), name='actividad_update'),

    # --- URL PARA EL HISTORIAL UNIFICADO ---
    # Esta URL sí necesita el ID para saber qué historial mostrar
    path('proyecto/<int:proyecto_id>/historial/', views.historial_avance_view, name='historial_avance'),
    
    # --- URLs PARA REGISTRO DE AVANCE BIM ---
    path('bim/registrar/', views.registrar_avance_bim, name='registrar_avance_bim'),

    # --- URLs DE API PARA FORMULARIO DINÁMICO ---
    path('api/buscar-elementos/',
         views.buscar_elementos_constructivos,
         name='api_buscar_elementos'),
    path('api/elemento/<int:elemento_id>/pasos/',
         views.obtener_pasos_y_avance_elemento,
         name='api_obtener_pasos'),
]