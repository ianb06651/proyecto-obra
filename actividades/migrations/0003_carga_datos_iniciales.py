# actividades/migrations/000X_carga_datos_iniciales.py

from django.db import migrations
from datetime import date, timedelta

# --- LÓGICA DE CÁLCULO COPIADA DEL MODELO ---
# Esta es la función que antes estaba en models.py. La ponemos aquí
# para que la migración pueda usarla con los modelos históricos.
def calcular_pv_para_migracion(actividad, fecha_corte, apps):
    Actividad = apps.get_model('actividades', 'Actividad')
    
    # Buscamos las sub-actividades de forma manual
    sub_actividades_qs = Actividad.objects.filter(padre_id=actividad.id)
    
    if sub_actividades_qs.exists():
        return sum(calcular_pv_para_migracion(sub, fecha_corte, apps) for sub in sub_actividades_qs)

    if not all([actividad.fecha_inicio_programada, actividad.fecha_fin_programada, actividad.meta_cantidad_total > 0]):
        return 0
    if fecha_corte < actividad.fecha_inicio_programada:
        return 0
    if fecha_corte >= actividad.fecha_fin_programada:
        return actividad.meta_cantidad_total

    duracion_total_dias = (actividad.fecha_fin_programada - actividad.fecha_inicio_programada).days + 1
    dias_transcurridos = (fecha_corte - actividad.fecha_inicio_programada).days + 1
    
    if duracion_total_dias <= 0: return 0
    valor_planeado_dia = actividad.meta_cantidad_total / duracion_total_dias
    return round(dias_transcurridos * valor_planeado_dia, 2)


# --- LÓGICA PARA LA CARGA DE DATOS ---

def crear_semanas_del_anio(apps, schema_editor):
    Semana = apps.get_model('actividades', 'Semana')
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
    Actividad = apps.get_model('actividades', 'Actividad')
    AvanceDiario = apps.get_model('actividades', 'AvanceDiario')

    fecha_inicio_avance = date(2025, 5, 2)
    fecha_fin_avance = date(2025, 7, 26)
    avance_diario_fijo = 1996.00

    try:
        despalme = Actividad.objects.get(nombre__iexact="Despalme")
    except Actividad.DoesNotExist:
        print("\nADVERTENCIA: No se encontró la actividad 'Despalme'.")
        return

    print("Creando registros de avance diario para 'Despalme' (excluyendo domingos)...")
    current_date = fecha_inicio_avance
    while current_date <= fecha_fin_avance:
        if current_date.weekday() != 6:
            # CAMBIO: Usamos nuestra nueva función local en lugar del método del modelo
            pv_cumulativo_hoy = calcular_pv_para_migracion(despalme, current_date, apps)
            pv_cumulativo_ayer = calcular_pv_para_migracion(despalme, current_date - timedelta(days=1), apps)
            pv_del_dia = pv_cumulativo_hoy - pv_cumulativo_ayer

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
    crear_semanas_del_anio(apps, schema_editor)
    crear_avances_masivos_despalme(apps, schema_editor)

def eliminar_datos_cargados(apps, schema_editor):
    # ... (la lógica de borrado no cambia)
    pass

class Migration(migrations.Migration):

    dependencies = [
        ('actividades', '0002_crear_superuser'),
    ]

    operations = [
        migrations.RunPython(carga_inicial, reverse_code=eliminar_datos_cargados),
    ]