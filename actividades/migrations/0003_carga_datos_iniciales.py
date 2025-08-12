from django.db import migrations, transaction
from datetime import date, timedelta

def carga_inicial(apps, schema_editor):
    Semana = apps.get_model('actividades', 'Semana')
    Actividad = apps.get_model('actividades', 'Actividad')
    AvanceDiario = apps.get_model('actividades', 'AvanceDiario')

    # --- 1. CREACIÓN DE SEMANAS (CON MÁS FEEDBACK) ---
    print("\n[+] Iniciando creación de Semanas...")
    fecha_inicio_semana1 = date(2025, 4, 24)
    for i in range(52):
        numero = i + 1
        inicio = fecha_inicio_semana1 + timedelta(weeks=i)
        fin = inicio + timedelta(days=6)
        obj, created = Semana.objects.get_or_create(
            numero_semana=numero,
            defaults={'fecha_inicio': inicio, 'fecha_fin': fin}
        )
        if created:
            print(f"  - Semana {numero} creada.")
    print("[+] Creación de Semanas completada.")

    # --- 2. CREACIÓN DE AVANCES (CON BÚSQUEDA ROBUSTA) ---
    print("\n[+] Iniciando creación de Avances para 'Despalme'...")
    
    # Búsqueda más robusta: filtramos y tomamos el primero.
    despalme = Actividad.objects.filter(nombre__iexact="Despalme").first()

    if not despalme:
        print("[!] ADVERTENCIA: No se encontró la actividad 'Despalme'. No se crearán avances.")
        return # Termina la función si no hay nada que hacer

    print(f"  - Actividad encontrada: '{despalme}' (ID: {despalme.pk})")
    
    fecha_inicio_avance = date(2025, 5, 2)
    fecha_fin_avance = date(2025, 7, 26)
    avance_diario_fijo = 1996.00
    
    registros_creados = 0
    current_date = fecha_inicio_avance
    while current_date <= fecha_fin_avance:
        if current_date.weekday() != 6: # Excluir Domingos
            
            # La lógica de PV no es necesaria para la carga inicial de datos históricos
            # Simplemente registramos el avance real.
            obj, created = AvanceDiario.objects.get_or_create(
                actividad=despalme,
                fecha_reporte=current_date,
                defaults={'cantidad_realizada_dia': avance_diario_fijo, 'cantidad_programada_dia': 0}
            )
            if created:
                registros_creados += 1
        current_date += timedelta(days=1)
        
    print(f"  - Se han creado {registros_creados} registros de avance diario.")
    print("[+] Creación de Avances completada.")

def eliminar_datos(apps, schema_editor):
    # Función para revertir la migración
    Semana = apps.get_model('actividades', 'Semana')
    AvanceDiario = apps.get_model('actividades', 'AvanceDiario')
    print("\nEliminando datos cargados por la migración...")
    Semana.objects.all().delete()
    AvanceDiario.objects.all().delete()
    print("Datos eliminados.")


class Migration(migrations.Migration):

    dependencies = [
        ('actividades', '0002_crear_superuser'), # O la migración que corresponda
    ]

    operations = [
        migrations.RunPython(carga_inicial, reverse_code=eliminar_datos),
    ]