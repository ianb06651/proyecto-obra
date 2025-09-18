# actividades/admin.py

from django.contrib import admin
from .models import (
    Empresa, Cargo, AreaDeTrabajo, Semana, PartidaActividad, PartidaPersonal, 
    TipoMaquinaria, ReporteClima, Proyecto, Actividad, ReportePersonal, 
    AvanceDiario, ReporteDiarioMaquinaria, MetaPorZona, AvancePorZona
)

# --- PASO 1: DEFINIR LOS INLINES ---
# Estos son los formularios incrustados para las metas y avances por zona.

class MetaPorZonaInline(admin.TabularInline):
    """Permite editar las Metas por Zona directamente dentro de la Actividad."""
    model = MetaPorZona
    extra = 1
    verbose_name = "Meta por Zona"
    verbose_name_plural = "Desglose de Metas por Zona"

class AvancePorZonaInline(admin.TabularInline):
    """Permite registrar el Avance por Zona directamente dentro del Avance Diario."""
    model = AvancePorZona
    extra = 1
    verbose_name = "Avance por Zona"
    verbose_name_plural = "Desglose de Avances por Zona"


# --- PASO 2: DEFINIR LAS CLASES ModelAdmin (SIN DECORADORES) ---

class ProyectoAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'fecha_inicio', 'fecha_fin_estimada')
    search_fields = ('nombre',)

class ActividadAdmin(admin.ModelAdmin):
    fields = (
        'proyecto', 'partida', 'padre', 'nombre', 
        ('meta_cantidad_total', 'unidad_medida'), 
        ('fecha_inicio_programada', 'fecha_fin_programada')
    )
    list_display = ('__str__', 'proyecto', 'partida')
    list_select_related = ('padre', 'proyecto', 'partida')
    list_filter = ('proyecto', 'partida')
    search_fields = ('nombre', 'padre__nombre')
    autocomplete_fields = ['padre']
    list_per_page = 25
    inlines = [MetaPorZonaInline] # Incrusta el formulario de metas por zona

class ReportePersonalAdmin(admin.ModelAdmin):
    list_display = ('fecha', 'empresa', 'cargo', 'partida', 'cantidad')
    list_filter = ('fecha', 'empresa', 'cargo', 'partida')

class AvanceDiarioAdmin(admin.ModelAdmin):
    list_display = ('fecha_reporte', 'actividad', 'empresa', 'total_realizado_calculado')
    list_filter = ('fecha_reporte', 'empresa')
    autocomplete_fields = ['actividad']
    inlines = [AvancePorZonaInline] # Incrusta el formulario de avances por zona

    def get_readonly_fields(self, request, obj=None):
        if obj and obj.avanceporzona_set.exists():
            return ['cantidad_realizada_dia']
        return []

class ReporteDiarioMaquinariaAdmin(admin.ModelAdmin):
    list_display = ('fecha', 'tipo_maquinaria', 'partida', 'empresa', 'cantidad_total', 'cantidad_activa')
    list_filter = ('fecha', 'empresa', 'partida', 'tipo_maquinaria')


# --- PASO 3: DEFINIR Y CREAR TU SITIO DE ADMINISTRACIÓN PERSONALIZADO ---

class MiAdminSite(admin.AdminSite):
    site_header = "Panel de Control de Obra"
    site_title = "Administración del Proyecto"
    index_title = "Bienvenido al Panel de Administración"

    def get_app_list(self, request, app_label=None):
        """
        Devuelve una lista ordenada y robusta de aplicaciones y modelos.
        """
        app_dict = self._build_app_dict(request)
        
        actividades_models = {m['object_name']: m for m in app_dict.get('actividades', {}).get('models', [])}
        
        def get_model(name):
            return actividades_models.get(name)

        app_list = [
            {
                "name": "Gestión de Proyecto",
                "app_label": "gestion_proyecto",
                "models": list(filter(None, [get_model('Proyecto'), get_model('Actividad')])),
            },
            {
                "name": "Reportes Diarios",
                "app_label": "reportes_diarios",
                "models": list(filter(None, [get_model('AvanceDiario'), get_model('ReporteDiarioMaquinaria'), get_model('ReportePersonal'), get_model('ReporteClima')])),
            },
            {
                "name": "Catálogos Generales",
                "app_label": "catalogos",
                "models": list(filter(None, [get_model('Empresa'), get_model('TipoMaquinaria'), get_model('Semana'), get_model('Cargo'), get_model('AreaDeTrabajo'), get_model('PartidaActividad'), get_model('PartidaPersonal')])),
            },
        ]
        return [app for app in app_list if app['models']]

mi_admin_site = MiAdminSite(name='mi_admin')


# --- PASO 4: REGISTRAR TODOS LOS MODELOS EN TU SITIO PERSONALIZADO ---

# Gestión de Proyecto
mi_admin_site.register(Proyecto, ProyectoAdmin)
mi_admin_site.register(Actividad, ActividadAdmin)

# Reportes Diarios
mi_admin_site.register(AvanceDiario, AvanceDiarioAdmin)
mi_admin_site.register(ReporteDiarioMaquinaria, ReporteDiarioMaquinariaAdmin)
mi_admin_site.register(ReportePersonal, ReportePersonalAdmin)
mi_admin_site.register(ReporteClima)

# Catálogos Generales
mi_admin_site.register(Empresa)
mi_admin_site.register(TipoMaquinaria)
mi_admin_site.register(Semana)
mi_admin_site.register(Cargo)
mi_admin_site.register(AreaDeTrabajo)
mi_admin_site.register(PartidaActividad)
mi_admin_site.register(PartidaPersonal)