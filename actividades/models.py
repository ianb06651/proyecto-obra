from django.db import models
from django.utils.translation import gettext_lazy as _
from django.core.exceptions import ValidationError
from datetime import date, timedelta
from django.db.models import Sum
from functools import cached_property

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

class Proyecto(models.Model):
    nombre = models.CharField(_("Nombre del Proyecto"), max_length=255, unique=True)
    fecha_inicio = models.DateField(_("Fecha de Inicio"))
    fecha_fin_estimada = models.DateField(_("Fecha de Finalización Estimada"))

    def get_valor_planeado_a_fecha(self, fecha_corte: date):
        actividades_raiz = self.actividades.filter(padre__isnull=True)
        return sum(act.get_valor_planeado_a_fecha(fecha_corte) for act in actividades_raiz)

    # --- NUEVO MÉTODO AÑADIDO ---
    def get_valor_planeado_en_rango(self, fecha_inicio_rango: date, fecha_fin_rango: date):
        """Suma el PV de las actividades raíz dentro de un rango de fechas."""
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

# --- MODELO JERÁRQUICO DE ACTIVIDAD (WBS) - VERSIÓN OPTIMIZADA ---
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

    @cached_property
    def cantidad_total_calculada(self):
        """Suma recursivamente la meta de las actividades hijas."""
        sub_actividades = self.sub_actividades.all()
        if sub_actividades.exists():
            return sum(sub.cantidad_total_calculada for sub in sub_actividades)
        return self.meta_cantidad_total

    @cached_property
    def dias_laborables_totales(self):
        """Calcula una sola vez los días laborables (L-S) del rango de la actividad."""
        if not self.fecha_inicio_programada or not self.fecha_fin_programada:
            return 0
        return sum(1 for i in range((self.fecha_fin_programada - self.fecha_inicio_programada).days + 1) if (self.fecha_inicio_programada + timedelta(days=i)).weekday() != 6)

    @cached_property
    def meta_diaria(self):
        """Calcula una sola vez la meta diaria distribuida en días laborables."""
        if self.dias_laborables_totales == 0:
            return 0
        return self.meta_cantidad_total / self.dias_laborables_totales

    def get_pv_diario(self, fecha: date):
        """Devuelve la meta planeada para un solo día específico."""
        # Las categorías padre no tienen PV diario propio, solo acumulan el de sus hijos.
        if self.sub_actividades.exists():
            return 0
        
        if not all([self.fecha_inicio_programada, self.fecha_fin_programada, self.meta_cantidad_total > 0]):
            return 0
        
        # El PV es 0 si la fecha está fuera del rango o es domingo.
        if not (self.fecha_inicio_programada <= fecha <= self.fecha_fin_programada) or fecha.weekday() == 6:
            return 0
            
        return round(self.meta_diaria, 2)
    
    def get_valor_planeado_a_fecha(self, fecha_corte: date):
        """Calcula el PV acumulado hasta una fecha de corte."""
        # Si es una categoría padre, su PV es la suma del PV de sus hijos.
        sub_actividades = self.sub_actividades.all()
        if sub_actividades.exists():
            return sum(sub.get_valor_planeado_a_fecha(fecha_corte) for sub in sub_actividades)

        if not self.fecha_inicio_programada: return 0
        
        # Lógica de cálculo acumulado correcta.
        if fecha_corte < self.fecha_inicio_programada: return 0
        if fecha_corte >= self.fecha_fin_programada: return self.meta_cantidad_total # Devuelve el total si ya pasó la fecha.

        dias_laborables_transcurridos = sum(1 for i in range((fecha_corte - self.fecha_inicio_programada).days + 1) if (self.fecha_inicio_programada + timedelta(days=i)).weekday() != 6)
        
        return round(dias_laborables_transcurridos * self.meta_diaria, 2)
    
    def get_valor_planeado_en_rango(self, fecha_inicio_rango: date, fecha_fin_rango: date):
        """
        Calcula el PV sumando los valores diarios únicamente dentro del rango especificado.
        """
        sub_actividades = self.sub_actividades.all()
        if sub_actividades.exists():
            return sum(sub.get_valor_planeado_en_rango(fecha_inicio_rango, fecha_fin_rango) for sub in sub_actividades)

        if not self.fecha_inicio_programada or not self.fecha_fin_programada:
            return 0

        # Determinamos el período de cálculo real que se solapa con el rango solicitado
        fecha_inicio_calculo = max(self.fecha_inicio_programada, fecha_inicio_rango)
        fecha_fin_calculo = min(self.fecha_fin_programada, fecha_fin_rango)

        if fecha_fin_calculo < fecha_inicio_calculo:
            return 0

        total_pv_rango = 0
        current_date = fecha_inicio_calculo
        while current_date <= fecha_fin_calculo:
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

# --- MODELOS DE REGISTROS ---
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
    cantidad_realizada_dia = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    
    @property
    def cantidad_programada_dia(self):
        return self.actividad.get_pv_diario(self.fecha_reporte)

    class Meta:
        verbose_name_plural = "Avances Diarios"
        unique_together = ('actividad', 'fecha_reporte')
        
    def __str__(self):
        return f"Avance de {self.actividad.nombre} en {self.fecha_reporte}"

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