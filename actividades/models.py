from django.db import models
from django.utils.translation import gettext_lazy as _
from django.core.exceptions import ValidationError
from datetime import date, timedelta
from django.db.models import Sum
from functools import cached_property

# --- CATÁLOGOS ---
# (Sin cambios en Empresa, Cargo, Semana, Proyecto, Partidas, TipoMaquinaria)
class Empresa(models.Model):
    nombre = models.CharField(max_length=255, unique=True)
    def __str__(self): return self.nombre

def get_default_empresa_pk():
    empresa, created = Empresa.objects.get_or_create(nombre='PROSER')
    return empresa.pk

class Cargo(models.Model):
    nombre = models.CharField(max_length=255, unique=True)
    def __str__(self): return self.nombre

# NOTA: Este modelo se usará como el catálogo de "Zonas de Trabajo".
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

# --- NUEVO MODELO INTERMEDIO PARA METAS POR ZONA ---
class MetaPorZona(models.Model):
    actividad = models.ForeignKey('Actividad', on_delete=models.CASCADE, related_name='metas_por_zona')
    zona = models.ForeignKey(AreaDeTrabajo, on_delete=models.CASCADE, verbose_name="Zona de Trabajo")
    meta = models.DecimalField(_("Meta por Zona"), max_digits=12, decimal_places=2)

    # --- NUEVOS CAMPOS ---
    # Hacemos que las fechas sean opcionales. Si son NULL, se usarán las de la Actividad padre.
    fecha_inicio_programada = models.DateField(null=True, blank=True)
    fecha_fin_programada = models.DateField(null=True, blank=True)

    class Meta:
        verbose_name = "Meta por Zona"
        verbose_name_plural = "Metas por Zona"
        unique_together = ('actividad', 'zona')

    # --- NUEVO MÉTODO AUXILIAR ---
    # Este método encapsula la lógica de cálculo para una sola zona.
    def get_valor_planeado_individual(self, fecha_corte: date):
        # Usa las fechas de la zona si existen, si no, las de la actividad padre.
        fecha_inicio = self.fecha_inicio_programada or self.actividad.fecha_inicio_programada
        fecha_fin = self.fecha_fin_programada or self.actividad.fecha_fin_programada

        if not fecha_inicio or not fecha_fin:
            return 0
        if fecha_corte < fecha_inicio:
            return 0
        if fecha_corte >= fecha_fin:
            return self.meta

        dias_totales = sum(1 for i in range((fecha_fin - fecha_inicio).days + 1) if (fecha_inicio + timedelta(days=i)).weekday() != 6)
        if dias_totales == 0:
            return 0
        
        meta_diaria_zona = self.meta / dias_totales

        dias_transcurridos = sum(1 for i in range((fecha_corte - fecha_inicio).days + 1) if (fecha_inicio + timedelta(days=i)).weekday() != 6)
        
        return round(dias_transcurridos * meta_diaria_zona, 2)

# --- NUEVO MODELO INTERMEDIO PARA AVANCES POR ZONA ---
class AvancePorZona(models.Model):
    """Modelo 'through' para almacenar el avance de un día en una zona específica."""
    avance_diario = models.ForeignKey('AvanceDiario', on_delete=models.CASCADE, related_name='avances_por_zona')
    zona = models.ForeignKey(AreaDeTrabajo, on_delete=models.CASCADE, verbose_name="Zona de Trabajo")
    cantidad = models.DecimalField(_("Cantidad por Zona"), max_digits=12, decimal_places=2)

    class Meta:
        verbose_name = "Avance por Zona"
        verbose_name_plural = "Avances por Zona"
        unique_together = ('avance_diario', 'zona')


# --- MODELO JERÁRQUICO DE ACTIVIDAD (WBS) ---
class Actividad(models.Model):
    nombre = models.CharField(_("Nombre de Actividad/Categoría"), max_length=255)
    padre = models.ForeignKey(
        'self', on_delete=models.CASCADE, null=True, blank=True,
        related_name='sub_actividades', verbose_name=_("Categoría Padre")
    )
    proyecto = models.ForeignKey(Proyecto, on_delete=models.CASCADE, related_name='actividades')
    partida = models.ForeignKey(PartidaActividad, on_delete=models.PROTECT, null=True, blank=True)
    
    # --- MODIFICACIÓN: Campo para meta general ---
    # Renombrado de 'meta_cantidad_total' a 'meta_general'
    # Se hace nullable para indicar que puede no usarse si hay desglose por zona.
    meta_general = models.DecimalField(
        _("Meta General"), max_digits=12, decimal_places=2, null=True, blank=True,
        help_text="Usar si la meta no se desglosa por zona. Ej: 66470"
    )

    # --- NUEVO: Relación ManyToMany para metas por zona ---
    zonas_meta = models.ManyToManyField(
        AreaDeTrabajo,
        through=MetaPorZona,
        related_name='actividades_meta',
        verbose_name=_("Desglose de Metas por Zona")
    )
    
    unidad_medida = models.CharField(_("Unidad de Medida"), max_length=50, blank=True, help_text="Ej: m3, Ton, Pza")
    fecha_inicio_programada = models.DateField(null=True, blank=True)
    fecha_fin_programada = models.DateField(null=True, blank=True)
    
    # --- NUEVO: Propiedad para calcular la meta total dinámicamente ---
    @property
    def meta_total(self):
        """
        Calcula la meta total. Suma las metas por zona si existen,
        de lo contrario, devuelve la meta general.
        """
        # Usamos 'metas_por_zona' (related_name del FK en MetaPorZona)
        metas_zonas = self.metas_por_zona.all()
        if metas_zonas.exists():
            total = metas_zonas.aggregate(total=Sum('meta'))['total']
            return total or 0
        return self.meta_general or 0

    # (Lógica existente de la clase sin cambios)
    @cached_property
    def cantidad_total_calculada(self):
        sub_actividades = self.sub_actividades.all()
        if sub_actividades.exists():
            return sum(sub.cantidad_total_calculada for sub in sub_actividades)
        # NOTA: La lógica original usaba meta_cantidad_total. Ahora usará la propiedad meta_total.
        return self.meta_total

    @cached_property
    def dias_laborables_totales(self):
        if not self.fecha_inicio_programada or not self.fecha_fin_programada:
            return 0
        return sum(1 for i in range((self.fecha_fin_programada - self.fecha_inicio_programada).days + 1) if (self.fecha_inicio_programada + timedelta(days=i)).weekday() != 6)

    @cached_property
    def meta_diaria(self):
        if self.dias_laborables_totales == 0:
            return 0
        # NOTA: Usa la nueva propiedad meta_total para el cálculo
        return self.meta_total / self.dias_laborables_totales

    def get_pv_diario(self, fecha: date):
        if self.sub_actividades.exists(): return 0
        if not all([self.fecha_inicio_programada, self.fecha_fin_programada, self.meta_total > 0]): return 0
        if not (self.fecha_inicio_programada <= fecha <= self.fecha_fin_programada) or fecha.weekday() == 6: return 0
        return round(self.meta_diaria, 2)

    # actividades/models.py -> dentro de la clase Actividad

    def get_valor_planeado_a_fecha(self, fecha_corte: date):
        # Primero, manejamos las actividades que son 'padre' (agrupadoras)
        sub_actividades = self.sub_actividades.all()
        if sub_actividades.exists():
            return sum(sub.get_valor_planeado_a_fecha(fecha_corte) for sub in sub_actividades)

        # --- LÓGICA REESCRITA ---
        metas_por_zona = self.metas_por_zona.all()

        # CASO 1: La actividad tiene desglose por zonas
        if metas_por_zona.exists():
            total_pv_zonas = 0
            # Iteramos sobre cada meta de zona y calculamos su PV individualmente
            for meta_zona in metas_por_zona:
                total_pv_zonas += meta_zona.get_valor_planeado_individual(fecha_corte)
            return total_pv_zonas

        # CASO 2: La actividad NO tiene desglose (comportamiento antiguo)
        else:
            if not self.fecha_inicio_programada: return 0
            if fecha_corte < self.fecha_inicio_programada: return 0
            # Usamos meta_total para ser consistentes, aunque aquí será igual a meta_general
            if fecha_corte >= self.fecha_fin_programada: return self.meta_total

            dias_laborables_transcurridos = sum(1 for i in range((fecha_corte - self.fecha_inicio_programada).days + 1) if (self.fecha_inicio_programada + timedelta(days=i)).weekday() != 6)
            
            # Usamos la propiedad meta_diaria que ya calcula en base a meta_total
            return round(dias_laborables_transcurridos * self.meta_diaria, 2)

    def get_valor_planeado_en_rango(self, fecha_inicio_rango: date, fecha_fin_rango: date):
        sub_actividades = self.sub_actividades.all()
        if sub_actividades.exists():
            return sum(sub.get_valor_planeado_en_rango(fecha_inicio_rango, fecha_fin_rango) for sub in sub_actividades)
        if not self.fecha_inicio_programada or not self.fecha_fin_programada: return 0
        fecha_inicio_calculo = max(self.fecha_inicio_programada, fecha_inicio_rango)
        fecha_fin_calculo = min(self.fecha_fin_programada, fecha_fin_rango)
        if fecha_fin_calculo < fecha_inicio_calculo: return 0
        total_pv_rango = sum(self.get_pv_diario(fecha_inicio_calculo + timedelta(days=i)) for i in range((fecha_fin_calculo - fecha_inicio_calculo).days + 1))
        return round(total_pv_rango, 2)

    class Meta:
        verbose_name = "Actividad (WBS)"
        verbose_name_plural = "Actividades (WBS)"
        unique_together = ('nombre', 'padre', 'proyecto')

    def __str__(self):
        if self.padre: return f"{self.padre} → {self.nombre}"
        return self.nombre

# --- MODELOS DE REGISTROS ---
class ReportePersonal(models.Model):
    # (Sin cambios en ReportePersonal)
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
    
    # --- MODIFICACIÓN: Campo para avance general ---
    # Renombrado de 'cantidad_realizada_dia' a 'cantidad_general'
    # Se hace nullable para que sea opcional si se usa el desglose por zona.
    cantidad_general = models.DecimalField(
        _("Cantidad General"), max_digits=12, decimal_places=2, null=True, blank=True
    )
    
    empresa = models.ForeignKey(
        Empresa,
        on_delete=models.PROTECT,
        default=get_default_empresa_pk,
        verbose_name="Empresa Contratista"
    )

    # --- MODIFICACIÓN: Relación ManyToMany para avances por zona ---
    # Se reemplaza el campo 'zonas' anterior por este que usa un modelo 'through'.
    zonas_avance = models.ManyToManyField(
        AreaDeTrabajo,
        through=AvancePorZona,
        related_name='avances_diarios',
        verbose_name=_("Desglose de Avance por Zona")
    )
    
    # --- NUEVO: Propiedad para calcular la cantidad total dinámicamente ---
    @property
    def cantidad_total(self):
        """
        Calcula la cantidad total del avance. Suma las cantidades por zona si existen,
        de lo contrario, devuelve la cantidad general.
        """
        # Usamos 'avances_por_zona' (related_name del FK en AvancePorZona)
        avances_zonas = self.avances_por_zona.all()
        if avances_zonas.exists():
            total = avances_zonas.aggregate(total=Sum('cantidad'))['total']
            return total or 0
        return self.cantidad_general or 0

    @property
    def cantidad_programada_dia(self):
        return self.actividad.get_pv_diario(self.fecha_reporte)

    class Meta:
        verbose_name_plural = "Avances Diarios"
        unique_together = ('actividad', 'fecha_reporte', 'empresa')

    def __str__(self):
        if hasattr(self, 'empresa') and self.empresa:
            return f"Avance de {self.actividad.nombre} por {self.empresa.nombre} en {self.fecha_reporte}"
        return f"Avance de {self.actividad.nombre} en {self.fecha_reporte}"


class ReporteDiarioMaquinaria(models.Model):
    # (Sin cambios en ReporteDiarioMaquinaria)
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
        if self.cantidad_activa + self.cantidad_inactiva != self.cantidad_total:
            raise ValidationError("La suma de la cantidad activa e inactiva debe ser igual a la cantidad total.")

class ReporteClima(models.Model):
    # (Sin cambios en ReporteClima)
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