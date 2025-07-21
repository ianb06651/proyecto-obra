from django.db import models
from django.conf import settings
from django.core.exceptions import ValidationError

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

# --- TABLAS SEPARADAS PARA PARTIDAS ---
class PartidaActividad(models.Model):
    nombre = models.CharField(max_length=255, unique=True)
    class Meta: verbose_name_plural = "Partidas de Actividades"
    def __str__(self): return self.nombre

class PartidaPersonal(models.Model):
    nombre = models.CharField(max_length=255, unique=True)
    class Meta: verbose_name_plural = "Partidas de Personal"
    def __str__(self): return self.nombre

# --- MODELOS PRINCIPALES (ACTUALIZADOS) ---
class Actividad(models.Model):
    partida = models.ForeignKey(PartidaActividad, on_delete=models.PROTECT) # ACTUALIZADO
    nombre_actividad = models.CharField(max_length=255)
    meta_cantidad_total = models.DecimalField(max_digits=12, decimal_places=2)
    unidad_medida = models.CharField(max_length=50)
    fecha_inicio_programada = models.DateField()
    fecha_fin_programada = models.DateField()
    class Meta: verbose_name_plural = "Actividades"
    def __str__(self): return self.nombre_actividad

class ReportePersonal(models.Model):
    fecha = models.DateField()
    empresa = models.ForeignKey(Empresa, on_delete=models.PROTECT)
    cargo = models.ForeignKey(Cargo, on_delete=models.PROTECT)
    partida = models.ForeignKey(PartidaPersonal, on_delete=models.PROTECT) # ACTUALIZADO
    area_de_trabajo = models.ForeignKey(AreaDeTrabajo, on_delete=models.PROTECT)
    cantidad = models.PositiveIntegerField()
    class Meta: verbose_name_plural = "Reportes de Personal"
    def __str__(self): return f"{self.fecha}: {self.cantidad} x {self.cargo.nombre}"

# --- MODELOS DE REGISTROS DIARIOS ---
class AvanceDiario(models.Model):
    actividad = models.ForeignKey(Actividad, on_delete=models.CASCADE)
    fecha_reporte = models.DateField()
    cantidad_programada_dia = models.DecimalField(max_digits=12, decimal_places=2)
    cantidad_realizada_dia = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    class Meta:
        verbose_name_plural = "Avances Diarios"
        unique_together = ('actividad', 'fecha_reporte')
    def __str__(self): return f"Avance de {self.actividad.nombre_actividad} en {self.fecha_reporte}"
    
class TipoMaquinaria(models.Model):
    """
    Catálogo para los tipos de maquinaria.
    Ej: Retroexcavadora, Pata de Cabra, Vibrocompactador.
    """
    nombre = models.CharField(max_length=100, unique=True, help_text="Ej: Retroexcavadora")
    partida = models.ForeignKey('PartidaActividad', on_delete=models.SET_NULL, null=True, blank=True, help_text="Partida a la que suele pertenecer esta maquinaria")

    class Meta:
        verbose_name = "Tipo de Maquinaria"
        verbose_name_plural = "Tipos de Maquinaria"
        ordering = ['nombre']

    def __str__(self):
        return self.nombre

class ReporteDiarioMaquinaria(models.Model):
    """
    Registro diario de la cantidad y estado de la maquinaria por tipo.
    Este modelo corresponde a una fila de tu tabla de registro.
    """
    # --- Campos de Selección ---
    fecha = models.DateField(help_text="Fecha del reporte")
    empresa = models.ForeignKey('Empresa', on_delete=models.PROTECT, help_text="Empresa propietaria o que opera la maquinaria")
    partida = models.ForeignKey('PartidaActividad', on_delete=models.PROTECT, help_text="Partida en la que se utiliza la maquinaria")
    tipo_maquinaria = models.ForeignKey(TipoMaquinaria, on_delete=models.PROTECT, help_text="Tipo de maquinaria reportada")
    zona_trabajo = models.ForeignKey('AreaDeTrabajo', on_delete=models.PROTECT, help_text="Zona de la obra donde se encuentra")

    # --- Cantidades ---
    cantidad_total = models.PositiveIntegerField(help_text="Número total de equipos de este tipo en el día")
    cantidad_activa = models.PositiveIntegerField(help_text="Número de equipos que están activos/operando")
    cantidad_inactiva = models.PositiveIntegerField(help_text="Número de equipos que están inactivos/en descanso")
    
    # --- Campo adicional para notas ---
    observaciones = models.TextField(blank=True, null=True)

    class Meta:
        verbose_name = "Reporte Diario de Maquinaria"
        verbose_name_plural = "Reportes Diarios de Maquinaria"
        ordering = ['-fecha', 'partida', 'tipo_maquinaria']
        # Restricción para evitar registros duplicados para el mismo día, tipo de maq, y partida
        unique_together = ('fecha', 'tipo_maquinaria', 'partida', 'empresa', 'zona_trabajo')

    def __str__(self):
        return f"{self.tipo_maquinaria} - {self.fecha}"

    def clean(self):
        # Validación para asegurar que las cantidades cuadren
        if self.cantidad_activa + self.cantidad_inactiva != self.cantidad_total:
            raise ValidationError(
                "La suma de la cantidad activa e inactiva debe ser igual a la cantidad total."
            )