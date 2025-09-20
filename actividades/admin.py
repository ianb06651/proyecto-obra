# src/actividades/admin.py
from django.contrib import admin
from .models import (
    Empresa, Cargo, AreaDeTrabajo, Semana,
    PartidaActividad, PartidaPersonal,
    Actividad, ReportePersonal, AvanceDiario, TipoMaquinaria,
    ReporteDiarioMaquinaria, ReporteClima, Proyecto,
    MetaPorZona, AvancePorZona
)

# --- Registros de Catálogos ---
admin.site.register(Empresa)
admin.site.register(Cargo)
# admin.site.register(AreaDeTrabajo) # Se comenta o elimina el registro simple
admin.site.register(Semana)
admin.site.register(PartidaActividad)
admin.site.register(PartidaPersonal)
admin.site.register(TipoMaquinaria)
admin.site.register(ReporteClima)


# --- NUEVO: ModelAdmin para AreaDeTrabajo ---
@admin.register(AreaDeTrabajo)
class AreaDeTrabajoAdmin(admin.ModelAdmin):
    """
    Configuración necesaria para habilitar la búsqueda
    en los campos de autocompletado.
    """
    list_display = ('nombre',)
    search_fields = ('nombre',) # <-- ESTA LÍNEA RESUELVE EL ERROR


# --- Inlines para gestionar los desgloses ---
class MetaPorZonaInline(admin.TabularInline):
    model = MetaPorZona
    extra = 1
    autocomplete_fields = ['zona']
    # Añadimos los campos al inline para que se puedan editar
    fields = ('zona', 'meta', 'fecha_inicio_programada', 'fecha_fin_programada')

class AvancePorZonaInline(admin.TabularInline):
    model = AvancePorZona
    extra = 1
    autocomplete_fields = ['zona']

# --- Configuraciones Avanzadas (sin cambios, se mantienen como estaban) ---

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
        ('meta_general', 'unidad_medida'),
        ('fecha_inicio_programada', 'fecha_fin_programada')
    )
    list_display = ('__str__', 'proyecto', 'partida', 'meta_total')
    list_select_related = ('padre', 'proyecto', 'partida')
    list_filter = ('proyecto', 'partida')
    search_fields = ('nombre', 'padre__nombre')
    autocomplete_fields = ['padre']
    list_per_page = 25
    inlines = [MetaPorZonaInline]
    readonly_fields = ('meta_total',)

@admin.register(ReportePersonal)
class ReportePersonalAdmin(admin.ModelAdmin):
    list_display = ('fecha', 'empresa', 'cargo', 'partida', 'cantidad')
    list_filter = ('fecha', 'empresa', 'cargo', 'partida')

@admin.register(AvanceDiario)
class AvanceDiarioAdmin(admin.ModelAdmin):
    list_display = ('fecha_reporte', 'actividad', 'cantidad_general', 'cantidad_total')
    list_filter = ('fecha_reporte', 'empresa')
    autocomplete_fields = ['actividad']
    inlines = [AvancePorZonaInline]
    readonly_fields = ('cantidad_total',)

@admin.register(ReporteDiarioMaquinaria)
class ReporteDiarioMaquinariaAdmin(admin.ModelAdmin):
    list_display = ('fecha', 'tipo_maquinaria', 'partida', 'empresa', 'cantidad_total', 'cantidad_activa')
    list_filter = ('fecha', 'empresa', 'partida', 'tipo_maquinaria')