from django.db import models
from django.utils.translation import gettext_lazy as _
from django.core.exceptions import ValidationError
from datetime import date, timedelta

# --- CATÁLOGOS ---
class Empresa(models.Model):
    nombre = models.CharField(max_length=255, unique=True)
    def __str__(self): return self.nombre

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

class PartidaActividad(models.Model):
    nombre = models.CharField(max_length=255, unique=True)
    class Meta: verbose_name_plural = "Partidas de Actividades"
    def __str__(self): return self.nombre

class PartidaPersonal(models.Model):
    nombre = models.CharField(max_length=255, unique=True)
    class Meta: verbose_name_plural = "Partidas de Personal"
    def __str__(self): return self.nombre
    
class Proyecto(models.Model):
    nombre = models.CharField(_("Nombre del Proyecto"), max_length=255, unique=True)
    fecha_inicio = models.DateField(_("Fecha de Inicio"))
    fecha_fin_estimada = models.DateField(_("Fecha de Finalización Estimada"))

    def get_valor_planeado_a_fecha(self, fecha_corte: date):
        """
        Calcula el PV total del proyecto sumando el PV
        de todas sus actividades de nivel superior.
        """
        actividades_raiz = self.actividades.filter(padre__isnull=True)
        total_pv = sum(act.get_valor_planeado_a_fecha(fecha_corte) for act in actividades_raiz)
        return total_pv

    def __str__(self): 
        return self.nombre

# --- MODELO JERÁRQUICO DE ACTIVIDAD (WBS) ---
class Actividad(models.Model):
    nombre = models.CharField(_("Nombre de Actividad/Categoría"), max_length=255)
    padre = models.ForeignKey(
        'self', on_delete=models.CASCADE, null=True, blank=True,
        related_name='sub_actividades', verbose_name=_("Categoría Padre")
    )
    proyecto = models.ForeignKey(Proyecto, on_delete=models.CASCADE, related_name='actividades')
    
    partida = models.ForeignKey(PartidaActividad, on_delete=models.PROTECT, null=True, blank=True)
    meta_cantidad_total = models.DecimalField(
        _("Meta de Cantidad"), max_digits=12, decimal_places=2, default=0.00,
        help_text="Solo llenar para actividades finales (sin hijos). Ej: 66470"
    )
    unidad_medida = models.CharField(_("Unidad de Medida"), max_length=50, blank=True, help_text="Ej: m3, Ton, Pza")
    fecha_inicio_programada = models.DateField(null=True, blank=True)
    fecha_fin_programada = models.DateField(null=True, blank=True)

    @property
    def cantidad_total_calculada(self):
        sub_actividades = self.sub_actividades.all()
        if sub_actividades.exists():
            return sum(sub.cantidad_total_calculada for sub in sub_actividades)
        return self.meta_cantidad_total

    def get_valor_planeado_a_fecha(self, fecha_corte: date):
        sub_actividades = self.sub_actividades.all()
        if sub_actividades.exists():
            return sum(sub.get_valor_planeado_a_fecha(fecha_corte) for sub in sub_actividades)

        if not all([self.fecha_inicio_programada, self.fecha_fin_programada, self.meta_cantidad_total > 0]):
            return 0
        if fecha_corte < self.fecha_inicio_programada:
            return 0
        if fecha_corte >= self.fecha_fin_programada:
            return self.meta_cantidad_total

        duracion_total_dias = (self.fecha_fin_programada - self.fecha_inicio_programada).days + 1
        dias_transcurridos = (fecha_corte - self.fecha_inicio_programada).days + 1
        
        if duracion_total_dias <= 0: return 0
        valor_planeado_dia = self.meta_cantidad_total / duracion_total_dias
        return round(dias_transcurridos * valor_planeado_dia, 2)

    class Meta:
        verbose_name = "Actividad (WBS)"
        verbose_name_plural = "Actividades (WBS)"
        unique_together = ('nombre', 'padre', 'proyecto')

    def __str__(self):
        if self.padre:
            return f"{self.padre} → {self.nombre}"
        return self.nombre

# --- MODELOS DE REGISTROS ---
class ReportePersonal(models.Model):
    fecha = models.DateField()
    empresa = models.ForeignKey(Empresa, on_delete=models.PROTECT)
    cargo = models.ForeignKey(Cargo, on_delete=models.PROTECT)
    partida = models.ForeignKey(PartidaPersonal, on_delete=models.PROTECT)
    area_de_trabajo = models.ForeignKey(AreaDeTrabajo, on_delete=models.PROTECT)
    cantidad = models.PositiveIntegerField()
    class Meta: verbose_name_plural = "Reportes de Personal"
    def __str__(self): return f"{self.fecha}: {self.cantidad} x {self.cargo.nombre}"

class AvanceDiario(models.Model):
    actividad = models.ForeignKey(Actividad, on_delete=models.CASCADE)
    fecha_reporte = models.DateField()
    cantidad_programada_dia = models.DecimalField(max_digits=12, decimal_places=2)
    cantidad_realizada_dia = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    class Meta:
        verbose_name_plural = "Avances Diarios"
        unique_together = ('actividad', 'fecha_reporte')
        
    def __str__(self):
        return f"Avance de {self.actividad.nombre} en {self.fecha_reporte}"
    
class TipoMaquinaria(models.Model):
    nombre = models.CharField(max_length=100, unique=True, help_text="Ej: Retroexcavadora")
    partida = models.ForeignKey('PartidaActividad', on_delete=models.SET_NULL, null=True, blank=True, help_text="Partida a la que suele pertenecer esta maquinaria")
    class Meta:
        verbose_name = "Tipo de Maquinaria"
        verbose_name_plural = "Tipos de Maquinaria"
        ordering = ['nombre']
    def __str__(self):
        return self.nombre

class ReporteDiarioMaquinaria(models.Model):
    fecha = models.DateField(help_text="Fecha del reporte")
    empresa = models.ForeignKey('Empresa', on_delete=models.PROTECT, help_text="Empresa propietaria o que opera la maquinaria")
    partida = models.ForeignKey('PartidaActividad', on_delete=models.PROTECT, help_text="Partida en la que se utiliza la maquinaria")
    tipo_maquinaria = models.ForeignKey(TipoMaquinaria, on_delete=models.PROTECT, help_text="Tipo de maquinaria reportada")
    zona_trabajo = models.ForeignKey('AreaDeTrabajo', on_delete=models.PROTECT, help_text="Zona de la obra donde se encuentra")
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