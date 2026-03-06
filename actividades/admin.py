# actividades/admin.py

from django.contrib import admin
from django.utils.html import format_html  # <-- Añadido para mostrar las imágenes
from .models import (
    Empresa, Cargo, AreaDeTrabajo, Semana,
    PartidaActividad, PartidaPersonal,
    Actividad, ReportePersonal, AvanceDiario, TipoMaquinaria,
    ReporteDiarioMaquinaria, ReporteClima, Proyecto,
    MetaPorZona, AvancePorZona, TipoElemento, ProcesoConstructivo, PasoProcesoTipoElemento,
    ElementoConstructivo, AvanceProcesoElemento,
    ElementoBIM_GUID, Cronograma, Observacion, CronogramaPorZona
)

# --- PERSONALIZACIÓN GENERAL DEL ADMIN ---
admin.site.site_header = "Panel de Control de Obra (DIPRO)"
admin.site.site_title = "Admin de Obra"
admin.site.index_title = "Gestión Central de la Obra"

# --- Registros de Catálogos ---
admin.site.register(Empresa)
admin.site.register(Cargo)
admin.site.register(Semana)
admin.site.register(PartidaActividad)
admin.site.register(PartidaPersonal)
admin.site.register(TipoMaquinaria)
admin.site.register(ReporteClima)


@admin.register(AreaDeTrabajo)
class AreaDeTrabajoAdmin(admin.ModelAdmin):
    list_display = ('nombre',)
    search_fields = ('nombre',)


# --- Inlines para gestionar los desgloses ---
class MetaPorZonaInline(admin.TabularInline):
    model = MetaPorZona
    extra = 1
    autocomplete_fields = ['zona']
    fields = ('zona', 'meta', 'fecha_inicio_programada', 'fecha_fin_programada')

class AvancePorZonaInline(admin.TabularInline):
    model = AvancePorZona
    extra = 1
    autocomplete_fields = ['zona']

# --- NUEVO INLINE: Ver fechas por zona dentro de la Tarea Maestra ---
class CronogramaPorZonaInline(admin.TabularInline):
    model = CronogramaPorZona
    extra = 1
    autocomplete_fields = ['zona']

# --- Configuraciones Avanzadas (WBS y Avances) ---

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
        'unidad_medida',
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
    list_display = ('fecha_reporte', 'actividad', 'cantidad_total')
    list_filter = ('fecha_reporte', 'empresa')
    autocomplete_fields = ['actividad']
    inlines = [AvancePorZonaInline]
    readonly_fields = ('cantidad_total',)

@admin.register(ReporteDiarioMaquinaria)
class ReporteDiarioMaquinariaAdmin(admin.ModelAdmin):
    list_display = ('fecha', 'tipo_maquinaria', 'partida', 'empresa', 'cantidad_total', 'cantidad_activa')
    list_filter = ('fecha', 'empresa', 'partida', 'tipo_maquinaria')

# --- CONFIGURACIÓN ADMIN PARA MODELOS BIM ---

@admin.register(ProcesoConstructivo)
class ProcesoConstructivoAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'descripcion')
    search_fields = ('nombre',)

class PasoProcesoTipoElementoInline(admin.TabularInline):
    model = PasoProcesoTipoElemento
    extra = 1
    ordering = ('orden',)
    autocomplete_fields = ['proceso'] 

@admin.register(TipoElemento)
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

class ElementoBIM_GUID_Inline(admin.TabularInline):
    model = ElementoBIM_GUID
    extra = 1 
    fields = ('identificador_bim',)
    verbose_name = "GUID de BIM"
    verbose_name_plural = "GUIDs de BIM (Navisworks/Revit)"

@admin.register(ElementoConstructivo)
class ElementoConstructivoAdmin(admin.ModelAdmin):
    list_display = ('identificador_unico', 'tipo_elemento', 'descripcion')
    list_filter = ('tipo_elemento',)
    search_fields = ('identificador_unico', 'descripcion') 
    autocomplete_fields = ['tipo_elemento']
    inlines = [ElementoBIM_GUID_Inline]


@admin.register(AvanceProcesoElemento)
class AvanceProcesoElementoAdmin(admin.ModelAdmin):
    list_display = ('elemento', 'paso_proceso', 'fecha_finalizacion')
    list_filter = ('paso_proceso__tipo_elemento', 'fecha_finalizacion')
    search_fields = ('elemento__identificador_unico', 'elemento__guids_bim__identificador_bim', 'paso_proceso__proceso__nombre') 
    autocomplete_fields = ['elemento', 'paso_proceso']
    date_hierarchy = 'fecha_finalizacion'

@admin.register(ElementoBIM_GUID)
class ElementoBIM_GUID_Admin(admin.ModelAdmin):
    list_display = ('identificador_bim', 'elemento_constructivo')
    search_fields = ('identificador_bim', 'elemento_constructivo__identificador_unico')
    autocomplete_fields = ['elemento_constructivo']
    
# --- CRONOGRAMA ACTUALIZADO ---

@admin.register(Cronograma)
class CronogramaAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'padre', 'proyecto')
    list_filter = ('proyecto', 'padre') 
    search_fields = ('nombre',)
    ordering = ('padre',)
    autocomplete_fields = ['padre'] 
    inlines = [CronogramaPorZonaInline]

@admin.register(CronogramaPorZona)
class CronogramaPorZonaAdmin(admin.ModelAdmin):
    list_display = ('tarea', 'zona', 'fecha_inicio_prog', 'fecha_fin_prog', 'estado_calculado')
    list_filter = ('zona', 'tarea__proyecto')
    search_fields = ('tarea__nombre', 'zona__nombre')
    list_editable = ('fecha_inicio_prog', 'fecha_fin_prog')

# --- AQUÍ ESTÁ LA MEJORA PARA OBSERVACIONES ---
@admin.register(Observacion)
class ObservacionAdmin(admin.ModelAdmin):
    list_display = ('fecha', 'zona', 'nombre', 'estado', 'mostrar_miniatura', 'fecha_actualizacion')
    list_filter = ('zona', 'estado', 'fecha')
    search_fields = ('nombre', 'comentario')
    date_hierarchy = 'fecha'
    list_editable = ('estado',)  # Permite cambiar el estado directamente desde la lista
    readonly_fields = ('mostrar_imagen_grande', 'fecha_actualizacion')
    
    # Agrupamos los campos para que no se vea como una lista aburrida
    fieldsets = (
        ('Información Principal', {
            'fields': ('fecha', 'zona', 'nombre', 'comentario')
        }),
        ('Evidencia Fotográfica', {
            'fields': ('imagen', 'mostrar_imagen_grande'),
            'classes': ('collapse',), # Lo hace colapsable
        }),
        ('Seguimiento', {
            'fields': ('estado', 'actualizado_por', 'fecha_actualizacion')
        }),
    )

    # Funciones para visualizar las imágenes reales en el Admin
    def mostrar_miniatura(self, obj):
        if obj.imagen:
            return format_html('<a href="{}" target="_blank"><img src="{}" style="width: 45px; height: 45px; object-fit: cover; border-radius: 4px;" /></a>', obj.imagen.url, obj.imagen.url)
        return "Sin Foto"
    mostrar_miniatura.short_description = "Evidencia"

    def mostrar_imagen_grande(self, obj):
        if obj.imagen:
            return format_html('<a href="{}" target="_blank"><img src="{}" style="max-width: 400px; max-height: 400px; border-radius: 8px; box-shadow: 0 4px 8px rgba(0,0,0,0.1);" /></a>', obj.imagen.url, obj.imagen.url)
        return "Sube una imagen primero"
    mostrar_imagen_grande.short_description = "Vista Previa"