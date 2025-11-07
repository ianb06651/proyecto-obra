# actividades/models.py

from django.db import models
from django.utils.translation import gettext_lazy as _
from django.core.exceptions import ValidationError
from datetime import date, timedelta
from django.db.models import Sum, Count # Importar Count
from functools import cached_property
from django.db.models import Max

# --- CATÁLOGOS ---
# ... (El resto de tus modelos: Empresa, Cargo, AreaDeTrabajo, etc. no cambian) ...
class Empresa(models.Model):
    nombre = models.CharField(max_length=255, unique=True)
    def __str__(self): return self.nombre

def get_default_empresa_pk():
    empresa, created = Empresa.objects.get_or_create(nombre='PROSER')
    return empresa.pk

class Cargo(models.Model):
    nombre = models.CharField(max_length=255, unique=True)
    def __str__(self): return self.nombre

class AreaDeTrabajo(models.Model):
    nombre = models.CharField(max_length=255, unique=True)
    class Meta: verbose_name_plural = "Áreas de Trabajo"
    def __str__(self): return self.nombre

class Semana(models.Model):
    numero_semana = models.IntegerField(unique=True)
    fecha_inicio = models.DateField()
    fecha_fin = models.DateField()
    class Meta:
        verbose_name_plural = "Semanas"
        ordering = ['numero_semana']
    def __str__(self): return f"Semana {self.numero_semana}"

class Proyecto(models.Model):
    nombre = models.CharField(_("Nombre del Proyecto"), max_length=255, unique=True)
    fecha_inicio = models.DateField(_("Fecha de Inicio"))
    fecha_fin_estimada = models.DateField(_("Fecha de Finalización Estimada"))

    def get_valor_planeado_a_fecha(self, fecha_corte: date):
        actividades_raiz = self.actividades.filter(padre__isnull=True)
        return sum(act.get_valor_planeado_a_fecha(fecha_corte) for act in actividades_raiz)

    def get_valor_planeado_en_rango(self, fecha_inicio_rango: date, fecha_fin_rango: date):
        actividades_raiz = self.actividades.filter(padre__isnull=True)
        return sum(act.get_valor_planeado_en_rango(fecha_inicio_rango, fecha_fin_rango) for act in actividades_raiz)

    def __str__(self):
        return self.nombre

class PartidaActividad(models.Model):
    nombre = models.CharField(max_length=255, unique=True)
    class Meta: verbose_name_plural = "Partidas de Actividades"
    def __str__(self): return self.nombre

class PartidaPersonal(models.Model):
    nombre = models.CharField(max_length=255, unique=True)
    class Meta: verbose_name_plural = "Partidas de Personal"
    def __str__(self): return self.nombre

class TipoMaquinaria(models.Model):
    nombre = models.CharField(max_length=100, unique=True, help_text="Ej: Retroexcavadora")
    partida = models.ForeignKey(PartidaActividad, on_delete=models.SET_NULL, null=True, blank=True, help_text="Partida a la que suele pertenecer esta maquinaria")
    class Meta:
        verbose_name = "Tipo de Maquinaria"
        verbose_name_plural = "Tipos de Maquinaria"
        ordering = ['nombre']
    def __str__(self):
        return self.nombre

class MetaPorZona(models.Model):
    actividad = models.ForeignKey('Actividad', on_delete=models.CASCADE, related_name='metas_por_zona')
    zona = models.ForeignKey(AreaDeTrabajo, on_delete=models.CASCADE, verbose_name="Zona de Trabajo")
    meta = models.DecimalField(_("Meta por Zona"), max_digits=12, decimal_places=2)
    fecha_inicio_programada = models.DateField(null=True, blank=True)
    fecha_fin_programada = models.DateField(null=True, blank=True)

    class Meta:
        verbose_name = "Meta por Zona"
        verbose_name_plural = "Metas por Zona"
        unique_together = ('actividad', 'zona')

    def get_valor_planeado_individual(self, fecha_corte: date):
        fecha_inicio = self.fecha_inicio_programada or self.actividad.fecha_inicio_programada
        fecha_fin = self.fecha_fin_programada or self.actividad.fecha_fin_programada
        if not fecha_inicio or not fecha_fin:
            return 0
        if fecha_corte < fecha_inicio:
            return 0
        if fecha_corte >= fecha_fin:
            return self.meta
        dias_totales = sum(1 for i in range((fecha_fin - fecha_inicio).days + 1) if (fecha_inicio + timedelta(days=i)).weekday() != 6) # 6 = Domingo
        if dias_totales == 0:
            return 0
        meta_diaria_zona = self.meta / dias_totales
        dias_transcurridos = sum(1 for i in range((fecha_corte - fecha_inicio).days + 1) if (fecha_inicio + timedelta(days=i)).weekday() != 6)
        return round(dias_transcurridos * meta_diaria_zona, 2)

class AvancePorZona(models.Model):
    avance_diario = models.ForeignKey('AvanceDiario', on_delete=models.CASCADE, related_name='avances_por_zona')
    zona = models.ForeignKey(AreaDeTrabajo, on_delete=models.CASCADE, verbose_name="Zona de Trabajo")
    cantidad = models.DecimalField(_("Cantidad por Zona"), max_digits=12, decimal_places=2)

    class Meta:
        verbose_name = "Avance por Zona"
        verbose_name_plural = "Avances por Zona"
        unique_together = ('avance_diario', 'zona')

class Actividad(models.Model):
    nombre = models.CharField(_("Nombre de Actividad/Categoría"), max_length=255)
    padre = models.ForeignKey(
        'self', on_delete=models.CASCADE, null=True, blank=True,
        related_name='sub_actividades', verbose_name=_("Categoría Padre")
    )
    proyecto = models.ForeignKey(Proyecto, on_delete=models.CASCADE, related_name='actividades')
    partida = models.ForeignKey(PartidaActividad, on_delete=models.PROTECT, null=True, blank=True)
    zonas_meta = models.ManyToManyField(
        AreaDeTrabajo,
        through=MetaPorZona,
        related_name='actividades_meta',
        verbose_name=_("Desglose de Metas por Zona")
    )
    unidad_medida = models.CharField(_("Unidad de Medida"), max_length=50, blank=True, help_text="Ej: m3, Ton, Pza")
    fecha_inicio_programada = models.DateField(null=True, blank=True)
    fecha_fin_programada = models.DateField(null=True, blank=True)

    @property
    def meta_total(self):
        metas_zonas = self.metas_por_zona.all()
        total = metas_zonas.aggregate(total=Sum('meta'))['total']
        return total or 0

    @cached_property
    def cantidad_total_calculada(self):
        sub_actividades = self.sub_actividades.all()
        if sub_actividades.exists():
            return sum(sub.cantidad_total_calculada for sub in sub_actividades)
        return self.meta_total

    @cached_property
    def dias_laborables_totales(self):
        if not self.fecha_inicio_programada or not self.fecha_fin_programada:
            return 0
        return sum(1 for i in range((self.fecha_fin_programada - self.fecha_inicio_programada).days + 1) if (self.fecha_inicio_programada + timedelta(days=i)).weekday() != 6) # 6 = Domingo

    @cached_property
    def meta_diaria(self):
        dias_totales = self.dias_laborables_totales 
        if dias_totales == 0:
            return 0
        return self.meta_total / dias_totales

    def get_pv_diario(self, fecha: date):
        sub_actividades = self.sub_actividades.all()
        if sub_actividades.exists():
            return 0
        total_pv_diario_zonas = 0
        metas_por_zona = self.metas_por_zona.all()
        if metas_por_zona.exists():
            for meta_zona in metas_por_zona:
                fecha_inicio_zona = meta_zona.fecha_inicio_programada or self.fecha_inicio_programada
                fecha_fin_zona = meta_zona.fecha_fin_programada or self.fecha_fin_programada
                if not fecha_inicio_zona or not fecha_fin_zona:
                    continue 
                if (fecha_inicio_zona <= fecha <= fecha_fin_zona) and fecha.weekday() != 6: # 6 = Domingo
                    dias_totales_zona = sum(1 for i in range((fecha_fin_zona - fecha_inicio_zona).days + 1) if (fecha_inicio_zona + timedelta(days=i)).weekday() != 6)
                    if dias_totales_zona > 0:
                        meta_diaria_zona = meta_zona.meta / dias_totales_zona
                        total_pv_diario_zonas += meta_diaria_zona
            return round(total_pv_diario_zonas, 2)
        else:
            return 0

    def get_valor_planeado_a_fecha(self, fecha_corte: date):
        sub_actividades = self.sub_actividades.all()
        if sub_actividades.exists():
            return sum(sub.get_valor_planeado_a_fecha(fecha_corte) for sub in sub_actividades)
        metas_por_zona = self.metas_por_zona.all()
        if metas_por_zona.exists():
            total_pv_zonas = 0
            for meta_zona in metas_por_zona:
                total_pv_zonas += meta_zona.get_valor_planeado_individual(fecha_corte)
            return total_pv_zonas
        else:
            return 0

    def get_valor_planeado_en_rango(self, fecha_inicio_rango: date, fecha_fin_rango: date):
        sub_actividades = self.sub_actividades.all()
        if sub_actividades.exists():
            return sum(sub.get_valor_planeado_en_rango(fecha_inicio_rango, fecha_fin_rango) for sub in sub_actividades)
        total_pv_rango = 0
        current_date = fecha_inicio_rango
        while current_date <= fecha_fin_rango:
            total_pv_rango += self.get_pv_diario(current_date)
            current_date += timedelta(days=1)
        return round(total_pv_rango, 2)

    class Meta:
        verbose_name = "Actividad (WBS)"
        verbose_name_plural = "Actividades (WBS)"
        unique_together = ('nombre', 'padre', 'proyecto')

    def __str__(self):
        if self.padre: return f"{self.padre} → {self.nombre}"
        return self.nombre

class ReportePersonal(models.Model):
    proyecto = models.ForeignKey(Proyecto, on_delete=models.CASCADE)
    fecha = models.DateField()
    empresa = models.ForeignKey(Empresa, on_delete=models.PROTECT)
    cargo = models.ForeignKey(Cargo, on_delete=models.PROTECT)
    partida = models.ForeignKey(PartidaPersonal, on_delete=models.PROTECT)
    area_de_trabajo = models.ForeignKey(AreaDeTrabajo, on_delete=models.PROTECT)
    cantidad = models.PositiveIntegerField()
    class Meta:
        verbose_name_plural = "Reportes de Personal"
        unique_together = ('proyecto', 'fecha', 'empresa', 'cargo', 'partida', 'area_de_trabajo')
    def __str__(self): return f"{self.fecha}: {self.cantidad} x {self.cargo.nombre}"

class AvanceDiario(models.Model):
    actividad = models.ForeignKey(Actividad, on_delete=models.CASCADE, related_name="avances")
    fecha_reporte = models.DateField()
    empresa = models.ForeignKey(
        Empresa,
        on_delete=models.PROTECT,
        default=get_default_empresa_pk,
        verbose_name="Empresa Contratista"
    )
    zonas_avance = models.ManyToManyField(
        AreaDeTrabajo,
        through=AvancePorZona,
        related_name='avances_diarios',
        verbose_name=_("Desglose de Avance por Zona")
    )

    @property
    def cantidad_total(self):
        avances_zonas = self.avances_por_zona.all()
        total = avances_zonas.aggregate(total=Sum('cantidad'))['total']
        return total or 0

    @property
    def cantidad_programada_dia(self):
        return self.actividad.get_pv_diario(self.fecha_reporte)

    class Meta:
        verbose_name_plural = "Avances Diarios"
        unique_together = ('actividad', 'fecha_reporte', 'empresa')

    def __str__(self):
        empresa_nombre = self.empresa.nombre if hasattr(self, 'empresa') and self.empresa else "N/A"
        return f"Avance de {self.actividad.nombre} por {empresa_nombre} en {self.fecha_reporte}"

class ReporteDiarioMaquinaria(models.Model):
    fecha = models.DateField(help_text="Fecha del reporte")
    empresa = models.ForeignKey(Empresa, on_delete=models.PROTECT, help_text="Empresa propietaria o que opera la maquinaria")
    partida = models.ForeignKey(PartidaActividad, on_delete=models.PROTECT, help_text="Partida en la que se utiliza la maquinaria")
    tipo_maquinaria = models.ForeignKey(TipoMaquinaria, on_delete=models.PROTECT, help_text="Tipo de maquinaria reportada")
    zona_trabajo = models.ForeignKey(AreaDeTrabajo, on_delete=models.PROTECT, help_text="Zona de la obra donde se encuentra")
    cantidad_total = models.PositiveIntegerField(help_text="Número total de equipos de este tipo en el día")
    cantidad_activa = models.PositiveIntegerField(help_text="Número de equipos que están activos/operando")
    cantidad_inactiva = models.PositiveIntegerField(help_text="Número de equipos que están inactivos/en descanso")
    observaciones = models.TextField(blank=True, null=True)
    class Meta:
        verbose_name = "Reporte Diario de Maquinaria"
        verbose_name_plural = "Reportes Diarios de Maquinaria"
        ordering = ['-fecha', 'partida', 'tipo_maquinaria']
        unique_together = ('fecha', 'tipo_maquinaria', 'partida', 'empresa', 'zona_trabajo')
    def __str__(self):
        return f"{self.tipo_maquinaria} - {self.fecha}"
    def clean(self):
        if (self.cantidad_activa is not None and self.cantidad_inactiva is not None and self.cantidad_total is not None and
                self.cantidad_activa + self.cantidad_inactiva != self.cantidad_total):
            raise ValidationError("La suma de la cantidad activa e inactiva debe ser igual a la cantidad total.")

class ReporteClima(models.Model):
    fecha = models.DateField(unique=True)
    temp_max_c = models.FloatField(help_text="Temperatura máxima en °C")
    temp_min_c = models.FloatField(help_text="Temperatura mínima en °C")
    sensacion_max_c = models.FloatField(help_text="Sensación térmica máxima en °C (horario laboral)")
    precipitacion_total_mm = models.FloatField(help_text="Precipitación total del día en mm")
    precipitacion_laboral_mm = models.FloatField(help_text="Precipitación en horario laboral (8am-6pm) en mm")
    precipitacion_no_laboral_mm = models.FloatField(help_text="Precipitación fuera de horario laboral en mm")
    condicion_texto = models.CharField(max_length=100, help_text="Descripción del clima (ej. Neblina)")
    condicion_icono = models.URLField(help_text="URL del ícono del clima")
    class Meta:
        verbose_name = "Reporte de Clima"
        verbose_name_plural = "Reportes de Clima"
        ordering = ['-fecha']
    def __str__(self):
        return f"Clima del {self.fecha}"
    
# --- MODELOS BIM ---
    
class TipoElemento(models.Model):
    """ Catálogo de tipos generales de elementos constructivos. Ej: Zapatas, Columnas."""
    nombre = models.CharField(_("Nombre del Tipo de Elemento"), max_length=100, unique=True)
    descripcion = models.TextField(_("Descripción"), blank=True, null=True)

    class Meta:
        verbose_name = _("Tipo de Elemento Constructivo")
        verbose_name_plural = _("Tipos de Elementos Constructivos")
        ordering = ['nombre']

    def __str__(self):
        return self.nombre

class ProcesoConstructivo(models.Model):
    """ Catálogo maestro de todos los pasos individuales posibles. Ej: Excavación, Armado."""
    nombre = models.CharField(_("Nombre del Proceso"), max_length=100, unique=True)
    descripcion = models.TextField(_("Descripción"), blank=True, null=True)

    class Meta:
        verbose_name = _("Proceso Constructivo")
        verbose_name_plural = _("Procesos Constructivos")
        ordering = ['nombre']

    def __str__(self):
        return self.nombre

class PasoProcesoTipoElemento(models.Model):
    """ Define la secuencia ordenada ('receta') de Procesos para cada TipoElemento."""
    tipo_elemento = models.ForeignKey(TipoElemento, on_delete=models.CASCADE, related_name='pasos_proceso')
    proceso = models.ForeignKey(ProcesoConstructivo, on_delete=models.PROTECT)
    orden = models.PositiveIntegerField(_("Orden en la Secuencia"))

    class Meta:
        verbose_name = _("Paso de Proceso por Tipo")
        verbose_name_plural = _("Pasos de Proceso por Tipo")
        unique_together = ('tipo_elemento', 'proceso', 'orden')
        ordering = ['tipo_elemento', 'orden']

    def __str__(self):
        return f"{self.tipo_elemento.nombre} - Paso {self.orden}: {self.proceso.nombre}"

class ElementoConstructivo(models.Model):
    """ 
    Representa cada objeto físico conceptual en la obra (el "código de ejes"). 
    Ej: Zapata Z-10. Este elemento puede tener MÚLTIPLES GUIDs asociados.
    """
    
    identificador_unico = models.CharField(
        _("Código de Ejes / ID Humano"), 
        max_length=255,
        unique=True,
        db_index=True,
        help_text=_("El identificador legible por humanos (ej. ZA-B5) que se usará para buscar.")
    )
    
    # --- CAMPO ELIMINADO ---
    # El campo 'identificador_bim' que estaba aquí ha sido removido.
    # --- FIN CAMPO ELIMINADO ---

    tipo_elemento = models.ForeignKey(TipoElemento, on_delete=models.PROTECT, related_name='elementos')
    descripcion = models.CharField(_("Descripción Adicional"), max_length=255, blank=True, null=True)

    class Meta:
        verbose_name = _("Elemento Constructivo")
        verbose_name_plural = _("Elementos Constructivos")
        ordering = ['identificador_unico'] 

    def __str__(self):
        return self.identificador_unico
    
    @property
    def total_pasos(self):
        if not hasattr(self, '_total_pasos'):
            self._total_pasos = self.tipo_elemento.pasos_proceso.count()
        return self._total_pasos

    @property
    def pasos_completados(self):
        if not hasattr(self, '_pasos_completados'):
            self._pasos_completados = self.avances_proceso.count()
        return self._pasos_completados

    @property
    def status(self):
        # Usamos getattr para poder aprovechar los valores 'anotados' por el
        # queryset de la API, y si no existen, los calculamos.
        completados = getattr(self, 'pasos_completados', self.avances_proceso.count())
        totales = getattr(self, 'total_pasos', self.tipo_elemento.pasos_proceso.count())

        if completados == 0:
            return "Pendiente"
        if totales > 0 and completados >= totales:
            return "Completado"
        return "En Proceso"


# --- NUEVO MODELO ---
class ElementoBIM_GUID(models.Model):
    """
    Almacena los GUIDs individuales del modelo BIM (Revit/Navisworks)
    y los vincula a un único ElementoConstructivo (código de ejes).
    """
    elemento_constructivo = models.ForeignKey(
        ElementoConstructivo, 
        on_delete=models.CASCADE, 
        # related_name nos permite hacer: mi_elemento_constructivo.guids_bim.all()
        related_name='guids_bim', 
        verbose_name=_("Elemento Constructivo (Ejes)")
    )
    identificador_bim = models.CharField(
        _("Identificador BIM (GUID)"),
        max_length=255,
        unique=True,  # Un GUID debe ser único en todo el proyecto
        db_index=True,
        help_text=_("El GUID único inmutable del modelo BIM (ej. 1a2b3c4d-...).")
    )
    
    class Meta:
        verbose_name = _("GUID de Elemento BIM")
        verbose_name_plural = _("GUIDs de Elementos BIM")
        ordering = ['elemento_constructivo', 'identificador_bim']

    def __str__(self):
        # Texto de ayuda para el admin
        return f"{self.identificador_bim} -> {self.elemento_constructivo.identificador_unico}"
# --- FIN NUEVO MODELO ---


class AvanceProcesoElemento(models.Model):
    """ Registra la fecha de finalización de un Paso específico para un Elemento."""
    elemento = models.ForeignKey(ElementoConstructivo, on_delete=models.CASCADE, related_name='avances_proceso')
    paso_proceso = models.ForeignKey(PasoProcesoTipoElemento, on_delete=models.PROTECT)
    fecha_finalizacion = models.DateField(_("Fecha de Finalización"))

    class Meta:
        verbose_name = _("Avance de Proceso por Elemento")
        verbose_name_plural = _("Avances de Proceso por Elemento")
        unique_together = ('elemento', 'paso_proceso')
        ordering = ['elemento', 'paso_proceso__orden']

    def __str__(self):
        return f"{self.elemento} - {self.paso_proceso.proceso.nombre}: {self.fecha_finalizacion}"

    def clean(self):
        if self.elemento_id and self.paso_proceso_id:
            if self.paso_proceso.tipo_elemento != self.elemento.tipo_elemento:
                raise ValidationError(
                    _("El paso de proceso seleccionado ('%(paso)s') no pertenece al tipo de elemento ('%(tipo_elemento)s') de este elemento constructivo."),
                    code='paso_incompatible',
                    params={'paso': self.paso_proceso, 'tipo_elemento': self.elemento.tipo_elemento},
                )
        if self.fecha_finalizacion and self.fecha_finalizacion > date.today():
             raise ValidationError(
                 _("La fecha de finalización no puede ser una fecha futura."), code='fecha_futura'
             )