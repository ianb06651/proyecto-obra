# src/actividades/admin.py
from django.contrib import admin
from .models import (
    Empresa, Cargo, AreaDeTrabajo, Semana, 
    PartidaActividad, PartidaPersonal, 
    Actividad, ReportePersonal, AvanceDiario, TipoMaquinaria,
    ReporteDiarioMaquinaria, ReporteClima, Proyecto
)

# --- Registros de Catálogos ---
admin.site.register(Empresa)
admin.site.register(Cargo)
admin.site.register(AreaDeTrabajo)
admin.site.register(Semana)
admin.site.register(PartidaActividad)
admin.site.register(PartidaPersonal)
admin.site.register(TipoMaquinaria)
admin.site.register(ReporteClima)

# --- Configuraciones Avanzadas ---

@admin.register(Proyecto)
class ProyectoAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'fecha_inicio', 'fecha_fin_estimada')
    search_fields = ('nombre',)

@admin.register(Actividad)
class ActividadAdmin(admin.ModelAdmin):
    fields = (
        'proyecto', 
        'partida', 
        'padre', 
        'nombre', 
        # Agrupar campos en una tupla los muestra en la misma línea
        ('meta_cantidad_total', 'unidad_medida'), 
        ('fecha_inicio_programada', 'fecha_fin_programada')
    )

    # --- CONFIGURACIÓN DE LA VISTA DE LISTA (sin cambios) ---
    list_display = ('__str__', 'proyecto', 'partida')
    list_select_related = ('padre', 'proyecto', 'partida')
    list_filter = ('proyecto', 'partida')
    search_fields = ('nombre', 'padre__nombre')
    autocomplete_fields = ['padre']
    list_per_page = 25

@admin.register(ReportePersonal)
class ReportePersonalAdmin(admin.ModelAdmin):
    list_display = ('fecha', 'empresa', 'cargo', 'partida', 'cantidad')
    list_filter = ('fecha', 'empresa', 'cargo', 'partida')

@admin.register(AvanceDiario)
class AvanceDiarioAdmin(admin.ModelAdmin):
    list_display = ('fecha_reporte', 'actividad', 'cantidad_realizada_dia')
    list_filter = ('fecha_reporte',)
    autocomplete_fields = ['actividad']

@admin.register(ReporteDiarioMaquinaria)
class ReporteDiarioMaquinariaAdmin(admin.ModelAdmin):
    list_display = ('fecha', 'tipo_maquinaria', 'partida', 'empresa', 'cantidad_total', 'cantidad_activa')
    list_filter = ('fecha', 'empresa', 'partida', 'tipo_maquinaria')