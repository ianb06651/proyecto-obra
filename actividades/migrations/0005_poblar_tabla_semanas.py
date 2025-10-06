# actividades/migrations/000X_poblar_tabla_semanas.py

from django.db import migrations
from datetime import date, timedelta

def poblar_semanas(apps, schema_editor):
    """
    Puebla la tabla Semana con los registros necesarios hasta la fecha límite.
    Este script es seguro de ejecutar múltiples veces.
    """
    # Obtenemos el modelo 'histórico' para la migración
    Semana = apps.get_model('actividades', 'Semana')
    
    print("\n   > Iniciando la creación/actualización del catálogo de semanas...")

    fecha_actual_inicio = date(2025, 4, 17)
    fecha_limite = date(2027, 1, 27)
    numero_de_semana = 1
    
    while fecha_actual_inicio <= fecha_limite:
        fecha_fin = fecha_actual_inicio + timedelta(days=6)

        # Usamos get_or_create para que la migración sea segura y solo añada las semanas que faltan
        Semana.objects.get_or_create(
            numero_semana=numero_de_semana,
            defaults={
                'fecha_inicio': fecha_actual_inicio,
                'fecha_fin': fecha_fin,
            }
        )
        
        # Preparamos los valores para la siguiente iteración
        fecha_actual_inicio += timedelta(days=7)
        numero_de_semana += 1
    
    print(f"   > Proceso finalizado. Se aseguraron las semanas hasta {fecha_limite}.")


class Migration(migrations.Migration):

    dependencies = [
        # Asegúrate de que este sea el nombre de tu última migración
        ('actividades', '0004_metaporzona_fecha_fin_programada_and_more'),
    ]

    operations = [
        migrations.RunPython(poblar_semanas),
    ]