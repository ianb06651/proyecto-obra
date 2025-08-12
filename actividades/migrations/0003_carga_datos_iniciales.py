# actividades/migrations/0004_carga_datos_iniciales.py

from django.db import migrations
from datetime import date, timedelta

# --- LÓGICA PARA LA CARGA DE DATOS ---

def crear_semanas_del_anio(apps, schema_editor):
    """
    Crea 52 semanas para el año, iniciando en la fecha especificada.
    """
    Semana = apps.get_model('actividades', 'Semana')
    
    # CAMBIO: Fecha de inicio corregida al 24 de abril de 2025
    fecha_inicio_semana1 = date(2025, 4, 24)
    
    print("\nCreando registros de Semanas...")
    for i in range(52):
        numero = i + 1
        inicio = fecha_inicio_semana1 + timedelta(weeks=i)
        fin = inicio + timedelta(days=6)
        
        Semana.objects.get_or_create(
            numero_semana=numero,
            defaults={'fecha_inicio': inicio, 'fecha_fin': fin}
        )
    print("Registros de Semanas creados.")

def crear_avances_masivos_despalme(apps, schema_editor):
    """
    Crea registros de AvanceDiario para la actividad "Despalme"
    con un valor fijo durante un rango de fechas.
    """
    Actividad = apps.get_model('actividades', 'Actividad')
    AvanceDiario = apps.get_model('actividades', 'AvanceDiario')

    fecha_inicio_avance = date(2025, 5, 2)
    fecha_fin_avance = date(2025, 7, 26)
    avance_diario_fijo = 1996.00

    try:
        despalme = Actividad.objects.get(nombre__iexact="Despalme")
        print(f"Encontrada la actividad: {despalme}")
    except Actividad.DoesNotExist:
        print("\nADVERTENCIA: No se encontró la actividad 'Despalme'. Saltando la creación de avances.")
        return
    except Actividad.MultipleObjectsReturned:
        print("\nADVERTENCIA: Se encontraron múltiples actividades llamadas 'Despalme'. Saltando la creación de avances.")
        return

    print("Creando registros de avance diario para 'Despalme'...")
    current_date = fecha_inicio_avance
    while current_date <= fecha_fin_avance:
        pv_del_dia = despalme.get_valor_planeado_a_fecha(current_date) - despalme.get_valor_planeado_a_fecha(current_date - timedelta(days=1))

        AvanceDiario.objects.get_or_create(
            actividad=despalme,
            fecha_reporte=current_date,
            defaults={
                'cantidad_programada_dia': pv_del_dia,
                'cantidad_realizada_dia': avance_diario_fijo
            }
        )
        current_date += timedelta(days=1)
    print("Registros de avance para 'Despalme' creados.")


def carga_inicial(apps, schema_editor):
    """Función que ejecuta todas las sub-funciones de carga."""
    crear_semanas_del_anio(apps, schema_editor)
    crear_avances_masivos_despalme(apps, schema_editor)

class Migration(migrations.Migration):

    dependencies = [
        ('actividades', '0002_crear_superuser'), # Asegúrate que esta sea tu última migración
    ]

    operations = [
        migrations.RunPython(carga_inicial, reverse_code=migrations.RunPython.noop),
    ]