# actividades/migrations/0014_migrar_datos_zonas.py

from django.db import migrations

def migrar_datos_a_zonas(apps, schema_editor):
    # Obtenemos los modelos históricos
    Cronograma = apps.get_model('actividades', 'Cronograma')
    CronogramaPorZona = apps.get_model('actividades', 'CronogramaPorZona')

    # Iteramos sobre todas las tareas existentes
    for tarea in Cronograma.objects.all():
        # Obtenemos las zonas que tenía asignada esta tarea (usando el campo legacy)
        zonas_asignadas = tarea.zonas.all()
        
        for zona in zonas_asignadas:
            # Creamos el registro específico para esta zona copiando las fechas maestras
            CronogramaPorZona.objects.create(
                tarea=tarea,
                zona=zona,
                fecha_inicio_prog=tarea.fecha_inicio_prog,
                fecha_fin_prog=tarea.fecha_fin_prog,
                fecha_inicio_real=tarea.fecha_inicio_real,
                fecha_fin_real=tarea.fecha_fin_real
            )

class Migration(migrations.Migration):

    dependencies = [

        ('actividades', '0013_alter_cronograma_options_alter_cronograma_zonas_and_more'), 
    ]

    operations = [
        migrations.RunPython(migrar_datos_a_zonas),
    ]