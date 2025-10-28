# src/actividades/admin.py
from django.contrib import admin
from .models import (
    Empresa, Cargo, AreaDeTrabajo, Semana,
    PartidaActividad, PartidaPersonal,
    Actividad, ReportePersonal, AvanceDiario, TipoMaquinaria,
    ReporteDiarioMaquinaria, ReporteClima, Proyecto,
    MetaPorZona, AvancePorZona, TipoElemento, ProcesoConstructivo, PasoProcesoTipoElemento,
    ElementoConstructivo, AvanceProcesoElemento
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

# --- Configuraciones Avanzadas (Modificadas) ---

@admin.register(Proyecto)
class ProyectoAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'fecha_inicio', 'fecha_fin_estimada')
    search_fields = ('nombre',)

@admin.register(Actividad)
class ActividadAdmin(admin.ModelAdmin):
    # MODIFICADO: Se elimina 'meta_general' de fields.
    fields = (
        'proyecto',
        'partida',
        'padre',
        'nombre',
        'unidad_medida', # 'meta_general' fue quitado de esta tupla
        ('fecha_inicio_programada', 'fecha_fin_programada')
    )
    # Se mantiene 'meta_total' (propiedad calculada) en list_display
    list_display = ('__str__', 'proyecto', 'partida', 'meta_total')
    list_select_related = ('padre', 'proyecto', 'partida')
    list_filter = ('proyecto', 'partida')
    search_fields = ('nombre', 'padre__nombre')
    autocomplete_fields = ['padre']
    list_per_page = 25
    inlines = [MetaPorZonaInline] # El inline para metas por zona es ahora la única forma de ver/editar metas
    readonly_fields = ('meta_total',) # 'meta_total' sigue siendo readonly

@admin.register(ReportePersonal)
class ReportePersonalAdmin(admin.ModelAdmin):
    list_display = ('fecha', 'empresa', 'cargo', 'partida', 'cantidad')
    list_filter = ('fecha', 'empresa', 'cargo', 'partida')

@admin.register(AvanceDiario)
class AvanceDiarioAdmin(admin.ModelAdmin):
    # MODIFICADO: Se elimina 'cantidad_general' de list_display. Se mantiene 'cantidad_total'.
    list_display = ('fecha_reporte', 'actividad', 'cantidad_total') # 'cantidad_general' eliminado
    list_filter = ('fecha_reporte', 'empresa')
    autocomplete_fields = ['actividad']
    inlines = [AvancePorZonaInline] # El inline es ahora la única forma de ver/editar avances
    readonly_fields = ('cantidad_total',) # 'cantidad_total' sigue siendo readonly

@admin.register(ReporteDiarioMaquinaria)
class ReporteDiarioMaquinariaAdmin(admin.ModelAdmin):
    list_display = ('fecha', 'tipo_maquinaria', 'partida', 'empresa', 'cantidad_total', 'cantidad_activa')
    list_filter = ('fecha', 'empresa', 'partida', 'tipo_maquinaria')

@admin.register(ProcesoConstructivo)
class ProcesoConstructivoAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'descripcion')
    search_fields = ('nombre',)

class PasoProcesoTipoElementoInline(admin.TabularInline):
    """ Permite definir los pasos directamente al crear/editar un TipoElemento """
    model = PasoProcesoTipoElemento
    extra = 1
    ordering = ('orden',)
    autocomplete_fields = ['proceso'] # Asume que ProcesoConstructivoAdmin tiene search_fields

@admin.register(TipoElemento) # Re-registrar TipoElemento para añadir el inline
class TipoElementoConPasosAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'descripcion')
    search_fields = ('nombre',)
    inlines = [PasoProcesoTipoElementoInline]

@admin.register(PasoProcesoTipoElemento)
class PasoProcesoTipoElementoAdmin(admin.ModelAdmin):
    list_display = ('tipo_elemento', 'orden', 'proceso')
    list_filter = ('tipo_elemento',)
    search_fields = ('proceso__nombre',)
    autocomplete_fields = ['tipo_elemento', 'proceso']
    list_editable = ('orden',)

@admin.register(ElementoConstructivo)
class ElementoConstructivoAdmin(admin.ModelAdmin):
    list_display = ('identificador_unico', 'tipo_elemento', 'descripcion')
    list_filter = ('tipo_elemento',)
    search_fields = ('identificador_unico', 'descripcion') # ¡Importante para la búsqueda!
    autocomplete_fields = ['tipo_elemento']

@admin.register(AvanceProcesoElemento)
class AvanceProcesoElementoAdmin(admin.ModelAdmin):
    list_display = ('elemento', 'paso_proceso', 'fecha_finalizacion')
    list_filter = ('paso_proceso__tipo_elemento', 'fecha_finalizacion')
    search_fields = ('elemento__identificador_unico', 'paso_proceso__proceso__nombre')
    autocomplete_fields = ['elemento', 'paso_proceso']
    date_hierarchy = 'fecha_finalizacion' # Facilita la navegación por fechas